"""Member 2 (media & export) reliability checks: import validation, probe, thumbnails, proxy, export.

Runs with the system ``ffmpeg`` only – no Qt, no external fixtures.  A real sample
MP4 can be supplied for the end-to-end section via ``LINGJIAN_SAMPLE_MP4`` or the
first command-line argument; otherwise a small file is generated with FFmpeg.

    python -m tests.test_media_pipeline [sample.mp4]
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

from video_editing_engine import (
    MAX_IMPORT_FILE_BYTES, Project, build_render_command, media_cache_key, probe_media, proxy_path,
    thumbnail, thumbnail_path, validate_import_file, validate_rendered_mp4,
)
import media_tasks
from media_tasks import (
    STATUS_CANCELLED, STATUS_FAILED, STATUS_OK, generate_proxy, import_media_batch, leftover_part_files,
    plan_import, render_export, run_ffmpeg_job, unique_part_path,
)

ROOT = Path(__file__).parents[1]
FF = str(ROOT / 'ffmpeg.exe') if (ROOT / 'ffmpeg.exe').exists() else (shutil.which('ffmpeg') or 'ffmpeg')
CHECKS = 0


def check(condition, message):
    global CHECKS
    CHECKS += 1
    if not condition:
        raise AssertionError(message)


def expect_error(fn, *needles):
    try:
        fn()
    except ValueError as exc:
        text = str(exc)
        for needle in needles:
            check(needle in text, f'error text {text!r} should mention {needle!r}')
        return text
    raise AssertionError('expected ValueError')


def ffmpeg(*args):
    p = subprocess.run([FF, '-y', '-v', 'error', *args], capture_output=True, text=True, encoding='utf-8', errors='replace',
                       creationflags=0x08000000 if os.name == 'nt' else 0)
    if p.returncode:
        raise AssertionError(p.stderr[-1500:])


def make_video(path: Path, seconds: float = 3.0, audio: bool = True, size='320x180'):
    args = ['-f', 'lavfi', '-i', f'testsrc2=size={size}:rate=30']
    if audio:
        args += ['-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000']
    args += ['-t', f'{seconds}', '-c:v', 'libx264', '-pix_fmt', 'yuv420p']
    if audio:
        args += ['-c:a', 'aac']
    ffmpeg(*args, str(path))
    return path


# ------------------------------------------------------------------ import validation

def test_import_validation(base: Path):
    good = make_video(base / 'good.mp4', 2)
    missing = base / 'missing.mp4'
    wrong_ext = base / 'notes.txt'
    wrong_ext.write_text('hello', encoding='utf-8')
    fake = base / 'fake.mp4'
    fake.write_bytes(b'this is not a video at all ' * 200)
    empty = base / 'empty.mp4'
    empty.write_bytes(b'')
    folder = base / 'folder.mp4'
    folder.mkdir()
    audio = base / 'music.wav'
    ffmpeg('-f', 'lavfi', '-i', 'sine=frequency=220:sample_rate=48000', '-t', '2', str(audio))

    expect_error(lambda: validate_import_file(missing), '文件不存在', 'missing.mp4')
    expect_error(lambda: validate_import_file(wrong_ext), '不支持的文件格式', 'notes.txt')
    expect_error(lambda: validate_import_file(empty), '0 字节', 'empty.mp4')
    expect_error(lambda: validate_import_file(folder), '不是普通文件')
    expect_error(lambda: validate_import_file(good, max_file_bytes=10), '文件过大')
    info = validate_import_file(good)
    check(info['kind'] == 'video' and info['size'] > 0, 'good video should validate')
    check(validate_import_file(audio)['kind'] == 'audio', 'wav should be audio')
    check(MAX_IMPORT_FILE_BYTES >= 1024 ** 3, 'default file limit should suit desktop video')

    # Extension alone must not be trusted: the probe rejects fake / empty / audio-only inputs.
    expect_error(lambda: probe_media(FF, str(fake)), 'fake.mp4')
    expect_error(lambda: probe_media(FF, str(empty)), 'empty.mp4')
    expect_error(lambda: probe_media(FF, str(missing)), 'missing.mp4')
    expect_error(lambda: probe_media(FF, str(audio)), '没有视频流')
    expect_error(lambda: probe_media('definitely-not-ffmpeg-binary', str(good)), 'FFmpeg')
    meta = probe_media(FF, str(good))
    check(meta['width'] == 320 and meta['height'] == 180 and meta['fps'] > 0 and 1.9 < meta['duration'] < 2.1, 'probe fields')
    check(meta['size'] == good.stat().st_size and meta['mtime_ns'] == good.stat().st_mtime_ns, 'probe records size/mtime')

    # Batch planning: dedupe, limits, classification, per-file reasons.
    same_twice = [str(good), str(good), str(Path(base) / '.' / 'good.mp4')]
    plan = plan_import(same_twice + [str(missing), str(wrong_ext), str(fake), str(empty), str(audio)])
    names = [Path(v).name for v in plan.videos]
    check(names == ['good.mp4', 'fake.mp4'], f'video dedupe + fake passes pre-validation (probe decides later): {names}')
    check(len(plan.duplicates) == 2, f'duplicates {plan.duplicates}')
    check(len(plan.audios) == 1, 'audio classified separately')
    reasons = dict(plan.rejected)
    check(set(reasons) == {'missing.mp4', 'notes.txt', 'empty.mp4'}, f'rejected {reasons}')
    check(all('：' in r for r in reasons.values()), 'reasons are actionable Chinese text')

    plan = plan_import([str(good)], known=[media_tasks.normalize_media_path(good)])
    check(plan.videos == [] and plan.duplicates, 'already-imported path is a duplicate, not a new task')

    videos = [make_video(base / f'batch{i}.mp4', .5, audio=False, size='64x64') for i in range(4)]
    plan = plan_import([str(v) for v in videos], max_count=2)
    check(len(plan.videos) == 2 and len(plan.rejected) == 2 and '数量上限' in plan.rejected[0][1], 'count limit')
    one = videos[0].stat().st_size
    plan = plan_import([str(v) for v in videos], max_total_bytes=one * 2 + 1)
    check(len(plan.videos) == 2 and '总大小上限' in plan.rejected[0][1], 'total size limit')
    plan = plan_import([str(v) for v in videos], max_file_bytes=one - 1)
    check(len(plan.videos) == 0 and all('文件过大' in r for _, r in plan.rejected), 'per-file limit')
    return good, fake, audio


# ------------------------------------------------------------------ thumbnails & cache keys

def test_thumbnail_and_cache(base: Path, good: Path, fake: Path):
    thumbs = base / 'thumbs'
    out = thumbnail_path(str(thumbs), str(good))
    thumbnail(FF, str(good), out, .5)
    check(Path(out).stat().st_size > 100, 'thumbnail written')
    check(not leftover_part_files(thumbs), 'no temp thumbnail left after success')
    # Seeking beyond the end falls back to the first frame instead of failing.
    thumbnail(FF, str(good), out, 999)
    check(Path(out).stat().st_size > 100, 'thumbnail fallback works')
    bad_out = str(thumbs / 'fake-thumb.jpg')
    expect_error(lambda: thumbnail(FF, str(fake), bad_out), '缩略图生成失败', 'fake.mp4')
    check(not Path(bad_out).exists() and not leftover_part_files(thumbs), 'failed thumbnail leaves nothing behind')

    twin_dir = base / 'twin'
    twin_dir.mkdir()
    twin = make_video(twin_dir / 'good.mp4', 1, audio=False, size='64x64')
    check(media_cache_key(good) != media_cache_key(twin), 'same file name in another folder gets a different key')
    check(thumbnail_path(str(thumbs), str(good)) != thumbnail_path(str(thumbs), str(twin)), 'thumbnail names do not collide')
    check(proxy_path(str(thumbs), str(good)) != proxy_path(str(thumbs), str(twin)), 'proxy names do not collide')
    key_before = media_cache_key(good)
    os.utime(good, (time.time() + 5, time.time() + 5))
    check(media_cache_key(good) != key_before, 'cache key changes when the file changes')

    # Batch import: one bad file does not stop the others; the summary keeps each reason.
    events = {'items': [], 'errors': [], 'progress': []}
    summary = import_media_batch(FF, [str(good), str(fake), str(twin)], thumbs, on_progress=lambda i, n, name: events['progress'].append((i, n, name)),
                                 on_item=lambda m: events['items'].append(m['path']), on_error=lambda name, reason: events['errors'].append((name, reason)))
    check(len(summary.succeeded) == 2 and len(summary.failed) == 1 and summary.failed[0][0] == 'fake.mp4', f'batch summary {summary.failed}')
    check(events['errors'] == summary.failed and len(events['items']) == 2, 'callbacks mirror the summary')
    check(events['progress'][0] == (0, 3, 'good.mp4') and events['progress'][-1] == (3, 3, ''), f'progress reports total and current file: {events["progress"]}')
    check('成功 2 个' in summary.text() and '失败 1 个' in summary.text(), summary.text())
    check(all(Path(m['thumbnail']).stat().st_size > 0 for m in summary.succeeded), 'thumbnails exist for successes')

    cancel = threading.Event()
    cancel.set()
    summary = import_media_batch(FF, [str(good)], thumbs, cancel=cancel)
    check(summary.cancelled and not summary.succeeded, 'cancelled before start processes nothing')


# ------------------------------------------------------------------ FFmpeg job runner

def test_job_runner(base: Path):
    long_out = base / 'long.mp4'
    # Read the synthetic source at realtime speed so fast machines cannot finish
    # the whole encode before the cancellation timer fires.
    cmd = [FF, '-y', '-v', 'info', '-re', '-f', 'lavfi', '-i', 'testsrc2=size=640x360:rate=30', '-t', '60', '-c:v', 'libx264', '-preset', 'ultrafast', str(long_out)]
    cancel = threading.Event()
    progress = []
    timer = threading.Timer(.6, cancel.set)
    timer.start()
    t0 = time.time()
    result = run_ffmpeg_job(cmd, duration=60, cancel=cancel, on_progress=progress.append)
    check(result.status == STATUS_CANCELLED and time.time() - t0 < 15, f'cancel stops ffmpeg promptly: {result.status}')
    check(not media_tasks.REGISTRY.live(), 'no live ffmpeg after cancel')
    check(progress == sorted(progress) and all(0 <= p <= 99 for p in progress), 'progress is monotonic 0-99')

    result = run_ffmpeg_job([FF, '-y', '-v', 'error', '-i', str(base / 'does-not-exist.mp4'), '-f', 'null', '-'])
    check(result.status == STATUS_FAILED and result.message(), 'failure carries a message')
    result = run_ffmpeg_job(['no-such-ffmpeg-binary', '-version'])
    check(result.status == STATUS_FAILED and 'FFmpeg' in result.message(), 'missing binary is a readable failure')
    result = run_ffmpeg_job([FF, '-y', '-v', 'info', '-f', 'lavfi', '-i', 'testsrc2=size=64x64:rate=30', '-t', '1', '-c:v', 'libx264', str(base / 'short.mp4')], duration=1, on_progress=progress.append)
    check(result.ok and progress[-1] == 99, 'ok job ends at 99% before publish')
    check(not media_tasks.REGISTRY.live(), 'registry drained')


# ------------------------------------------------------------------ proxy workflow

def test_proxy(base: Path, good: Path, fake: Path):
    cache = base / 'proxies'
    out = proxy_path(str(cache), str(good))
    progress = []
    result = generate_proxy(FF, str(good), out, duration=2, on_progress=progress.append)
    check(result.ok and result.output == out and Path(out).stat().st_size > 1024, 'proxy generated')
    check(progress[-1] == 100 and not leftover_part_files(cache), 'proxy progress completes and temp is gone')
    meta = probe_media(FF, out)
    check('h264' in meta['codec'] and meta['has_audio'], 'proxy is H.264 with audio')

    bad_out = str(cache / 'fake.proxy.mp4')
    result = generate_proxy(FF, str(fake), bad_out)
    check(result.status == STATUS_FAILED and not Path(bad_out).exists() and not leftover_part_files(cache), 'failed proxy leaves nothing')
    check(result.message(), 'failed proxy has a message')

    slow_src = make_video(base / 'slow-src.mp4', 25, audio=True, size='640x360')
    cancel = threading.Event()
    cancel_out = proxy_path(str(cache), str(slow_src))
    threading.Timer(.5, cancel.set).start()
    result = generate_proxy(FF, str(slow_src), cancel_out, duration=25, cancel=cancel)
    check(result.status == STATUS_CANCELLED, f'proxy cancel status {result.status}')
    check(not Path(cancel_out).exists() and not leftover_part_files(cache), 'cancelled proxy is not published and temp is cleaned')
    check(Path(out).exists(), 'earlier successful proxy cache untouched')
    check(not media_tasks.REGISTRY.live(), 'no ffmpeg left after proxy cancel')


# ------------------------------------------------------------------ export workflow

def test_export(base: Path, good: Path, sample: Path):
    out_dir = base / 'exports'
    out_dir.mkdir()
    final = out_dir / 'final.mp4'
    original = b'user original file that must survive failures'
    final.write_bytes(original)

    meta = probe_media(FF, str(sample))
    project = Project('导出测试')
    project.add(meta)
    project.trim(0, .4, min(meta['duration'], 2.2))
    project.clips[0].caption = '裁剪导出'
    build = lambda temp: build_render_command(FF, project, temp, 320, 180, 'standard')  # noqa: E731

    # Failure: an unusable build command never touches the user's file.
    result = render_export(FF, lambda temp: [FF, '-y', '-v', 'error', '-i', str(base / 'nope.mp4'), temp], str(final), duration=1)
    check(result.status == STATUS_FAILED and final.read_bytes() == original, 'failed export protects existing target')
    check(not leftover_part_files(out_dir), 'failed export cleans temp')

    # Failure: render "succeeds" but validation fails (no audio while audio expected).
    silent = make_video(base / 'silent-src.mp4', 1.5, audio=False)
    result = render_export(FF, lambda temp: [FF, '-y', '-v', 'error', '-i', str(silent), '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', temp], str(final), duration=1.5, expect_audio=True)
    check(result.status == STATUS_FAILED and '缺少音频流' in result.message() and final.read_bytes() == original, 'validation failure keeps original')
    check(not leftover_part_files(out_dir), 'validation failure cleans temp')

    # Cancel: temp removed, original untouched, status is "cancelled" not "failed".
    cancel = threading.Event()
    threading.Timer(.5, cancel.set).start()
    slow = make_video(base / 'slow-export-src.mp4', 30, audio=True, size='640x360')
    slow_project = Project('慢导出')
    slow_project.add(probe_media(FF, str(slow)))
    result = render_export(FF, lambda temp: build_render_command(FF, slow_project, temp, 640, 360, 'high'), str(final), duration=30, cancel=cancel)
    check(result.status == STATUS_CANCELLED and result.message() == '已取消', f'export cancel status {result.status}')
    check(final.read_bytes() == original and not leftover_part_files(out_dir), 'cancelled export protects target and cleans temp')
    check(not media_tasks.REGISTRY.live(), 'no ffmpeg left after export cancel')

    # Success: real trimmed export, atomic replace, re-probe and tail decode.
    progress = []
    result = render_export(FF, build, str(final), duration=project.duration, expect_audio=True, on_progress=progress.append)
    check(result.ok and result.output == str(final) and progress[-1] == 100, f'export ok: {result.message()}')
    check(final.read_bytes() != original and final.stat().st_size > 4096, 'target replaced with the render')
    check(not leftover_part_files(out_dir), 'no temp after success')
    again = validate_rendered_mp4(FF, str(final), expect_audio=True)
    check('h264' in again['codec'] and again['has_audio'] and abs(again['duration'] - project.duration) < .35, f'exported mp4 re-probes: {again["duration"]} vs {project.duration}')
    check(again['width'] == 320 and again['height'] == 180, 'preset size honoured')
    cmd = build(str(final))
    check('+faststart' in cmd and 'yuv420p' in cmd and 'libx264' in cmd and 'aac' in cmd, 'encoder settings preserved')
    # Presets: landscape / portrait / square all build.
    for w, h in ((1280, 720), (720, 1280), (1080, 1080)):
        check(build_render_command(FF, project, str(unique_part_path(final)), w, h, 'high'), f'preset {w}x{h}')
    tmp = unique_part_path(final)
    check(tmp.parent == final.parent and '.part' in tmp.name and tmp != unique_part_path(final), 'temp paths are unique and beside target')


def main():
    sample_arg = sys.argv[1] if len(sys.argv) > 1 else os.environ.get('LINGJIAN_SAMPLE_MP4', '')
    base = Path(tempfile.mkdtemp(prefix='lingjian-media-'))
    try:
        good, fake, audio = test_import_validation(base)
        print('[1/5] import validation PASS', flush=True)
        test_thumbnail_and_cache(base, good, fake)
        print('[2/5] thumbnails & cache PASS', flush=True)
        test_job_runner(base)
        print('[3/5] job runner / cancel PASS', flush=True)
        test_proxy(base, good, fake)
        print('[4/5] proxy PASS', flush=True)
        sample = Path(sample_arg) if sample_arg and Path(sample_arg).exists() else good
        test_export(base, good, sample)
        print(f'[5/5] export PASS (sample: {"external" if sample != good else "generated"})', flush=True)
        media_tasks.REGISTRY.terminate_all()
        print(f'MEDIA PIPELINE PASS · {CHECKS} checks')
    finally:
        media_tasks.REGISTRY.terminate_all()
        shutil.rmtree(base, ignore_errors=True)


if __name__ == '__main__':
    main()
