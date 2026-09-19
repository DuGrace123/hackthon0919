"""Member 4: reviewable AI plans, independent of Qt and the team's storage layer.

The host supplies an ownership-aware backend with atomic compare-and-swap saves.
Only server-resolved media is processed. Plan generation never saves a project.
"""
from __future__ import annotations

import copy
import math
import os
import re
import tempfile
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Protocol

from ai_story_planner import (
    APIConfig, AIRequestError, AnalysisCancelled, analyze_video, chronological_sequence,
    local_sequence, plan_sequence, run_analysis_command,
)
from builtin_music import music_by_id, resolve_music
from builtin_sound_effects import resolve_sfx, sfx_by_id
from creative_treatment import apply_global_creative_treatment
from edit_plan import apply_opening_treatment, build_edit_plan, opening_preset_choices, plan_preview_text, plan_to_clips, plan_to_overlays
from video_editing_engine import Clip, OverlayClip, Project, SFXCue

ROOT = Path(__file__).resolve().parent


class WorkflowError(RuntimeError):
    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code, self.status = code, status


class RevisionConflict(WorkflowError):
    def __init__(self):
        super().__init__('revision_conflict', '工程已改变，请刷新并重新生成方案。', 409)


@dataclass(frozen=True)
class MediaSource:
    id: str
    path: Path
    name: str
    duration: float
    has_audio: bool
    capture_order: str = ''


@dataclass(frozen=True)
class ProjectSnapshot:
    project: Project
    revision: int
    version_token: str | None = None


class WorkflowBackend(Protocol):
    """Implement access checks in every method; do not return shared live objects.

    Missing/unauthorized IDs must raise WorkflowError(..., status=404).
    commit_project must compare revision AND save atomically, raising
    RevisionConflict on mismatch. Its revision must increase on every save.
    When get_project returns a version_token, commit_project must also compare
    expected_token inside that transaction to detect repeated external writes.
    """
    def get_project(self, project_id: str, owner_id: str) -> ProjectSnapshot: ...
    def resolve_media(self, project_id: str, media_id: str, owner_id: str) -> MediaSource: ...
    def commit_project(self, project_id: str, owner_id: str, project: Project,
                       expected_revision: int, *, expected_token: str | None = None) -> ProjectSnapshot: ...


def config_from_environment() -> APIConfig:
    """Call at server startup. No keys, endpoint overrides or models from clients."""
    return APIConfig(
        base_url=os.environ.get('FIGSTUDIO_AI_BASE_URL', 'https://api.openai.com'),
        api_key=os.environ.get('FIGSTUDIO_AI_API_KEY', ''),
        model=os.environ.get('FIGSTUDIO_AI_MODEL', 'gpt-5-mini'),
        transcription_model=os.environ.get('FIGSTUDIO_AI_TRANSCRIPTION_MODEL', 'gpt-4o-mini-transcribe'),
        timeout=60,
    )


def validate_cloud_config(config: APIConfig | None) -> APIConfig:
    """Copy and check a server-side cloud configuration; web requests need HTTPS and a bounded timeout."""
    config = copy.deepcopy(config or APIConfig())
    if config.api_key:
        config.endpoint('responses')
        if not config.base_url.strip().startswith('https://'):
            raise ValueError('Web cloud requests require a server-configured HTTPS endpoint')
        if (isinstance(config.timeout, bool) or not isinstance(config.timeout, (int, float))
                or not 1 <= config.timeout <= 180):
            raise ValueError('Cloud timeout must be between 1 and 180 seconds')
    return config


ROLE_LABELS = {'hook': '冷开场钩子', 'setup': '铺垫', 'development': '发展', 'climax': '高潮', 'outro': '收尾', 'broll': '空镜'}
TRANSITION_LABELS = {'none': '直接切换', 'cut': '直接切换', 'fade': '淡入淡出', 'dissolve': '叠化', 'wipe_left': '向左擦除',
                     'wipe_right': '向右擦除', 'slide_left': '向左滑动', 'slide_right': '向右滑动', 'circle': '圆形遮罩',
                     'smooth': '平滑过渡', 'pip_zoom': '画中画推近', 'tear_left': '左撕裂', 'tear_right': '右撕裂',
                     'pixelize': '像素化', 'squeeze': '挤压', 'radial': '径向', 'fade_black': '黑场', 'fade_white': '白场',
                     'cover_left': '左覆盖', 'reveal_right': '右揭示'}


def capture_stamps(sources: list) -> tuple[list[str], str]:
    """Comparable 14-digit stamps for every source: real capture time when all sources carry one, else the selection order."""
    stamps = [str(getattr(item, 'capture_order', '') or '') for item in sources]
    if stamps and all(re.fullmatch(r'\d{14}', x) for x in stamps) and len(set(stamps)) == len(stamps):
        return stamps, 'capture_time'
    if len(sources) == 1 and stamps and re.fullmatch(r'\d{14}', stamps[0]):
        return stamps, 'capture_time'
    return [f'{index + 1:014d}' for index in range(len(sources))], 'selection'


def _identifier(value: str) -> None:
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', value):
        raise WorkflowError('invalid_id', '工程或素材 ID 无效。', 422)


def _revision(value: int) -> None:
    if type(value) is not int or value < 0:
        raise WorkflowError('invalid_revision', '工程版本无效。', 422)


def _fingerprint(source: MediaSource) -> tuple:
    try:
        path = Path(source.path).resolve(strict=True)
        stat = path.stat()
        if not path.is_file():
            raise OSError()
        return str(path), stat.st_size, stat.st_mtime_ns
    except OSError:
        raise WorkflowError('media_unavailable', '素材已移动或不可用，请重新导入。', 409) from None


def _validate_source(source: MediaSource, requested_id: str) -> None:
    if source.id != requested_id:
        raise WorkflowError('media_unavailable', '素材不可用。', 404)
    if (isinstance(source.duration, bool) or not isinstance(source.duration, (int, float))
            or not math.isfinite(source.duration) or not .5 <= source.duration <= 1800):
        raise WorkflowError('invalid_media', '每份素材需为 0.5 秒到 30 分钟的视频。', 422)


def analyze_local(ffmpeg: str, source: MediaSource, checkpoint: Callable) -> list[dict]:
    """Sample actual scene changes throughout a video; make no semantic claims."""
    result = run_analysis_command([
        ffmpeg, '-nostdin', '-hide_banner', '-i', str(source.path), '-an',
        '-vf', "fps=2,scale=192:-2,select='gt(scene,0.18)',showinfo", '-f', 'null', '-',
    ], timeout=120, checkpoint=checkpoint)
    raw_cuts = re.findall(rb'pts_time:([0-9.]+)', result.stderr)
    cuts = sorted({0.0, source.duration} | {float(x) for x in raw_cuts if 0 < float(x) < source.duration})
    windows = []
    for start, end in zip(cuts, cuts[1:]):
        while end - start >= .5:
            stop = min(end, start + 4.8)
            windows.append((start, stop))
            start = stop
    # Bound prompt size without taking only the beginning of long recordings.
    if len(windows) > 120:
        windows = [windows[round(i * (len(windows) - 1) / 119)] for i in range(120)]
    return [dict(start=round(a, 3), end=round(b, 3), score=60,
                 caption='', reason='本地场景与时长规则选择，未分析语义或转写对白',
                 role='development', stage='other', stability=50, motion=50,
                 audio_value=0, visual_signature=f'{source.id}:{a:.3f}') for a, b in windows]


def _dedupe_captions(sequence: list[dict]) -> list[str]:
    """The same spoken line often spans two adjacent windows; keep the caption once."""
    notes, previous = [], ''
    for index, shot in enumerate(sequence):
        caption = str(shot.get('caption') or '').strip()
        if caption and caption.lower() == previous.lower():
            shot['caption'] = ''
            notes.append(f'第 {index + 1} 个镜头与上一镜头对白相同，字幕只保留一次')
        elif caption:
            previous = caption
    return notes


def _format_stamp(stamp: str) -> str:
    return f'{stamp[:4]}-{stamp[4:6]}-{stamp[6:8]} {stamp[8:10]}:{stamp[10:12]}:{stamp[12:14]}' if re.fullmatch(r'\d{14}', stamp or '') else ''


def _build_report(record: _Record, plan: dict, shots: list[dict], summaries: list[dict], strategy: dict,
                  order_basis: str, opening: str, style: str, notes: list[str], extras: list[str] | None = None) -> dict:
    """Human-readable explanation of the plan: story line, structure, techniques, source usage."""
    validation = plan.get('validation') or {}
    mode = record.public['mode']
    story = str(strategy.get('strategy') or '').strip()
    if not story:
        story = ('本地模式按画面场景切换和目标时长挑选镜头，没有理解画面语义，也没有转写对白；'
                 '正片按拍摄顺序推进。' if mode == 'local' else '模型未返回故事线说明。')
    roles = [shot['role'] for shot in shots]
    role_counts = {role: roles.count(role) for role in ROLE_LABELS if role in roles}
    transitions = [shot['transition'] for shot in shots[1:]]
    transition_counts: dict[str, int] = {}
    for item in transitions:
        transition_counts[item] = transition_counts.get(item, 0) + 1
    total = float(validation.get('duration') or 0)
    average = total / len(shots) if shots else 0
    basis_text = ('按素材文件中的真实拍摄时间排列' if order_basis == 'capture_time'
                  else '素材缺少可靠的拍摄时间，按素材列表中的顺序作为拍摄顺序')
    structure = [
        ('纯时间顺序：所有镜头按拍摄先后排列，不设冷开场' if opening == 'chronological'
         else '冷开场：先用一个最有吸引力的镜头做钩子，之后正片按拍摄顺序推进'),
        basis_text,
        ('拍摄顺序锁已开启：钩子之后的正文不允许倒序' if plan.get('capture_order_locked') else '拍摄顺序锁关闭：允许模型自由排序'),
        f"正文顺序一致率 {float(validation.get('chronology_ratio', 1)) * 100:.0f}%",
        '结构：' + ' → '.join(f'{ROLE_LABELS[role]} {count} 个' for role, count in role_counts.items()),
    ]
    techniques = [f'共 {len(shots)} 个镜头，平均每镜头 {average:.1f} 秒，总长 {total:.1f} 秒（目标 {float(plan.get("target_duration", 0)):.1f} 秒）']
    for name, count in sorted(transition_counts.items(), key=lambda pair: -pair[1]):
        techniques.append(f'{TRANSITION_LABELS.get(name, name)} {count} 处')
    captioned = sum(1 for shot in shots if shot['caption'])
    if captioned:
        techniques.append(f'{captioned} 个镜头带字幕，字幕取自真实语音转写' if mode == 'cloud' else f'{captioned} 个镜头带字幕')
    if notes:
        techniques.append(f'相邻镜头重复对白去重 {len(notes)} 处')
    if style:
        techniques.append(f'导演风格：{style}')
    if mode == 'cloud':
        techniques.append('云端分析：抽帧联系图 + 语音转写，模型评估每个候选镜头的动作、稳定性和叙事价值后选片')
    else:
        techniques.append('本地分析：FFmpeg 场景切换检测，按时长与多样性规则选片')
    techniques.extend(extras or [])
    sources = []
    for index, source in enumerate(record.sources):
        used = [shot for shot in shots if shot['media_id'] == source.id]
        summary = summaries[index] if index < len(summaries) else {}
        sources.append({
            'media_id': source.id, 'name': Path(source.name.replace('\\', '/')).name[:200],
            'duration': source.duration, 'shots_used': len(used),
            'seconds_used': round(sum(shot['end'] - shot['start'] for shot in used), 3),
            'summary': str(summary.get('summary') or ''), 'transcript': str(summary.get('transcript') or ''),
            'capture_time': _format_stamp(plan['source_catalog'][index]['capture_order']) if order_basis == 'capture_time' else '',
            'order': index + 1,
        })
    text_lines = ['故事线：' + story, '']
    text_lines += ['结构与顺序：'] + [f'- {line}' for line in structure] + ['']
    text_lines += ['剪辑手法：'] + [f'- {line}' for line in techniques] + ['']
    text_lines += ['素材使用：'] + [
        f"- {item['order']}. {item['name']} · {item['duration']:.1f}s · 选用 {item['shots_used']} 个镜头 / {item['seconds_used']:.1f}s"
        + (f" · {item['summary']}" if item['summary'] else '') for item in sources] + ['']
    text_lines.append(plan_preview_text(plan))
    return {'story': story, 'structure': structure, 'techniques': techniques, 'sources': sources,
            'order_basis': order_basis, 'opening': opening, 'style': style,
            'chronology_ratio': float(validation.get('chronology_ratio', 1)),
            'report_text': '\n'.join(text_lines)}


@dataclass
class _Record:
    public: dict
    owner_id: str
    sources: list[MediaSource]
    fingerprints: list[tuple]
    snapshot: ProjectSnapshot
    expires_at: float
    cancelled: threading.Event = field(default_factory=threading.Event)
    finished: threading.Event = field(default_factory=threading.Event)
    plan: dict | None = None
    base_plan: dict | None = None
    context: dict = field(default_factory=dict)
    preset: str = 'smart'
    applied_revision: int | None = None
    applied_token: str | None = None


def _style_clips(clips: list, decisions: list[dict]) -> list:
    """Desktop styling: first cut is hard, hook captions are larger and sit in the lower third."""
    for index, clip in enumerate(clips):
        role = str(decisions[index].get('role', 'development')) if index < len(decisions) else 'development'
        if index == 0:
            clip.transition = 'none'
        clip.transition_duration = .32
        if clip.caption_font == '微软雅黑':
            clip.caption_font = '黑体' if role == 'hook' else '微软雅黑'
        clip.caption_size = 54 if role == 'hook' else 42
        clip.caption_bg, clip.caption_bg_opacity = '#000000', .48
        clip.position = 'lower_third' if role == 'hook' else 'bottom'
    return clips


def _plan_sound_cues(plan: dict) -> list:
    cues = []
    for raw in plan.get('sound_cues') or []:
        effect_id = str(raw.get('effect_id') or '')
        meta, path = sfx_by_id(effect_id), resolve_sfx(ROOT, effect_id)
        if meta and Path(path).exists():
            cues.append(SFXCue(path, float(raw.get('start', 0)), meta['name'], float(raw.get('volume', meta['volume'])), effect_id))
    return cues


class AIWorkflow:
    """Bounded, process-local AI jobs with protected apply/undo transactions.

    Use one instance per server process and call close() during lifespan teardown.
    Plans expire after ttl_seconds; projects are persisted by WorkflowBackend.
    """
    def __init__(self, backend: WorkflowBackend, ffmpeg: str, *,
                 cloud_config: APIConfig | None = None, max_workers: int = 2,
                 max_pending: int = 4, max_records: int = 100, ttl_seconds: int = 3600,
                 local_analyzer: Callable = analyze_local, caption_limit: int = 120):
        if min(max_workers, max_records, ttl_seconds) < 1 or max_pending < 0:
            raise ValueError('Invalid workflow limits')
        self.backend, self.ffmpeg = backend, ffmpeg
        self.config = validate_cloud_config(cloud_config)
        self.local_analyzer = local_analyzer
        self.caption_limit = caption_limit
        self.ttl, self.max_records = ttl_seconds, max_records
        self._lock = threading.RLock()
        self._slots = threading.BoundedSemaphore(max_workers + max_pending)
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix='ai-plan')
        self._records: dict[str, _Record] = {}
        self._closed = False

    def configure_cloud(self, config: APIConfig | None) -> None:
        """Swap the server-side cloud configuration at runtime; jobs already running keep the one they started with."""
        validated = validate_cloud_config(config)
        with self._lock:
            self.config = validated

    def capabilities(self) -> dict:
        return {'local_available': bool(self.ffmpeg), 'cloud_available': bool(self.config.api_key and self.ffmpeg),
                'max_sources': 20, 'target_duration': {'min': 5, 'max': 180},
                'max_source_duration': 1800, 'plan_ttl_seconds': self.ttl,
                'cloud_uploads': ['contact_sheets', 'compressed_audio', 'prompt', 'analysis_context'],
                'cloud_notice': '云端分析会发送抽帧图片、音频和剪辑要求，可能产生 API 费用。',
                'local_notice': '本地模式按场景和时长选片，不上传素材、不生成语音字幕。'}

    def create(self, project_id: str, owner_id: str, *, media_ids: list[str], revision: int,
               mode: str = 'local', target_duration: float = 30, prompt: str = '',
               cloud_consent: bool = False, opening: str = 'hook', style: str = '') -> dict:
        _identifier(project_id)
        _revision(revision)
        if not owner_id:
            raise WorkflowError('unauthorized', '请先登录。', 401)
        if mode not in ('local', 'cloud'):
            raise WorkflowError('invalid_mode', '请选择本地或云端模式。', 422)
        if (not isinstance(media_ids, list) or not 1 <= len(media_ids) <= 20):
            raise WorkflowError('invalid_sources', '请选择 1 到 20 份素材。', 422)
        for media_id in media_ids:
            _identifier(media_id)
        if len(set(media_ids)) != len(media_ids):
            raise WorkflowError('duplicate_sources', '请勿重复选择同一份素材。', 422)
        if (isinstance(target_duration, bool) or not isinstance(target_duration, (int, float))
                or not math.isfinite(target_duration) or not 5 <= target_duration <= 180):
            raise WorkflowError('invalid_duration', '目标时长必须为 5 到 180 秒。', 422)
        if not isinstance(prompt, str) or len(prompt) > 2000:
            raise WorkflowError('invalid_prompt', '剪辑要求最多 2000 个字符。', 422)
        if opening not in ('hook', 'chronological'):
            raise WorkflowError('invalid_opening', '开头方式只能是冷开场或纯时间顺序。', 422)
        if not isinstance(style, str) or len(style) > 60:
            raise WorkflowError('invalid_style', '导演风格无效。', 422)
        if mode == 'cloud' and cloud_consent is not True:
            raise WorkflowError('consent_required', '请先确认云端上传内容和 API 用量。', 422)
        if mode == 'cloud' and not self.config.api_key:
            raise WorkflowError('cloud_unavailable', '服务端尚未配置云端 AI，可先使用本地模式。', 503)
        snapshot = copy.deepcopy(self.backend.get_project(project_id, owner_id))
        if snapshot.revision != revision:
            raise RevisionConflict()
        sources = [self.backend.resolve_media(project_id, item, owner_id) for item in media_ids]
        for source, media_id in zip(sources, media_ids):
            _validate_source(source, media_id)
        fingerprints = [_fingerprint(item) for item in sources]
        if not self._slots.acquire(blocking=False):
            raise WorkflowError('busy', 'AI 任务已满，请等待现有任务结束。', 429)
        try:
            with self._lock:
                self._prune()
                if self._closed or len(self._records) >= self.max_records:
                    raise WorkflowError('busy', 'AI 服务暂不可用，请稍后重试。', 503)
                plan_id = uuid.uuid4().hex
                public = {'id': plan_id, 'project_id': project_id, 'base_revision': revision,
                          'mode': mode, 'status': 'queued', 'progress': 0, 'message': '等待分析',
                          'result': None, 'error': None}
                record = _Record(public, owner_id, sources, fingerprints, snapshot, time.monotonic() + self.ttl)
                self._records[plan_id] = record
                self._executor.submit(self._generate, record, target_duration, prompt, opening, style)
                return copy.deepcopy(public)
        except Exception:
            self._slots.release()
            raise

    def _prune(self):
        now = time.monotonic()
        for plan_id, record in list(self._records.items()):
            if record.finished.is_set() and record.expires_at < now:
                del self._records[plan_id]

    def _owned(self, project_id: str, plan_id: str, owner_id: str) -> _Record:
        self._prune()
        record = self._records.get(plan_id)
        if not record or record.owner_id != owner_id or record.public['project_id'] != project_id:
            raise WorkflowError('not_found', '找不到该 AI 方案，可能已过期。', 404)
        self.backend.get_project(project_id, owner_id)  # Permissions may have been revoked.
        return record

    def list(self, project_id: str, owner_id: str) -> list[dict]:
        """Unexpired plans of one owner for one project, newest first (lets a page restore state)."""
        _identifier(project_id)
        with self._lock:
            self._prune()
            self.backend.get_project(project_id, owner_id)
            return [copy.deepcopy(record.public) for record in reversed(list(self._records.values()))
                    if record.owner_id == owner_id and record.public['project_id'] == project_id]

    def get(self, project_id: str, plan_id: str, owner_id: str) -> dict:
        with self._lock:
            return copy.deepcopy(self._owned(project_id, plan_id, owner_id).public)

    def cancel(self, project_id: str, plan_id: str, owner_id: str) -> dict:
        with self._lock:
            record = self._owned(project_id, plan_id, owner_id)
            if record.public['status'] in ('applied', 'undone'):
                raise WorkflowError('invalid_state', '方案已应用，请使用撤销操作。', 409)
            if record.public['status'] not in ('failed', 'cancelled'):
                record.cancelled.set()
                record.plan = None
                record.public.update(status='cancelled', message='已取消，工程未改变', result=None)
            return copy.deepcopy(record.public)

    def _checkpoint(self, record: _Record):
        if record.cancelled.is_set() or self._closed:
            raise AnalysisCancelled('Analysis cancelled')
        if time.monotonic() > record.expires_at:
            raise AIRequestError('AI 分析超时，请缩短素材后重试。', 'analysis_timeout', True)

    def _progress(self, record: _Record, value: int, message: str):
        with self._lock:
            self._checkpoint(record)
            record.public.update(status='running', progress=value, message=message)

    def _check_sources(self, record: _Record):
        for source, fingerprint in zip(record.sources, record.fingerprints):
            current = self.backend.resolve_media(record.public['project_id'], source.id, record.owner_id)
            if current != source or _fingerprint(current) != fingerprint:
                raise WorkflowError('media_changed', '素材已改变，请重新生成方案。', 409)

    def _generate(self, record: _Record, target: float, prompt: str, opening: str = 'hook', style: str = ''):
        try:
            checkpoint = lambda: self._checkpoint(record)
            analyses, summaries = [], []
            stamps, order_basis = capture_stamps(record.sources)
            director_prompt = prompt + (f'\n导演风格：{style}' if style else '')
            with tempfile.TemporaryDirectory(prefix='figstudio-ai-') as scratch:
                for index, source in enumerate(record.sources):
                    self._progress(record, 5 + int(index / len(record.sources) * 70),
                                   f'分析素材 {index + 1}/{len(record.sources)}')
                    summary = {}
                    if record.public['mode'] == 'cloud':
                        segments = analyze_video(self.ffmpeg, self.config, str(source.path), source.duration,
                                                 scratch, director_prompt, checkpoint=checkpoint, has_audio=source.has_audio,
                                                 report=summary)
                    else:
                        segments = self.local_analyzer(self.ffmpeg, source, checkpoint)
                    summaries.append(summary)
                    analyses.append({'meta': {'path': str(source.path), 'name': Path(source.name.replace('\\', '/')).name[:200],
                                             'duration': source.duration, 'has_audio': source.has_audio,
                                             'capture_order': stamps[index]}, 'segments': segments})
                self._progress(record, 80, '规划镜头顺序与时长')
                strategy = {}
                if record.public['mode'] == 'cloud':
                    sequence = plan_sequence(self.config, analyses, target, director_prompt, allow_fallback=False, report=strategy)
                else:
                    sequence = local_sequence(analyses, target, director_prompt)
                checkpoint()
                if opening == 'chronological':
                    sequence = chronological_sequence(sequence, analyses)
                notes = _dedupe_captions(sequence)
                base_plan = build_edit_plan(sequence, analyses, target, director_prompt, record.public['mode'])
                for decision, beat in zip(base_plan['decisions'], sequence):
                    decision['chapter'] = str(beat.get('chapter') or '')[:120]
                    decision['stage'] = str(beat.get('stage') or '')[:30]
                report = base_plan['validation']
                if not report['ok'] or not math.isfinite(report['duration']) or report['duration'] > target + .05:
                    raise WorkflowError('invalid_plan', '没有生成可应用的剪辑方案，请调整素材或目标时长。', 422)
                self._check_sources(record)
                context = {'summaries': summaries, 'strategy': strategy, 'order_basis': order_basis, 'opening': opening,
                           'style': style, 'notes': notes, 'stamps': stamps}
                plan = self._treat(base_plan, 'smart', style)
                result = self._describe(record, plan, context, 'smart')
                with self._lock:
                    checkpoint()
                    record.plan, record.base_plan, record.context, record.preset = plan, base_plan, context, 'smart'
                    record.expires_at = time.monotonic() + self.ttl
                    record.public.update(status='ready', progress=100, message='方案已生成，等待确认应用', result=result)
        except AnalysisCancelled:
            with self._lock:
                record.public.update(status='cancelled', message='已取消，工程未改变', result=None)
        except Exception as exc:
            with self._lock:
                if not record.cancelled.is_set():
                    safe = isinstance(exc, (AIRequestError, WorkflowError))
                    record.public.update(status='failed', message='分析失败，工程未改变', result=None,
                                         error={'code': exc.code if safe else 'analysis_failed',
                                                'message': str(exc) if safe else '分析失败，请检查素材后重试。',
                                                'retryable': bool(getattr(exc, 'retryable', False))})
        finally:
            record.finished.set()
            self._slots.release()

    @staticmethod
    def _treat(base_plan: dict, preset: str, style: str) -> dict:
        """Desktop-equivalent full treatment: opening preset masks/transitions, then the whole-film effect and sound map."""
        return apply_global_creative_treatment(apply_opening_treatment(copy.deepcopy(base_plan), preset, style), style, 'balanced')

    def _describe(self, record: _Record, plan: dict, context: dict, preset: str) -> dict:
        """Public result for a treated plan. Explicit allowlist: internal filesystem paths never leave the server."""
        report = plan.get('validation') or {}
        shots = []
        for decision in plan['decisions']:
            source = record.sources[decision['source_index']]
            start, end = decision['start'], decision['end']
            if not all(math.isfinite(x) for x in (start, end)) or not 0 <= start < end <= source.duration + .001:
                raise WorkflowError('invalid_plan', 'AI 方案超出素材范围，请重新生成。', 422)
            decision['caption'] = decision['caption'][:self.caption_limit]
            decision['reason'] = decision['reason'][:400]
            shots.append({'id': decision['decision_id'], 'media_id': source.id,
                          'name': Path(source.name.replace('\\', '/')).name[:200],
                          'start': start, 'end': end, 'role': decision['role'],
                          'caption': decision['caption'], 'reason': decision['reason'],
                          'transition': decision['transition'], 'has_audio': source.has_audio,
                          'chapter': str(decision.get('chapter') or '')[:120], 'stage': str(decision.get('stage') or '')[:30],
                          'mask': str(decision.get('mask_shape') or 'none'), 'motion_effect': str(decision.get('motion_effect') or 'none'),
                          'caption_effect': str(decision.get('caption_effect') or 'clean'),
                          'purpose': str(decision.get('creative_purpose') or '')[:200], 'title': str(decision.get('title_text') or '')[:60],
                          'capture_stamp': context['stamps'][decision['source_index']]})
        creative = plan.get('creative_direction') or {}
        direction = plan.get('global_creative_direction') or {}
        music = music_by_id(str(direction.get('music_id') or ''))
        overlays, cues = plan.get('overlay_tracks') or [], plan.get('sound_cues') or []
        keep_music = bool(record.snapshot.project.bgm)
        extras = [f"高级开篇「{creative.get('name', '')}」：前 {len(creative.get('shots') or [])} 个镜头写入蒙版、位置、羽化和转场，{len(overlays)} 个叠加层，{len(creative.get('sounds') or [])} 个开篇音效",
                  f"全片创意编排：{int(direction.get('accent_count', 0))} 个重点事件用动效与字幕强调，最小间隔 {float(direction.get('minimum_accent_spacing', 0)):.1f} 秒，共 {len(cues)} 个同步音效"
                  + (f"，自动配乐「{music['name']}」" if music and not keep_music else '，保留已有背景音乐' if keep_music else '')]
        report_payload = _build_report(record, plan, shots, context['summaries'], context['strategy'], context['order_basis'],
                                       context['opening'], context['style'], context['notes'], extras)
        return {'shots': shots, 'duration': report.get('duration', 0),
                'summary': f"共 {len(shots)} 个镜头，预计 {float(report.get('duration', 0)):.1f} 秒",
                'validation': {'ok': bool(report.get('ok')), 'blockers': list(report.get('blockers') or []),
                               'warnings': list(report.get('warnings') or []),
                               'repairs': list(report.get('repairs') or []) + list(context['notes']),
                               'duration': report.get('duration', 0), 'chronology_ratio': float(report.get('chronology_ratio', 1))},
                'changes': {'replace_video_clips': len(record.snapshot.project.clips),
                            'remove_overlays': len(record.snapshot.project.overlays),
                            'remove_sound_effects': len(record.snapshot.project.sfx),
                            'add_overlays': len(overlays), 'add_sound_effects': len(cues),
                            'preserve_background_music': keep_music,
                            'music': '' if keep_music or not music else music['name']},
                'warnings': list(report.get('warnings') or []), 'repairs': list(report.get('repairs') or []) + list(context['notes']),
                'capture_order_locked': plan['capture_order_locked'],
                'creative': {'preset_id': str(creative.get('preset_id') or ''), 'requested': preset,
                             'name': str(creative.get('name') or ''), 'summary': str(creative.get('summary') or ''),
                             'duration_hint': float(creative.get('duration_hint', 0) or 0),
                             'shot_count': len(creative.get('shots') or []), 'overlay_count': len(overlays),
                             'sound_count': len(creative.get('sounds') or [])},
                'opening_presets': [{'value': value, 'name': name} for name, value in opening_preset_choices()],
                'global_direction': {'accent_count': int(direction.get('accent_count', 0)),
                                     'minimum_accent_spacing': float(direction.get('minimum_accent_spacing', 0)),
                                     'music_id': str(direction.get('music_id') or ''), 'music_name': music['name'] if music else '',
                                     'rule': str(direction.get('rule') or '')},
                'report': report_payload}

    def set_opening(self, project_id: str, plan_id: str, owner_id: str, *, preset: str) -> dict:
        """Switch the opening preset of a ready plan (desktop parity); the base plan and its order never change."""
        if preset not in {value for _, value in opening_preset_choices()}:
            raise WorkflowError('invalid_preset', '未知的开篇方案。', 422)
        with self._lock:
            record = self._owned(project_id, plan_id, owner_id)
            if record.public['status'] != 'ready' or record.base_plan is None:
                raise WorkflowError('invalid_state', '当前方案不能切换开篇。', 409)
            plan = self._treat(record.base_plan, preset, record.context.get('style', ''))
            result = self._describe(record, plan, record.context, preset)
            record.plan, record.preset = plan, preset
            record.public['result'] = result
            record.public['message'] = f"已切换开篇方案：{result['creative']['name']}"
            return copy.deepcopy(record.public)

    def apply(self, project_id: str, plan_id: str, owner_id: str, *, revision: int, confirm: bool) -> dict:
        _revision(revision)
        if confirm is not True:
            raise WorkflowError('confirmation_required', '请先预览方案并确认应用。', 422)
        with self._lock:
            record = self._owned(project_id, plan_id, owner_id)
            if record.public['status'] != 'ready' or record.plan is None:
                raise WorkflowError('invalid_state', '当前方案不能应用。', 409)
            if revision != record.snapshot.revision:
                raise RevisionConflict()
            self._check_sources(record)
            plan = copy.deepcopy(record.plan)
            if not (plan.get('validation') or {}).get('ok', True):
                raise WorkflowError('invalid_plan', '方案已被阻止，请切换开篇方案或重新生成。', 422)
            candidate = copy.deepcopy(record.snapshot.project)
            candidate.clips = _style_clips(plan_to_clips(plan, Clip), plan['decisions'])
            for clip, decision in zip(candidate.clips, plan['decisions']):
                clip.has_audio = record.sources[decision['source_index']].has_audio
                clip.caption = clip.caption[:self.caption_limit]
                clip.reason = clip.reason[:400]
            # Old auxiliary tracks would sit at unrelated positions; the plan brings its own overlays and cues.
            candidate.overlays = plan_to_overlays(plan, OverlayClip)
            candidate.sfx = _plan_sound_cues(plan)
            direction = plan.get('global_creative_direction') or {}
            music_id = str(direction.get('music_id') or '')
            music, music_path = music_by_id(music_id), resolve_music(ROOT, music_id)
            music_applied = ''
            if not candidate.bgm and music and Path(music_path).exists():
                candidate.bgm, candidate.bgm_id = music_path, music_id
                candidate.bgm_volume = float(direction.get('music_volume', music['volume']))
                candidate.bgm_ducking = bool(direction.get('music_ducking', True))
                candidate.bgm_fade_in = float(direction.get('music_fade_in', 1))
                candidate.bgm_fade_out = float(direction.get('music_fade_out', 2))
                music_applied = music['name']
            candidate.prompt = plan['prompt']
            candidate.edit_plan = plan
            candidate.edit_log.append({'type': 'apply_ai_plan', 'transaction_id': plan_id,
                                       'engine': record.public['mode'], 'clip_count': len(candidate.clips),
                                       'overlay_count': len(candidate.overlays), 'sfx_count': len(candidate.sfx),
                                       'opening': (plan.get('creative_direction') or {}).get('preset_id', ''),
                                       'music': music_applied})
            options = {'expected_token': record.snapshot.version_token} if record.snapshot.version_token is not None else {}
            saved = self.backend.commit_project(project_id, owner_id, candidate, revision, **options)
            record.applied_revision = saved.revision
            record.applied_token = saved.version_token
            record.public.update(status='applied', revision=saved.revision, message='方案已应用，可撤销')
            return copy.deepcopy(record.public)

    def undo(self, project_id: str, plan_id: str, owner_id: str, *, revision: int) -> dict:
        _revision(revision)
        with self._lock:
            record = self._owned(project_id, plan_id, owner_id)
            if record.public['status'] != 'applied':
                raise WorkflowError('invalid_state', '当前方案没有可撤销的应用记录。', 409)
            if revision != record.applied_revision:
                raise RevisionConflict()
            options = {'expected_token': record.applied_token} if record.applied_token is not None else {}
            saved = self.backend.commit_project(project_id, owner_id, copy.deepcopy(record.snapshot.project), revision, **options)
            record.public.update(status='undone', revision=saved.revision, message='已恢复应用前的工程')
            return copy.deepcopy(record.public)

    def close(self):
        with self._lock:
            self._closed = True
            for record in self._records.values():
                if not record.finished.is_set():
                    record.cancelled.set()
        self._executor.shutdown(wait=True)
