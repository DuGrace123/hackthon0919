"""Reliable media task helpers shared by the desktop UI and the tests.

This module keeps the *process* side of the media pipeline in one place:

* import validation (path, extension, size and batch limits) before any FFmpeg work;
* a cancellable FFmpeg job runner that reports real progress, closes pipes and
  never leaves a child process behind;
* import / proxy / export workflows that write to unique temporary files, only
  publish a result after validation, and clean up their own leftovers on failure
  or cancellation.

It intentionally builds on ``video_editing_engine`` (probe, thumbnail, proxy and
render commands) instead of duplicating a second media pipeline.
"""
from __future__ import annotations

import atexit
import os
import re
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Optional

from video_editing_engine import (
    AUDIO_EXT, VIDEO_EXT, MAX_IMPORT_FILE_BYTES, MAX_IMPORT_FILE_COUNT, MAX_IMPORT_TOTAL_BYTES,
    build_proxy_command, normalize_media_path, probe_media, thumbnail, thumbnail_path,
    validate_rendered_mp4, validate_import_file,
)

_CREATIONFLAGS = 0x08000000 if os.name == 'nt' else 0
_TIME_RE = re.compile(r'time=(\d+):(\d+):(\d+(?:\.\d+)?)')

STATUS_OK = 'ok'
STATUS_FAILED = 'failed'
STATUS_CANCELLED = 'cancelled'


# --------------------------------------------------------------------------- import validation

@dataclass
class ImportPlan:
    """Result of validating a batch of user-selected paths before analysis."""
    videos: list[str] = field(default_factory=list)
    audios: list[str] = field(default_factory=list)
    rejected: list[tuple[str, str]] = field(default_factory=list)  # (display name, reason)
    duplicates: list[str] = field(default_factory=list)
    total_bytes: int = 0

    @property
    def accepted(self) -> list[str]:
        return self.videos + self.audios


def plan_import(paths: Iterable[str], known: Iterable[str] = (), *, max_file_bytes: int = MAX_IMPORT_FILE_BYTES,
                max_count: int = MAX_IMPORT_FILE_COUNT, max_total_bytes: int = MAX_IMPORT_TOTAL_BYTES) -> ImportPlan:
    """Validate paths, split them into video/audio, drop duplicates and enforce batch limits.

    ``known`` lists normalized paths that are already imported or queued; they are
    reported as duplicates instead of being analysed twice.  Nothing here touches
    FFmpeg – the media probe still decides whether a file is really usable.
    """
    plan = ImportPlan()
    seen = set(str(k) for k in known)
    for raw in paths:
        raw = str(raw or '').strip()
        if not raw:
            continue
        name = Path(raw).name or raw
        try:
            info = validate_import_file(raw, max_file_bytes=max_file_bytes)
        except ValueError as exc:
            plan.rejected.append((name, str(exc)))
            continue
        path = info['path']
        if path in seen:
            plan.duplicates.append(path)
            continue
        seen.add(path)
        if len(plan.accepted) >= max_count:
            plan.rejected.append((name, f'超过单批导入数量上限（最多 {max_count} 个文件），请分批导入'))
            continue
        if plan.total_bytes + info['size'] > max_total_bytes:
            plan.rejected.append((name, f'超过单批导入总大小上限（{_human_size(max_total_bytes)}），请分批导入'))
            continue
        plan.total_bytes += info['size']
        (plan.audios if info['kind'] == 'audio' else plan.videos).append(path)
    return plan


def _human_size(size: int) -> str:
    value = float(size)
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if value < 1024 or unit == 'TB':
            return f'{value:.0f} {unit}' if unit in ('B', 'KB') else f'{value:.1f} {unit}'
        value /= 1024
    return f'{size} B'


# --------------------------------------------------------------------------- process registry

class ProcessRegistry:
    """Tracks live FFmpeg children so cancellation and shutdown can stop them."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._procs: dict[int, subprocess.Popen] = {}

    def add(self, proc: subprocess.Popen) -> None:
        with self._lock:
            self._procs[proc.pid] = proc

    def remove(self, proc: subprocess.Popen) -> None:
        with self._lock:
            self._procs.pop(proc.pid, None)

    def live(self) -> list[subprocess.Popen]:
        with self._lock:
            return [p for p in self._procs.values() if p.poll() is None]

    def terminate_all(self, timeout: float = 3.0) -> int:
        """Terminate every tracked child and wait for it. Returns the number stopped."""
        stopped = 0
        for proc in self.live():
            stop_process(proc, timeout)
            stopped += 1
            self.remove(proc)
        return stopped


REGISTRY = ProcessRegistry()
atexit.register(REGISTRY.terminate_all)


def stop_process(proc: subprocess.Popen, timeout: float = 3.0) -> None:
    """Terminate ``proc`` gracefully, escalate to kill, then always wait and close pipes."""
    try:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=timeout)
    except OSError:
        pass
    finally:
        for stream in (proc.stdin, proc.stdout, proc.stderr):
            try:
                if stream:
                    stream.close()
            except OSError:
                pass


# --------------------------------------------------------------------------- FFmpeg job runner

@dataclass
class JobResult:
    status: str
    returncode: Optional[int] = None
    log: str = ''
    output: str = ''
    detail: str = ''

    @property
    def ok(self) -> bool:
        return self.status == STATUS_OK

    @property
    def cancelled(self) -> bool:
        return self.status == STATUS_CANCELLED

    def message(self) -> str:
        if self.ok:
            return '完成'
        if self.cancelled:
            return '已取消'
        return self.detail or (self.log.strip().splitlines() or ['FFmpeg 返回错误'])[-1][-300:]


def run_ffmpeg_job(cmd: list[str], *, duration: float = 0.0, cancel: Optional[threading.Event] = None,
                   on_progress: Optional[Callable[[int], None]] = None, poll_interval: float = 0.05,
                   log_lines: int = 40) -> JobResult:
    """Run an FFmpeg command, stream its progress, and honour cancellation.

    * ``duration`` (seconds) converts FFmpeg's ``time=`` reports into 0–99 %;
    * ``cancel`` is checked continuously – when set, the child is terminated and
      the result is ``STATUS_CANCELLED`` (never reported as an FFmpeg failure);
    * pipes are always drained and closed and the child is always waited for.
    """
    if cancel is not None and cancel.is_set():
        return JobResult(STATUS_CANCELLED, detail='任务开始前已取消')
    try:
        proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                                text=True, encoding='utf-8', errors='replace', creationflags=_CREATIONFLAGS)
    except FileNotFoundError:
        return JobResult(STATUS_FAILED, detail='未找到 FFmpeg，请确认 ffmpeg 已安装并加入 PATH')
    except OSError as exc:
        return JobResult(STATUS_FAILED, detail=f'无法启动 FFmpeg：{exc}')
    REGISTRY.add(proc)
    tail: list[str] = []
    cancelled = False
    last_percent = -1

    def reader() -> None:
        try:
            for line in proc.stderr:  # type: ignore[union-attr]
                tail.append(line)
                if len(tail) > log_lines:
                    del tail[0]
                if duration > 0 and on_progress is not None:
                    m = _TIME_RE.search(line)
                    if m:
                        seconds = int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3])
                        percent = max(0, min(99, int(seconds / duration * 100)))
                        nonlocal last_percent
                        if percent != last_percent:
                            last_percent = percent
                            on_progress(percent)
        except (OSError, ValueError):
            pass

    thread = threading.Thread(target=reader, name='ffmpeg-stderr', daemon=True)
    thread.start()
    try:
        while proc.poll() is None:
            if cancel is not None and cancel.is_set():
                cancelled = True
                stop_process(proc)
                break
            time.sleep(poll_interval)
    finally:
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            stop_process(proc)
        thread.join(timeout=5)
        for stream in (proc.stderr,):
            try:
                if stream:
                    stream.close()
            except OSError:
                pass
        REGISTRY.remove(proc)
    log = ''.join(tail)[-2400:]
    if cancelled:
        return JobResult(STATUS_CANCELLED, proc.returncode, log, detail='已取消')
    if proc.returncode != 0:
        return JobResult(STATUS_FAILED, proc.returncode, log)
    if on_progress is not None and duration > 0:
        on_progress(99)
    return JobResult(STATUS_OK, proc.returncode, log)


# --------------------------------------------------------------------------- temp file helpers

def unique_part_path(final: str | os.PathLike[str], suffix: str = '') -> Path:
    """A unique temporary path *next to* ``final`` so the final rename stays atomic."""
    target = Path(final)
    ext = suffix or target.suffix or '.tmp'
    return target.parent / f'.{target.stem}.{uuid.uuid4().hex[:12]}.part{ext}'


def remove_quietly(path: str | os.PathLike[str] | None) -> bool:
    if not path:
        return False
    try:
        Path(path).unlink()
        return True
    except FileNotFoundError:
        return False
    except OSError:
        return False


def publish_file(temp: str | os.PathLike[str], final: str | os.PathLike[str]) -> None:
    """Atomically move ``temp`` over ``final`` (replaces an existing target)."""
    Path(final).parent.mkdir(parents=True, exist_ok=True)
    os.replace(temp, final)


# --------------------------------------------------------------------------- import workflow

@dataclass
class ImportSummary:
    total: int = 0
    succeeded: list[dict] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)
    cancelled: bool = False

    def text(self) -> str:
        parts = [f'成功 {len(self.succeeded)} 个']
        if self.failed:
            parts.append(f'失败 {len(self.failed)} 个')
        if self.cancelled:
            parts.append('已取消剩余文件')
        return '，'.join(parts)


def analyze_one(ffmpeg: str, path: str, cache_dir: str | os.PathLike[str]) -> dict:
    """Probe a single video and make sure a valid thumbnail exists for it.

    Raises ``ValueError`` with a Chinese, actionable reason.  A failed thumbnail
    never leaves a half-written file behind.
    """
    meta = probe_media(ffmpeg, path)
    thumb = thumbnail_path(str(cache_dir), meta['path'])
    if not (Path(thumb).exists() and Path(thumb).stat().st_size > 0):
        thumbnail(ffmpeg, meta['path'], thumb, min(2.0, meta['duration'] * .25))
    meta['thumbnail'] = thumb
    return meta


def import_media_batch(ffmpeg: str, paths: Iterable[str], cache_dir: str | os.PathLike[str], *,
                       cancel: Optional[threading.Event] = None,
                       on_progress: Optional[Callable[[int, int, str], None]] = None,
                       on_item: Optional[Callable[[dict], None]] = None,
                       on_error: Optional[Callable[[str, str], None]] = None) -> ImportSummary:
    """Probe and thumbnail every path; one bad file never aborts the batch."""
    paths = [str(p) for p in paths]
    summary = ImportSummary(total=len(paths))
    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    for index, path in enumerate(paths):
        if cancel is not None and cancel.is_set():
            summary.cancelled = True
            break
        name = Path(path).name
        if on_progress:
            on_progress(index, len(paths), name)
        try:
            meta = analyze_one(ffmpeg, path, cache_dir)
        except Exception as exc:  # noqa: BLE001 - every reason is reported to the user
            reason = str(exc) or exc.__class__.__name__
            summary.failed.append((name, reason))
            if on_error:
                on_error(name, reason)
            continue
        summary.succeeded.append(meta)
        if on_item:
            on_item(meta)
    if on_progress and not summary.cancelled:
        on_progress(len(paths), len(paths), '')
    return summary


# --------------------------------------------------------------------------- proxy workflow

def generate_proxy(ffmpeg: str, source: str, out: str, *, duration: float = 0.0,
                   cancel: Optional[threading.Event] = None,
                   on_progress: Optional[Callable[[int], None]] = None) -> JobResult:
    """Render a playback proxy into a unique temp file and publish it only on success."""
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    temp = unique_part_path(out, '.mp4')
    result = run_ffmpeg_job(build_proxy_command(ffmpeg, source, str(temp)), duration=duration, cancel=cancel,
                            on_progress=on_progress)
    if result.ok:
        try:
            if not temp.exists() or temp.stat().st_size < 1024:
                raise ValueError('代理文件为空或不完整')
            probe_media(ffmpeg, str(temp))
            publish_file(temp, out)
            result.output = out
            if on_progress:
                on_progress(100)
        except Exception as exc:  # noqa: BLE001
            remove_quietly(temp)
            return JobResult(STATUS_FAILED, result.returncode, result.log, detail=f'代理校验失败：{exc}')
    else:
        remove_quietly(temp)
    return result


# --------------------------------------------------------------------------- export workflow

def render_export(ffmpeg: str, build_command: Callable[[str], list[str]], final: str, *, duration: float = 0.0,
                  expect_audio: bool = True, cancel: Optional[threading.Event] = None,
                  on_progress: Optional[Callable[[int], None]] = None) -> JobResult:
    """Render to a unique temp file beside ``final``; validate; then atomically replace.

    ``build_command(output_path)`` must return the FFmpeg argument list writing to
    ``output_path`` (normally ``build_render_command`` with the temp path).  The
    user's previous ``final`` file is untouched unless validation succeeds.
    """
    target = Path(final)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = unique_part_path(target, '.mp4')
    try:
        cmd = build_command(str(temp))
    except Exception as exc:  # noqa: BLE001
        return JobResult(STATUS_FAILED, detail=f'无法生成导出命令：{exc}')
    result = run_ffmpeg_job(cmd, duration=duration, cancel=cancel, on_progress=on_progress)
    if not result.ok:
        remove_quietly(temp)
        return result
    try:
        meta = validate_rendered_mp4(ffmpeg, str(temp), expect_audio=expect_audio)
        publish_file(temp, target)
    except Exception as exc:  # noqa: BLE001
        remove_quietly(temp)
        return JobResult(STATUS_FAILED, result.returncode, result.log, detail=f'编码结束但兼容性校验失败：{exc}')
    result.output = str(target)
    result.detail = f'兼容性校验通过 · H.264/AAC · {meta["width"]}×{meta["height"]} · {meta["duration"]:.1f}秒'
    if on_progress:
        on_progress(100)
    return result


def leftover_part_files(folder: str | os.PathLike[str]) -> list[Path]:
    """List ``*.part*`` temp files in ``folder`` (used by tests and diagnostics)."""
    root = Path(folder)
    if not root.exists():
        return []
    return sorted(p for p in root.iterdir() if '.part' in p.name and p.is_file())
