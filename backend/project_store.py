"""Project persistence: validation, atomic writes, optimistic revisions, id boundary.

Framework-free on purpose (standard library plus the root engine modules) so the
desktop application, the HTTP layer and the tests all share one implementation.
The dataclasses in ``video_editing_engine`` remain the single source of truth for
the project/clip structure; this module only adds the guarantees the store needs:

- every payload is validated field by field and canonicalised to schema version 5;
- a project is written with ``atomic_write_text`` and the previous version is kept
  as ``<id>.ljproject.bak``, so a failed save never damages the old file;
- every save carries the revision the client last read; a stale revision is
  rejected with ``RevisionConflict`` instead of overwriting someone else's work;
- revision, timestamps and a fingerprint of the body live in ``<id>.meta.json``;
  a file rewritten by another tool (the desktop app strips the envelope) is
  recognised by its changed fingerprint and counted as a newer revision;
- project ids are server generated and strictly checked, and every path is
  resolved inside the workspace, so no request can reach files outside it.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import logging
import math
import os
import re
import shutil
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from video_editing_engine import Clip, OverlayClip, Project, SFXCue, atomic_write_text
from edit_plan import ALLOWED_MASKS, ALLOWED_TRANSITIONS

log = logging.getLogger(__name__)

SCHEMA_VERSION = 5
PROJECT_SUFFIX = ".ljproject"
BACKUP_SUFFIX = ".ljproject.bak"
META_SUFFIX = ".meta.json"
MAX_MAGNITUDE = 1e15  # any numeric project field beyond this is nonsense and would not survive float formatting
FILL_SEGMENT_KEYS = {"path", "start", "duration", "name"}
ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")
RATIO_PATTERN = re.compile(r"^\d+:\d+$")
TITLE_MAX_CHARS = 120
CAPTION_MAX_CHARS = 120  # same limit as edit_plan.apply_controlled_tool
DEFAULT_TITLE = "未命名作品"
DEFAULT_RATIO = "9:16"

# Values the desktop UI and the renderer understand (see video_editor_app / build_render_command).
ALLOWED_POSITIONS = {"top", "center", "lower_third", "bottom"}
ALLOWED_CAPTION_EFFECTS = {"clean", "jelly", "kinetic", "typewriter", "stamp", "pop", "highlight", "minimal"}
ALLOWED_MOTION_EFFECTS = {"none", "slow_push", "punch_in", "handheld"}
ALLOWED_TITLE_EFFECTS = {"", "bounce", "text_window"}
ALLOWED_PERSON_MODES = {"", "blur", "dim", "color"}
ALLOWED_OVERLAY_LAYOUTS = {"pip_right", "pip_left", "center", "full"}
ALLOWED_OVERLAY_MASKS = {"none", "ellipse", "circle"}

# Envelope keys the store manages itself; they are accepted on input and ignored.
ENVELOPE_KEYS = {"id", "revision", "created_at", "updated_at", "recovered_from_backup"}
PROJECT_KEYS = set(Project().to_dict().keys())
_TYPE_CHECKS = {"str": (str,), "float": (int, float), "int": (int,), "bool": (bool,), "list": (list,), "dict": (dict,)}


class ProjectStoreError(Exception):
    code = "project_store_error"
    status = 500

    def __init__(self, message: str, **extra):
        super().__init__(message)
        self.message = message
        self.extra = extra

    def to_detail(self) -> dict:
        return {"code": self.code, "message": self.message, **self.extra}


class InvalidProjectId(ProjectStoreError):
    code = "invalid_project_id"
    status = 400


class ProjectNotFound(ProjectStoreError):
    code = "project_not_found"
    status = 404


class InvalidProject(ProjectStoreError):
    """The payload failed validation; ``errors`` lists every problem found."""
    code = "invalid_project"
    status = 422

    def __init__(self, errors: list[dict]):
        self.errors = list(errors)
        first = self.errors[0] if self.errors else {"path": "", "message": "工程数据无效"}
        summary = f"{first['path']}: {first['message']}" if first.get("path") else first["message"]
        if len(self.errors) > 1:
            summary += f"（共 {len(self.errors)} 个问题）"
        super().__init__(summary, errors=self.errors)


class RevisionConflict(ProjectStoreError):
    """The client saved with a revision that is no longer current."""
    code = "revision_conflict"
    status = 409

    def __init__(self, expected: int, current: "ProjectRecord"):
        self.expected = expected
        self.current = current
        super().__init__(
            f"工程已被其他人修改：你基于 revision {expected}，服务器当前是 revision {current.revision}",
            expected=expected, current=current.to_dict(),
        )


class ProjectCorrupt(ProjectStoreError):
    code = "project_corrupt"
    status = 500


@dataclass
class ProjectRecord:
    id: str
    revision: int
    created_at: str
    updated_at: str
    project: dict
    recovered_from_backup: bool = False

    def to_dict(self) -> dict:
        return {"id": self.id, "revision": self.revision, "created_at": self.created_at,
                "updated_at": self.updated_at, "recovered_from_backup": self.recovered_from_backup,
                "project": self.project}

    def to_file_dict(self) -> dict:
        # Envelope first, then the version-5 body the desktop application understands.
        return {"id": self.id, "revision": self.revision, "created_at": self.created_at,
                "updated_at": self.updated_at, **self.project}

    def summary(self) -> dict:
        clips = self.project.get("clips") or []
        overlays = self.project.get("overlays") or []
        duration = round(max(sum(float(c["end"]) - float(c["start"]) for c in clips) if clips else 0,
                            max((float(o["timeline_start"]) + float(o["end"]) - float(o["start"]) for o in overlays), default=0)), 3)
        return {"id": self.id, "title": self.project.get("title", ""), "revision": self.revision,
                "updated_at": self.updated_at, "clip_count": len(clips), "duration": duration,
                "recovered_from_backup": self.recovered_from_backup}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _mtime_iso(path: Path) -> str:
    try:
        stamp = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
    except OSError:
        return _now()
    return stamp.isoformat(timespec="seconds").replace("+00:00", "Z")


def _fingerprint(project: dict) -> str:
    return hashlib.sha1(json.dumps(project, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _is_number(value) -> bool:
    """Finite, sane-magnitude int/float; NaN and infinities parse from JSON but cannot be written back as strict JSON."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    if isinstance(value, float) and not math.isfinite(value):
        return False
    return abs(value) <= MAX_MAGNITUDE


def _check_finite(value, path: str, errors: list[dict]) -> None:
    """Free-form structures (edit_plan, edit_log) must stay strict JSON: no NaN/Infinity anywhere inside."""
    if isinstance(value, bool):
        return
    if isinstance(value, (int, float)):
        if not _is_number(value):
            errors.append({"path": path, "message": "必须是有限数字"})
    elif isinstance(value, dict):
        for key, item in value.items():
            _check_finite(item, f"{path}.{key}" if path else str(key), errors)
    elif isinstance(value, list):
        for i, item in enumerate(value):
            _check_finite(item, f"{path}[{i}]", errors)


def project_version_token(record: ProjectRecord) -> str:
    """Detect repeated external writes or recovery that can reuse a revision."""
    state = {'project': record.project, 'revision': record.revision,
             'recovered_from_backup': record.recovered_from_backup}
    return hashlib.sha256(json.dumps(state, ensure_ascii=False, sort_keys=True,
                                     allow_nan=False).encode('utf-8')).hexdigest()


class _Checker:
    """Collects field errors for one item so the caller can report all of them at once."""

    def __init__(self, prefix: str, data: dict, errors: list[dict]):
        self.prefix = prefix
        self.data = data
        self.errors = errors

    def fail(self, name: str, message: str) -> None:
        self.errors.append({"path": f"{self.prefix}.{name}" if self.prefix and name else (self.prefix or name), "message": message})

    def number(self, name: str, lo=None, hi=None, exclusive_lo=False) -> None:
        if name not in self.data:
            return
        value = self.data[name]
        if not _is_number(value):
            return self.fail(name, "必须是数字")
        if lo is not None and (value <= lo if exclusive_lo else value < lo):
            return self.fail(name, f"必须{'大于' if exclusive_lo else '不小于'} {lo}")
        if hi is not None and value > hi:
            self.fail(name, f"必须不大于 {hi}")

    def choice(self, name: str, allowed: set) -> None:
        value = self.data.get(name)
        if name in self.data and isinstance(value, str) and value not in allowed:
            self.fail(name, f"不支持的值 {value!r}，允许：{', '.join(sorted(repr(x) for x in allowed))}")

    def text(self, name: str, max_chars: int | None = None, required: bool = False) -> None:
        if name not in self.data:
            if required:
                self.fail(name, "不能为空")
            return
        value = self.data[name]
        if not isinstance(value, str):
            return self.fail(name, "必须是字符串")
        if required and not value.strip():
            return self.fail(name, "不能为空")
        if "\x00" in value:
            self.fail(name, "包含非法字符")
        elif max_chars is not None and len(value) > max_chars:
            self.fail(name, f"最多 {max_chars} 个字符")


def _check_fields(prefix: str, data, cls, errors: list[dict], required: set[str]) -> bool:
    """Generic key/type checks driven by the dataclass definition. Returns True if the item is usable."""
    if not isinstance(data, dict):
        errors.append({"path": prefix, "message": "必须是 JSON 对象"})
        return False
    fields = {f.name: f for f in dataclasses.fields(cls)}
    unknown = sorted(set(data) - set(fields))
    if unknown:
        errors.append({"path": prefix, "message": f"未知字段 {', '.join(unknown)}；允许的字段：{', '.join(fields)}"})
    # Unknown keys are reported but do not stop the semantic checks; missing or mistyped fields do.
    ok = True
    for name in sorted(required - set(data)):
        errors.append({"path": f"{prefix}.{name}", "message": "缺少必填字段"})
        ok = False
    for name, value in data.items():
        if name not in fields:
            continue
        expected = _TYPE_CHECKS.get(str(fields[name].type))
        if expected is None:
            continue
        numeric = expected in ((int, float), (int,))
        if not isinstance(value, expected) or (numeric and isinstance(value, bool)):
            errors.append({"path": f"{prefix}.{name}", "message": f"类型应为 {fields[name].type}"})
            ok = False
        elif numeric and not _is_number(value):
            errors.append({"path": f"{prefix}.{name}", "message": "必须是有限数字"})
            ok = False
    return ok


def _check_fill_segment(prefix: str, segment, errors: list[dict]) -> None:
    """title_fill_segments entries go through float() in build_render_command; keep them numeric here."""
    if not isinstance(segment, dict):
        errors.append({"path": prefix, "message": "必须是 JSON 对象"})
        return
    unknown = sorted(set(segment) - FILL_SEGMENT_KEYS)
    if unknown:
        errors.append({"path": prefix, "message": f"未知字段 {', '.join(unknown)}；允许的字段：{', '.join(sorted(FILL_SEGMENT_KEYS))}"})
    s = _Checker(prefix, segment, errors)
    s.text("path", required=True)
    s.text("name", 200)
    s.number("start", 0)
    s.number("duration", 0, exclusive_lo=True)


def _check_clip(prefix: str, data: dict, errors: list[dict]) -> None:
    c = _Checker(prefix, data, errors)
    c.text("path", required=True)
    c.text("name", 200)
    c.text("caption", CAPTION_MAX_CHARS)
    c.text("title_text", CAPTION_MAX_CHARS)
    c.number("start", 0)
    c.number("end", 0)
    if _is_number(data.get("start")) and _is_number(data.get("end")) and data["end"] <= data["start"]:
        c.fail("end", "出点必须大于入点")
    c.number("volume", 0, 2)
    c.number("caption_size", 1, 400)
    c.number("caption_bg_opacity", 0, 1)
    c.number("transition_duration", 0.05, 2)
    for name in ("mask_x", "mask_y", "mask_opacity"):
        c.number(name, 0, 1)
    for name in ("mask_width", "mask_height"):
        c.number(name, 0, 1, exclusive_lo=True)
    c.number("mask_feather", 0)
    c.number("person_effect_start", 0)
    c.number("person_effect_end", 0)
    c.choice("position", ALLOWED_POSITIONS)
    c.choice("transition", ALLOWED_TRANSITIONS)
    c.choice("mask_shape", ALLOWED_MASKS)
    c.choice("caption_effect", ALLOWED_CAPTION_EFFECTS)
    c.choice("motion_effect", ALLOWED_MOTION_EFFECTS)
    c.choice("title_effect", ALLOWED_TITLE_EFFECTS)
    c.choice("person_effect_mode", ALLOWED_PERSON_MODES)
    for i, segment in enumerate(data.get("title_fill_segments") or []):
        _check_fill_segment(f"{prefix}.title_fill_segments[{i}]", segment, errors)


def _check_overlay(prefix: str, data: dict, errors: list[dict]) -> None:
    c = _Checker(prefix, data, errors)
    c.text("path", required=True)
    c.text("name", 200)
    c.number("start", 0)
    c.number("end", 0)
    if _is_number(data.get("start")) and _is_number(data.get("end")) and data["end"] <= data["start"]:
        c.fail("end", "出点必须大于入点")
    c.number("timeline_start", 0)
    c.number("track", 2, 8)
    for name in ("x", "y", "opacity"):
        c.number(name, 0, 1)
    for name in ("width", "height"):
        c.number(name, 0, 1, exclusive_lo=True)
    c.number("feather", 0)
    c.choice("layout", ALLOWED_OVERLAY_LAYOUTS)
    c.choice("mask_shape", ALLOWED_OVERLAY_MASKS)


def _check_sfx(prefix: str, data: dict, errors: list[dict]) -> None:
    c = _Checker(prefix, data, errors)
    c.text("path", required=True)
    c.text("name", 200)
    c.text("effect_id", 100)
    c.number("start", 0)
    c.number("volume", 0, 2)


_ITEM_RULES = {
    "clips": (Clip, {"path", "start", "end"}, _check_clip),
    "overlays": (OverlayClip, {"path", "start", "end", "timeline_start"}, _check_overlay),
    "sfx": (SFXCue, {"path", "start"}, _check_sfx),
}


def validate_project_payload(data) -> dict:
    """Validate a project dict and return its canonical version-5 form.

    Raises ``InvalidProject`` with every problem found (path + message) so a client
    can fix them in one round trip. Envelope keys (id, revision, timestamps) are
    ignored: the store owns them.
    """
    if not isinstance(data, dict):
        raise InvalidProject([{"path": "", "message": "工程必须是 JSON 对象"}])
    errors: list[dict] = []
    body = {k: v for k, v in data.items() if k not in ENVELOPE_KEYS}
    unknown = sorted(set(body) - PROJECT_KEYS)
    if unknown:
        errors.append({"path": "", "message": f"未知字段 {', '.join(unknown)}；允许的字段：{', '.join(sorted(PROJECT_KEYS))}"})
    version = body.get("version", SCHEMA_VERSION)
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        errors.append({"path": "version", "message": "version 必须是正整数"})
    elif version > SCHEMA_VERSION:
        errors.append({"path": "version", "message": f"不支持的工程版本 {version}，当前最高支持 {SCHEMA_VERSION}"})
    top = _Checker("", body, errors)
    top.text("title", TITLE_MAX_CHARS)
    top.text("bgm", 4096)
    top.text("bgm_id", 100)
    top.text("ratio", 20)
    top.text("prompt", 10000)
    if isinstance(body.get("ratio"), str) and not RATIO_PATTERN.match(body["ratio"]):
        top.fail("ratio", "画幅比例格式应为 宽:高，例如 9:16")
    top.number("bgm_volume", 0, 2)
    top.number("bgm_fade_in", 0, 60)
    top.number("bgm_fade_out", 0, 60)
    if "bgm_ducking" in body and not isinstance(body["bgm_ducking"], bool):
        top.fail("bgm_ducking", "必须是布尔值")
    if "edit_plan" in body and not isinstance(body["edit_plan"], dict):
        top.fail("edit_plan", "必须是 JSON 对象")
    else:
        _check_finite(body.get("edit_plan", {}), "edit_plan", errors)
    if "edit_log" in body and not isinstance(body["edit_log"], list):
        top.fail("edit_log", "必须是列表")
    else:
        _check_finite(body.get("edit_log", []), "edit_log", errors)
    for key, (cls, required, check) in _ITEM_RULES.items():
        items = body.get(key, [])
        if not isinstance(items, list):
            top.fail(key, "必须是列表")
            continue
        seen: dict[str, int] = {}
        for i, item in enumerate(items):
            prefix = f"{key}[{i}]"
            if not _check_fields(prefix, item, cls, errors, required):
                continue
            check(prefix, item, errors)
            item_id = item.get("id")
            if isinstance(item_id, str) and item_id:
                if item_id in seen:
                    errors.append({"path": f"{prefix}.id", "message": f"与 {key}[{seen[item_id]}] 的 id 重复"})
                seen[item_id] = i
    if errors:
        raise InvalidProject(errors)
    canonical = dict(body)
    canonical["version"] = SCHEMA_VERSION
    for key in _ITEM_RULES:
        # Blank ids get a fresh uuid, matching what the dataclass default would do.
        canonical[key] = [{**item, "id": item["id"] if item.get("id") else str(uuid.uuid4())} for item in canonical.get(key, [])]
    try:
        project = Project.from_dict(canonical)
        for key in _ITEM_RULES:
            for i, item in enumerate(getattr(project, key)):
                try:
                    item.validate()
                except ValueError as exc:
                    errors.append({"path": f"{key}[{i}]", "message": str(exc)})
    except (TypeError, ValueError) as exc:
        errors.append({"path": "", "message": f"工程数据无法解析：{exc}"})
    if errors:
        raise InvalidProject(errors)
    canonical = project.to_dict()
    try:
        json.dumps(canonical, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise InvalidProject([{"path": "", "message": f"工程包含无法写成 JSON 的内容：{exc}"}])
    return canonical


class ProjectStore:
    """File-backed project repository: ``<workspace>/projects/<id>.ljproject`` (+ ``.bak`` and ``.meta.json``)."""

    def __init__(self, workspace: str | os.PathLike):
        self.workspace = Path(workspace).resolve()
        (self.workspace / "projects").mkdir(parents=True, exist_ok=True)
        self.projects_dir = (self.workspace / "projects").resolve()
        self._locks: dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()

    @classmethod
    def from_env(cls, default: str | os.PathLike = "workspace") -> "ProjectStore":
        return cls(os.environ.get("LINGJIAN_WORKSPACE") or default)

    # ---- boundary ----------------------------------------------------------------
    def _check_id(self, project_id) -> str:
        if not isinstance(project_id, str) or not ID_PATTERN.match(project_id):
            raise InvalidProjectId("工程 ID 必须是 32 位小写十六进制字符串", project_id=str(project_id)[:64])
        return project_id

    def _path(self, project_id: str, suffix: str = PROJECT_SUFFIX) -> Path:
        path = (self.projects_dir / f"{project_id}{suffix}").resolve()
        if path.parent != self.projects_dir:
            # Defence in depth: the id regex already makes this unreachable.
            raise InvalidProjectId("工程路径越界", project_id=project_id)
        return path

    def _lock(self, project_id: str) -> threading.Lock:
        with self._locks_guard:
            return self._locks.setdefault(project_id, threading.Lock())

    # ---- file io ---------------------------------------------------------------------
    def _load_body(self, path: Path, project_id: str) -> tuple[dict, dict]:
        """Parse and validate one project file; returns (raw file dict, canonical project)."""
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ProjectCorrupt(f"工程文件不是合法 JSON：{exc.msg}", project_id=project_id)
        if not isinstance(raw, dict):
            raise ProjectCorrupt("工程文件不是 JSON 对象", project_id=project_id)
        try:
            return raw, validate_project_payload(raw)
        except InvalidProject as exc:
            raise ProjectCorrupt("工程文件内容无效", project_id=project_id, errors=exc.errors)

    def _read_meta(self, project_id: str) -> dict | None:
        path = self._path(project_id, META_SUFFIX)
        if not path.exists():
            return None
        try:
            meta = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            log.warning("ignoring unreadable metadata for %s: %s", project_id, exc)
            return None
        revision = meta.get("revision") if isinstance(meta, dict) else None
        if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1 or not isinstance(meta.get("fingerprint"), str):
            log.warning("ignoring malformed metadata for %s", project_id)
            return None
        return meta

    def _record(self, project_id: str, raw: dict, project: dict, meta: dict | None, path: Path, recovered: bool) -> ProjectRecord:
        if meta is not None:
            created = meta.get("created_at") if isinstance(meta.get("created_at"), str) else _mtime_iso(path)
            if meta["fingerprint"] == _fingerprint(project):
                updated = meta.get("updated_at") if isinstance(meta.get("updated_at"), str) else created
                return ProjectRecord(project_id, meta["revision"], created, updated, project, recovered)
            # The body differs from the store's last write (desktop save, hand edit, backup recovery, or a crash
            # between the two writes): count it as a newer revision so clients holding the old one conflict
            # instead of silently winning. The envelope revision covers the crash case where it ran ahead.
            envelope = raw.get("revision")
            envelope = envelope if isinstance(envelope, int) and not isinstance(envelope, bool) else 0
            return ProjectRecord(project_id, max(meta["revision"] + 1, envelope), created, _mtime_iso(path), project, recovered)
        # No metadata: a legacy or foreign file; trust its envelope if it has one.
        revision = raw.get("revision")
        if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
            revision = 1
        created = raw.get("created_at") if isinstance(raw.get("created_at"), str) else _mtime_iso(path)
        updated = raw.get("updated_at") if isinstance(raw.get("updated_at"), str) else created
        return ProjectRecord(project_id, revision, created, updated, project, recovered)

    def _read(self, project_id: str) -> ProjectRecord:
        path = self._path(project_id)
        if not path.exists():
            raise ProjectNotFound("工程不存在", project_id=project_id)
        meta = self._read_meta(project_id)
        try:
            raw, project = self._load_body(path, project_id)
        except (ProjectCorrupt, OSError, UnicodeDecodeError) as exc:
            backup = self._path(project_id, BACKUP_SUFFIX)
            if not backup.exists():
                raise exc if isinstance(exc, ProjectCorrupt) else ProjectCorrupt(f"工程文件无法读取：{exc}", project_id=project_id)
            log.warning("project %s is damaged (%s); serving backup", project_id, exc)
            raw, project = self._load_body(backup, project_id)
            return self._record(project_id, raw, project, meta, backup, True)
        return self._record(project_id, raw, project, meta, path, False)

    def _write(self, record: ProjectRecord, keep_backup: bool) -> None:
        path = self._path(record.id)
        if keep_backup and path.exists():
            shutil.copy2(path, self._path(record.id, BACKUP_SUFFIX))
        atomic_write_text(path, json.dumps(record.to_file_dict(), ensure_ascii=False, indent=2, allow_nan=False))
        # Concurrency metadata lives beside the project so a tool that rewrites the body cannot reset it.
        meta = {"id": record.id, "revision": record.revision, "created_at": record.created_at,
                "updated_at": record.updated_at, "fingerprint": _fingerprint(record.project)}
        atomic_write_text(self._path(record.id, META_SUFFIX), json.dumps(meta, ensure_ascii=False, indent=2))

    # ---- public api ------------------------------------------------------------------
    def create(self, title: str | None = None, ratio: str | None = None, project: dict | None = None) -> ProjectRecord:
        if project is None:
            payload = {"title": DEFAULT_TITLE if title is None else title, "ratio": DEFAULT_RATIO if ratio is None else ratio}
        elif isinstance(project, dict):
            payload = dict(project)
            if title is not None:
                payload["title"] = title
            if ratio is not None:
                payload["ratio"] = ratio
        else:
            payload = project  # validate_project_payload reports the type problem
        clean = validate_project_payload(payload)
        project_id = uuid.uuid4().hex
        while self._path(project_id).exists():
            project_id = uuid.uuid4().hex
        now = _now()
        record = ProjectRecord(project_id, 1, now, now, clean)
        with self._lock(project_id):
            self._write(record, keep_backup=False)
        return record

    def get(self, project_id: str) -> ProjectRecord:
        return self._read(self._check_id(project_id))

    def list(self) -> list[dict]:
        summaries = []
        for path in self.projects_dir.glob(f"*{PROJECT_SUFFIX}"):
            project_id = path.name[: -len(PROJECT_SUFFIX)]
            if not ID_PATTERN.match(project_id):
                continue
            try:
                summaries.append(self._read(project_id).summary())
            except ProjectStoreError as exc:
                log.warning("skipping project %s: %s", project_id, exc)
        summaries.sort(key=lambda x: x["updated_at"], reverse=True)
        return summaries

    def save(self, project_id: str, project: dict, expected_revision: int, *,
             expected_token: str | None = None) -> ProjectRecord:
        project_id = self._check_id(project_id)
        if not isinstance(expected_revision, int) or isinstance(expected_revision, bool) or expected_revision < 1:
            raise InvalidProject([{"path": "revision", "message": "revision 必须是正整数（上次读取到的版本号）"}])
        clean = validate_project_payload(project)
        with self._lock(project_id):
            current = self._read(project_id)
            if current.revision != expected_revision or (expected_token is not None and project_version_token(current) != expected_token):
                raise RevisionConflict(expected_revision, current)
            record = ProjectRecord(project_id, current.revision + 1, current.created_at, _now(), clean)
            # A damaged main file must not overwrite the good backup we just served.
            self._write(record, keep_backup=not current.recovered_from_backup)
        return record

    def delete(self, project_id: str) -> None:
        project_id = self._check_id(project_id)
        with self._lock(project_id):
            path = self._path(project_id)
            if not path.exists():
                raise ProjectNotFound("工程不存在", project_id=project_id)
            path.unlink()
            for suffix in (BACKUP_SUFFIX, META_SUFFIX):
                extra = self._path(project_id, suffix)
                if extra.exists():
                    extra.unlink()
