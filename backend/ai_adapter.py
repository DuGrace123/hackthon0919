"""Connect Member 4's AI workflow to Member 1's local ProjectStore.

Until Member 2 supplies an upload catalog, sources are the unique video paths
referenced by project clips/overlays inside workspace/media. Never open a path
outside that root, even when an imported project contains an absolute path.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import threading
from pathlib import Path

from ai_workflow import MediaSource, ProjectSnapshot, RevisionConflict, WorkflowError
from backend.project_store import (
    ProjectStore, ProjectStoreError, RevisionConflict as StoreConflict, project_version_token,
)
from video_editing_engine import Project, VIDEO_EXT, probe_media


LOCAL_OWNER = 'local-workspace'


def resolve_ffmpeg(explicit: str | None = None) -> str:
    candidate = explicit if explicit is not None else os.environ.get('LINGJIAN_FFMPEG')
    if candidate is not None:
        return shutil.which(candidate) or ''
    if os.name == 'nt':
        bundled = Path(__file__).resolve().parents[1] / 'ffmpeg.exe'
        if bundled.is_file():
            return str(bundled)
    found = shutil.which('ffmpeg')
    if found:
        return found
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except (ImportError, RuntimeError):
        return ''


class ProjectStoreAIBackend:
    def __init__(self, store: ProjectStore, ffmpeg: str):
        self.store, self.ffmpeg = store, ffmpeg
        self.media_dir = store.workspace / 'media'
        self.media_dir.mkdir(parents=True, exist_ok=True)
        self.media_dir = self.media_dir.resolve()
        self._cache: dict[tuple, dict] = {}
        self._cache_lock = threading.Lock()

    def _record(self, project_id: str, owner_id: str):
        if owner_id != LOCAL_OWNER:
            raise WorkflowError('not_found', '工程不可用。', 404)
        try:
            return self.store.get(project_id)
        except ProjectStoreError as exc:
            raise WorkflowError(exc.code, '工程不可用，请刷新后重试。', exc.status) from None

    def get_project(self, project_id: str, owner_id: str) -> ProjectSnapshot:
        record = self._record(project_id, owner_id)
        return ProjectSnapshot(Project.from_dict(record.project), record.revision, project_version_token(record))

    def _candidates(self, project: dict):
        unique: dict[str, tuple[Path, str]] = {}
        unavailable = []
        for clip in project.get('clips', []) + project.get('overlays', []):
            try:
                raw = Path(clip['path'])
                path = (raw if raw.is_absolute() else self.store.workspace / raw).resolve(strict=True)
                relative = path.relative_to(self.media_dir)
                if not path.is_file() or path.suffix.lower() not in VIDEO_EXT:
                    raise ValueError('Not a supported video')
                media_id = hashlib.sha256(relative.as_posix().encode('utf-8')).hexdigest()[:32]
                name = Path((clip.get('name') or path.name).replace('\\', '/')).name[:200]
                unique.setdefault(media_id, (path, name))
            except (OSError, ValueError):
                unavailable.append({'clip_id': clip.get('id', ''),
                                    'message': '素材需存在于 workspace/media 中，且为受支持的视频格式。'})
        return unique, unavailable

    def _source(self, media_id: str, path: Path, name: str) -> MediaSource:
        if not self.ffmpeg:
            raise WorkflowError('ffmpeg_unavailable', '未找到 FFmpeg，请在服务端安装或设置 LINGJIAN_FFMPEG。', 503)
        try:
            stat = path.stat()
            key = (str(path), stat.st_size, stat.st_mtime_ns)
            with self._cache_lock:
                meta = self._cache.get(key)
            if meta is None:
                meta = probe_media(self.ffmpeg, str(path), timeout=15)
                if not meta['width'] or not meta['height']:
                    raise ValueError('Not a video stream')
                with self._cache_lock:
                    if len(self._cache) >= 256:
                        self._cache.clear()
                    self._cache[key] = meta
            return MediaSource(media_id, path, name, meta['duration'], meta['has_audio'], meta['capture_order'])
        except (OSError, ValueError, subprocess.TimeoutExpired):
            raise WorkflowError('media_unavailable', '素材无法读取或探测超时，请检查后重新导入。', 422) from None

    def list_sources(self, project_id: str, owner_id: str) -> dict:
        record = self._record(project_id, owner_id)
        candidates, unavailable = self._candidates(record.project)
        items = []
        for media_id, (path, name) in candidates.items():
            try:
                source = self._source(media_id, path, name)
                items.append({'id': source.id, 'name': source.name, 'duration': source.duration,
                              'has_audio': source.has_audio})
            except WorkflowError as exc:
                if exc.status == 503:
                    raise
                unavailable.append({'media_id': media_id, 'message': str(exc)})
        return {'items': items, 'unavailable': unavailable, 'revision': record.revision}

    def resolve_media(self, project_id: str, media_id: str, owner_id: str) -> MediaSource:
        record = self._record(project_id, owner_id)
        candidates, _ = self._candidates(record.project)
        if media_id not in candidates:
            raise WorkflowError('not_found', '当前工程没有可访问的该素材。', 404)
        return self._source(media_id, *candidates[media_id])

    def commit_project(self, project_id: str, owner_id: str, project: Project,
                       expected_revision: int, *, expected_token: str | None = None) -> ProjectSnapshot:
        self._record(project_id, owner_id)
        try:
            saved = self.store.save(project_id, project.to_dict(), expected_revision, expected_token=expected_token)
        except StoreConflict:
            raise RevisionConflict() from None
        except ProjectStoreError as exc:
            raise WorkflowError(exc.code, '工程保存失败，请检查数据后重试。', exc.status) from None
        except OSError:
            raise WorkflowError('save_failed', '工程未保存成功，请检查磁盘空间后重试。', 503) from None
        return ProjectSnapshot(Project.from_dict(saved.project), saved.revision, project_version_token(saved))
