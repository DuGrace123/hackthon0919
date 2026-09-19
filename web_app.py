from __future__ import annotations

import atexit
import copy
import dataclasses
import struct
import tempfile
import wave
import hmac
import json
import os
import re
import secrets
import shutil
import subprocess
import threading
import uuid
from dataclasses import asdict
from datetime import timedelta
from functools import wraps
from pathlib import Path

from flask import Flask, g, jsonify, redirect, render_template, request, send_from_directory, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from ai_story_planner import AIRequestError, APIConfig, list_models, protect_secret, transcribe_audio, unprotect_secret
from builtin_music import music_by_id
from ai_workflow import (
    AIWorkflow,
    MediaSource,
    ProjectSnapshot,
    RevisionConflict,
    WorkflowError,
    config_from_environment,
    validate_cloud_config,
)
from edit_plan import ALLOWED_TRANSITIONS
from video_editing_engine import (
    AUDIO_EXT,
    VIDEO_EXT,
    Clip,
    Project,
    build_render_command,
    probe_media,
    validate_rendered_mp4,
)
from web_auth import AccountStore, utc_now, validate_password, validate_role, validate_username


ROOT = Path(__file__).resolve().parent
ALLOWED_EXTENSIONS = VIDEO_EXT | AUDIO_EXT
WEB_PROJECT_ID = "workspace"  # The web editor keeps one working project per workspace.
CAPTION_MAX_CHARS = 120
# Manual picks plus every transition an AI plan may assign, so AI clips stay editable.
WEB_TRANSITIONS = {"none", "fade", "dissolve", "wipeleft", "wiperight", "slideup", "slidedown"} | set(ALLOWED_TRANSITIONS)


def resolve_ffmpeg() -> str:
    """LINGJIAN_FFMPEG, then the bundled ffmpeg.exe (Windows only), PATH, then imageio-ffmpeg."""
    configured = os.environ.get("LINGJIAN_FFMPEG")
    if configured:
        return shutil.which(configured) or (configured if Path(configured).is_file() else "")
    if os.name == "nt":
        bundled = ROOT / "ffmpeg.exe"
        if bundled.is_file():
            return str(bundled)
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except (ImportError, RuntimeError):
        return ""


def _load_secret_key(workspace: Path) -> str:
    configured = os.environ.get("LINGJIAN_SECRET_KEY")
    if configured:
        return configured
    path = workspace / ".session_secret"
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    value = secrets.token_urlsafe(48)
    path.write_text(value, encoding="utf-8")
    return value


def _atomic_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def capture_stamp(value) -> str:
    """Normalize a probe capture_order (filename stamp or ISO creation time) to 14 comparable digits."""
    text = str(value or "").strip()
    if re.fullmatch(r"\d{14}", text):
        return text
    match = re.match(r"(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})", text)
    return "".join(match.groups()) if match else ""


def format_stamp(stamp: str) -> str:
    return f"{stamp[:4]}-{stamp[4:6]}-{stamp[6:8]} {stamp[8:10]}:{stamp[10:12]}:{stamp[12:14]}" if stamp else ""


def _load_ai_settings(path: Path) -> dict | None:
    """Admin-saved cloud settings; the key is stored with protect_secret (DPAPI on Windows)."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return None
        data["api_key"] = unprotect_secret(str(data.get("api_key") or ""))
        return data
    except FileNotFoundError:
        return None
    except Exception:
        return None


def _save_ai_settings(path: Path, data: dict) -> None:
    payload = {**data, "api_key": protect_secret(str(data.get("api_key") or ""))}
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    os.replace(temporary, path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def _default_cloud_tester(config: APIConfig) -> list[str] | None:
    return list_models(config, timeout=15)


def _default_transcription_tester(config: APIConfig) -> None:
    """Send half a second of silence to /v1/audio/transcriptions; proves the transcription model really works."""
    with tempfile.TemporaryDirectory(prefix="lingjian-probe-") as folder:
        path = Path(folder) / "probe.wav"
        with wave.open(str(path), "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(16000)
            handle.writeframes(struct.pack("<h", 0) * 8000)
        transcribe_audio(dataclasses.replace(config, timeout=min(config.timeout, 30)), str(path))


def _default_export_runner(ffmpeg: str, project: Project, output: Path) -> dict:
    width, height = {"9:16": (720, 1280), "16:9": (1280, 720), "1:1": (1080, 1080)}.get(
        project.ratio, (720, 1280)
    )
    command = build_render_command(ffmpeg, project, str(output), width, height, "standard")
    flags = 0x08000000 if os.name == "nt" else 0
    process = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=flags,
    )
    if process.returncode:
        raise RuntimeError((process.stderr or "FFmpeg export failed")[-1400:])
    return validate_rendered_mp4(ffmpeg, str(output))


def create_app(workspace: str | Path | None = None, probe_fn=None, export_runner=None, ai_analyzer=None,
               cloud_tester=None, transcription_tester=None) -> Flask:
    app = Flask(__name__, template_folder="web/templates", static_folder="web/static")
    production = os.environ.get("LINGJIAN_ENV", "development") == "production"
    setup_token = os.environ.get("LINGJIAN_SETUP_TOKEN", "")
    upload_limit_mb = int(os.environ.get("LINGJIAN_MAX_UPLOAD_MB", "2048"))
    if upload_limit_mb < 1:
        raise ValueError("LINGJIAN_MAX_UPLOAD_MB must be a positive integer")
    if production and len(os.environ.get("LINGJIAN_SECRET_KEY", "")) < 32:
        raise ValueError("Production requires LINGJIAN_SECRET_KEY with at least 32 characters")
    app.config["MAX_CONTENT_LENGTH"] = upload_limit_mb * 1024 * 1024

    workspace_path = Path(workspace or os.environ.get("LINGJIAN_WEB_WORKSPACE", ROOT / "web_workspace")).resolve()
    upload_path = workspace_path / "uploads"
    export_path = workspace_path / "exports"
    project_path = workspace_path / "project.ljproject"
    catalog_path = workspace_path / "media_catalog.json"
    ai_settings_path = workspace_path / "ai_settings.json"
    upload_path.mkdir(parents=True, exist_ok=True)
    export_path.mkdir(parents=True, exist_ok=True)
    app.secret_key = _load_secret_key(workspace_path)
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SECURE=production,
        SESSION_COOKIE_SAMESITE="Lax",
        PERMANENT_SESSION_LIFETIME=timedelta(hours=12),
    )
    accounts = AccountStore(workspace_path / "accounts.sqlite3")
    if production and accounts.count() == 0 and len(setup_token) < 32:
        raise ValueError("First production launch requires LINGJIAN_SETUP_TOKEN with at least 32 characters")

    ffmpeg = resolve_ffmpeg()

    def probe(ffmpeg_path, path):
        if probe_fn is not None:
            return probe_fn(ffmpeg_path, path)
        return probe_media(ffmpeg_path, path, require_video=Path(path).suffix.lower() not in AUDIO_EXT)

    run_export = export_runner or _default_export_runner
    lock = threading.RLock()
    jobs: dict[str, dict] = {}
    export_slot = threading.BoundedSemaphore(1)

    def csrf_token() -> str:
        token = session.get("csrf_token")
        if not token:
            token = secrets.token_urlsafe(32)
            session["csrf_token"] = token
        return token

    def current_account() -> dict | None:
        return getattr(g, "current_user", None)

    def require_admin(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = current_account()
            if not user or user["role"] != "admin":
                return jsonify(error="需要管理员权限"), 403
            return view(*args, **kwargs)

        return wrapped

    @app.before_request
    def authenticate_request():
        g.current_user = None
        user_id = session.get("user_id")
        if user_id:
            row = accounts.get(int(user_id))
            if row is not None and bool(row["is_active"]):
                g.current_user = accounts.public(row)
            else:
                session.clear()

        if request.path.startswith("/api/") and request.method in {"POST", "PATCH", "PUT", "DELETE"}:
            expected = session.get("csrf_token", "")
            supplied = request.headers.get("X-CSRF-Token", "")
            if not expected or not supplied or not hmac.compare_digest(expected, supplied):
                return jsonify(error="安全令牌无效，请刷新页面后重试"), 403

        public_endpoints = {"login_page", "guide_page", "guide_pdf", "auth_status", "auth_setup", "auth_login", "health", "static"}
        if request.endpoint in public_endpoints:
            return None
        if g.current_user is None:
            if request.path.startswith("/api/"):
                return jsonify(error="请先登录"), 401
            return redirect(url_for("login_page"))
        return None

    try:
        project = Project.load(project_path) if project_path.exists() else Project(title="网页剪辑工程")
    except Exception:
        project = Project(title="网页剪辑工程")
    try:
        catalog = json.loads(catalog_path.read_text(encoding="utf-8")) if catalog_path.exists() else {}
    except Exception:
        catalog = {}

    # Every content change increments the revision so AI plans can detect edits made
    # after they were generated (optimistic lock, mirrors the backend project store).
    revision = 1

    def bump_revision() -> None:
        nonlocal revision
        revision += 1

    def replace_project(candidate: Project) -> None:
        nonlocal project
        project = candidate
        bump_revision()

    def save_catalog() -> None:
        _atomic_json(catalog_path, catalog)

    def catalog_item(media_id: str) -> dict:
        item = catalog.get(media_id)
        if not item:
            raise ValueError("找不到该素材")
        return item

    def ensure_capture_order(item: dict) -> str:
        """Media uploaded before capture times were recorded gets probed once; result is cached in the catalog."""
        if "capture_order" not in item and (ffmpeg or probe_fn is not None):
            try:
                metadata = probe(ffmpeg, str(item["path"]))
                item["capture_order"] = str(metadata.get("capture_order") or "")
            except Exception:
                item["capture_order"] = ""
            save_catalog()
        return capture_stamp(item.get("capture_order"))

    def clip_json(clip: Clip) -> dict:
        data = asdict(clip)
        media = next((item for item in catalog.values() if item.get("path") == clip.path), None)
        data["media_id"] = media.get("id") if media else ""
        data["media_url"] = f"/media/{media['stored_name']}" if media else ""
        data["duration"] = clip.duration
        return data

    def state_json() -> dict:
        return {
            "project": {
                "title": project.title,
                "ratio": project.ratio,
                "duration": project.duration,
                "revision": revision,
                "clips": [clip_json(clip) for clip in project.clips],
                "overlay_count": len(project.overlays),
                "sfx_count": len(project.sfx),
                "bgm_name": ((music_by_id(project.bgm_id) or {}).get("name") if project.bgm_id else "") or (Path(project.bgm).name if project.bgm else ""),
            },
            "media": [
                {**item, "url": f"/media/{item['stored_name']}"}
                for item in sorted(catalog.values(), key=lambda value: value.get("created_at", ""))
            ],
        }

    def export_worker(job_id: str, snapshot: Project, output: Path) -> None:
        jobs[job_id] = {"status": "running", "progress": 15}
        try:
            report = run_export(ffmpeg, snapshot, output)
            jobs[job_id] = {
                "status": "done",
                "progress": 100,
                "filename": output.name,
                "download_url": f"/api/exports/{output.name}",
                "report": report,
            }
        except Exception as exc:
            output.unlink(missing_ok=True)
            jobs[job_id] = {"status": "error", "progress": 0, "message": str(exc)}
        finally:
            export_slot.release()

    @app.errorhandler(413)
    def too_large(_error):
        return jsonify(error=f"文件过大，单次上传上限为 {upload_limit_mb} MB"), 413

    @app.errorhandler(ValueError)
    def invalid_request(error):
        return jsonify(error=str(error)), 400

    @app.errorhandler(Exception)
    def unexpected_error(error):
        app.logger.exception("Unhandled web editor error")
        if production:
            return jsonify(error="服务器处理失败，请稍后重试"), 500
        return jsonify(error=f"服务器处理失败：{error}"), 500

    @app.get("/login")
    def login_page():
        if current_account():
            return redirect(url_for("index"))
        return render_template("login.html")

    @app.get("/guide")
    def guide_page():
        guide = json.loads((ROOT / "web" / "user_guide.json").read_text(encoding="utf-8"))
        return render_template("guide.html", guide=guide)

    @app.get("/guide/download")
    def guide_pdf():
        return send_from_directory(
            ROOT / "web" / "static" / "guides", "lingjian-quick-start.pdf",
            as_attachment=True, download_name="灵剪快速上手.pdf", mimetype="application/pdf",
        )

    @app.get("/api/auth/status")
    def auth_status():
        setup_required = accounts.count() == 0
        return jsonify(
            setup_required=setup_required,
            setup_token_required=setup_required and bool(setup_token),
            authenticated=current_account() is not None,
            user=current_account(),
            csrf_token=csrf_token(),
        )

    @app.post("/api/auth/setup")
    def auth_setup():
        payload = request.get_json(silent=True) or {}
        with lock:
            if accounts.count() != 0:
                return jsonify(error="管理员账户已经创建，请直接登录"), 409
            supplied = str(payload.get("setup_token") or "")
            if setup_token and not hmac.compare_digest(setup_token.encode(), supplied.encode()):
                return jsonify(error="初始化密钥无效，请使用部署控制台提供的密钥"), 403
            username = validate_username(payload.get("username"))
            password = validate_password(payload.get("password"))
            if password != str(payload.get("confirm_password") or ""):
                raise ValueError("两次输入的密码不一致")
            user = accounts.create(username, generate_password_hash(password), "admin")
        session.clear()
        session.permanent = True
        session["user_id"] = user["id"]
        token = csrf_token()
        return jsonify(user=user, csrf_token=token), 201

    @app.post("/api/auth/login")
    def auth_login():
        payload = request.get_json(silent=True) or {}
        username = str(payload.get("username") or "").strip()
        password = str(payload.get("password") or "")
        row = accounts.get_by_username(username)
        if row is None or not bool(row["is_active"]) or not check_password_hash(row["password_hash"], password):
            return jsonify(error="用户名或密码错误，或账户已停用"), 401
        accounts.touch_login(int(row["id"]))
        session.clear()
        session.permanent = True
        session["user_id"] = int(row["id"])
        token = csrf_token()
        return jsonify(user=accounts.public(accounts.get(int(row["id"]))), csrf_token=token)

    @app.post("/api/auth/logout")
    def auth_logout():
        session.clear()
        return jsonify(logged_out=True)

    @app.get("/api/auth/me")
    def auth_me():
        return jsonify(user=current_account(), csrf_token=csrf_token())

    @app.get("/admin/accounts")
    def account_admin_page():
        if current_account()["role"] != "admin":
            return redirect(url_for("index"))
        return render_template("admin.html")

    @app.get("/api/admin/users")
    @require_admin
    def list_users():
        return jsonify(users=accounts.list())

    @app.post("/api/admin/users")
    @require_admin
    def create_user():
        payload = request.get_json(silent=True) or {}
        username = validate_username(payload.get("username"))
        password = validate_password(payload.get("password"))
        role = validate_role(payload.get("role"))
        user = accounts.create(username, generate_password_hash(password), role)
        return jsonify(user=user), 201

    @app.patch("/api/admin/users/<int:user_id>")
    @require_admin
    def update_user(user_id: int):
        payload = request.get_json(silent=True) or {}
        target = accounts.get(user_id)
        if target is None:
            raise ValueError("找不到该账户")
        requested_role = validate_role(payload["role"]) if "role" in payload else None
        requested_active = bool(payload["is_active"]) if "is_active" in payload else None
        removes_active_admin = bool(target["is_active"]) and target["role"] == "admin" and (
            requested_role == "editor" or requested_active is False
        )
        if removes_active_admin and accounts.active_admin_count() <= 1:
            raise ValueError("必须至少保留一个启用中的管理员账户")
        if user_id == current_account()["id"] and requested_active is False:
            raise ValueError("不能停用当前登录账户")
        password_hash = None
        if "password" in payload and str(payload["password"]):
            password_hash = generate_password_hash(validate_password(payload["password"]))
        user = accounts.update(
            user_id,
            role=requested_role,
            is_active=requested_active,
            password_hash=password_hash,
        )
        return jsonify(user=user)

    @app.delete("/api/admin/users/<int:user_id>")
    @require_admin
    def delete_user(user_id: int):
        target = accounts.get(user_id)
        if target is None:
            raise ValueError("找不到该账户")
        if user_id == current_account()["id"]:
            raise ValueError("不能删除当前登录账户")
        if bool(target["is_active"]) and target["role"] == "admin" and accounts.active_admin_count() <= 1:
            raise ValueError("必须至少保留一个启用中的管理员账户")
        accounts.delete(user_id)
        return jsonify(deleted=True)

    @app.get("/")
    def index():
        return render_template("index.html", current_user=current_account(), csrf_token=csrf_token())

    @app.get("/api/health")
    def health():
        return jsonify(status="ok" if ffmpeg else "degraded", ffmpeg=ffmpeg or "", export_ready=bool(ffmpeg))

    @app.get("/api/project")
    def get_project():
        with lock:
            return jsonify(state_json())

    @app.patch("/api/project")
    def update_project():
        payload = request.get_json(silent=True) or {}
        with lock:
            changed = False
            if "title" in payload:
                title = str(payload["title"]).strip()
                if not title or len(title) > 120:
                    raise ValueError("工程名称应为 1–120 个字符")
                changed = changed or title != project.title
                project.title = title
            if "ratio" in payload:
                ratio = str(payload["ratio"])
                if ratio not in {"9:16", "16:9", "1:1"}:
                    raise ValueError("不支持的画幅")
                changed = changed or ratio != project.ratio
                project.ratio = ratio
            if changed:
                bump_revision()
            return jsonify(state_json())

    @app.post("/api/media/upload")
    def upload_media():
        files = request.files.getlist("files") or request.files.getlist("file")
        if not files or not any(item.filename for item in files):
            raise ValueError("请选择要上传的媒体文件")
        created = []
        destinations = []
        try:
            for incoming in files:
                original_name = Path(incoming.filename or "").name
                extension = Path(original_name).suffix.lower()
                if extension not in ALLOWED_EXTENSIONS:
                    raise ValueError(f"不支持的文件格式：{extension or '无扩展名'}")
                safe_name = secure_filename(original_name) or f"media{extension}"
                media_id = uuid.uuid4().hex
                stored_name = f"{media_id}-{safe_name}"
                destination = upload_path / stored_name
                destinations.append(destination)
                incoming.save(destination)
                if probe_fn is None and not ffmpeg:
                    raise ValueError("未找到 FFmpeg。请将 ffmpeg.exe 放在项目根目录，或设置 LINGJIAN_FFMPEG 环境变量。")
                metadata = probe(ffmpeg, str(destination))
                item = {
                    "id": media_id,
                    "name": original_name,
                    "stored_name": stored_name,
                    "path": str(destination),
                    "duration": round(float(metadata["duration"]), 3),
                    "has_audio": bool(metadata.get("has_audio")),
                    "width": int(metadata.get("width") or 0),
                    "height": int(metadata.get("height") or 0),
                    "codec": str(metadata.get("codec") or "unknown"),
                    "capture_order": str(metadata.get("capture_order") or ""),
                    "created_at": uuid.uuid1().hex,
                }
                created.append({**item, "url": f"/media/{stored_name}"})
            # Publish the batch only after every file is valid; failed batches leave no orphans.
            with lock:
                catalog.update({item["id"]: {k: v for k, v in item.items() if k != "url"} for item in created})
                try:
                    save_catalog()
                except Exception:
                    for item in created:
                        catalog.pop(item["id"], None)
                    raise
        except Exception:
            for destination in destinations:
                destination.unlink(missing_ok=True)
            raise
        return jsonify(media=created), 201

    @app.delete("/api/media/<media_id>")
    def delete_media(media_id: str):
        with lock:
            item = catalog_item(media_id)
            used_by = [clip for clip in project.clips if clip.path == item["path"]]
            used_by += [overlay for overlay in project.overlays if overlay.path == item["path"]]
            if used_by:
                return jsonify(error=f"该素材正在时间线上使用（{len(used_by)} 处），请先从时间线移除后再删除。", code="media_in_use"), 409
            catalog.pop(media_id, None)
            save_catalog()
            try:
                Path(item["path"]).unlink(missing_ok=True)
            except OSError:
                app.logger.warning("素材文件删除失败：%s", item["path"])
            return jsonify(deleted=True, **state_json())

    @app.get("/media/<path:filename>")
    def serve_media(filename: str):
        return send_from_directory(upload_path, filename, conditional=True)

    @app.post("/api/timeline/clips")
    def add_clip():
        payload = request.get_json(silent=True) or {}
        item = catalog_item(str(payload.get("media_id") or ""))
        if not item.get("width"):
            raise ValueError("音频可以导入和预览；当前时间线仅支持视频片段")
        start = float(payload.get("start", 0))
        end = float(payload.get("end", item["duration"]))
        if start < 0 or end <= start or end > float(item["duration"]) + 0.04:
            raise ValueError("裁剪范围超出素材时长")
        with lock:
            project.clips.append(
                Clip(item["path"], start, end, item["name"], has_audio=bool(item["has_audio"]))
            )
            bump_revision()
            return jsonify(state_json()), 201

    @app.patch("/api/timeline/clips/<clip_id>")
    def update_clip(clip_id: str):
        payload = request.get_json(silent=True) or {}
        with lock:
            clip = next((item for item in project.clips if item.id == clip_id), None)
            if clip is None:
                raise ValueError("找不到该时间线片段")
            before = copy.deepcopy(clip)
            if "start" in payload:
                clip.start = float(payload["start"])
            if "end" in payload:
                clip.end = float(payload["end"])
            if "caption" in payload:
                caption = str(payload["caption"])
                if len(caption) > 120:
                    raise ValueError("单段字幕最多 120 个字符")
                clip.caption = caption
            if "transition" in payload:
                transition = str(payload["transition"])
                if transition not in WEB_TRANSITIONS:
                    raise ValueError("不支持的转场")
                clip.transition = transition
            if "volume" in payload:
                clip.volume = max(0, min(2, float(payload["volume"])))
            media = next((item for item in catalog.values() if item.get("path") == clip.path), None)
            try:
                clip.validate()
                if media and clip.end > float(media["duration"]) + 0.04:
                    raise ValueError("片段出点超出素材时长")
            except Exception:
                clip.__dict__.update(before.__dict__)
                raise
            bump_revision()
            return jsonify(state_json())

    @app.delete("/api/timeline/clips/<clip_id>")
    def delete_clip(clip_id: str):
        with lock:
            index = next((i for i, item in enumerate(project.clips) if item.id == clip_id), -1)
            if index < 0:
                raise ValueError("找不到该时间线片段")
            project.clips.pop(index)
            bump_revision()
            return jsonify(state_json())

    @app.post("/api/timeline/reorder")
    def reorder_clips():
        payload = request.get_json(silent=True) or {}
        ordered_ids = [str(value) for value in payload.get("clip_ids") or []]
        with lock:
            current = {item.id: item for item in project.clips}
            if len(ordered_ids) != len(current) or set(ordered_ids) != set(current):
                raise ValueError("排序列表必须完整包含当前时间线片段")
            project.clips = [current[clip_id] for clip_id in ordered_ids]
            bump_revision()
            return jsonify(state_json())

    @app.post("/api/project/save")
    def save_project():
        with lock:
            _atomic_json(project_path, project.to_dict())
            return jsonify(saved=True, path=str(project_path))

    # ---------------------------------------------------------------- AI director
    class EditorAIBackend:
        """WorkflowBackend over the single in-memory project and the upload catalog.

        Media is resolved from server-side catalog records only; clients never send paths.
        commit_project compares the revision and writes the project file inside the editor lock.
        """

        @staticmethod
        def _check(project_id: str, owner_id: str) -> None:
            if project_id != WEB_PROJECT_ID or not owner_id:
                raise WorkflowError("not_found", "工程不可用。", 404)

        def get_project(self, project_id: str, owner_id: str) -> ProjectSnapshot:
            self._check(project_id, owner_id)
            with lock:
                return ProjectSnapshot(copy.deepcopy(project), revision)

        def resolve_media(self, project_id: str, media_id: str, owner_id: str) -> MediaSource:
            self._check(project_id, owner_id)
            with lock:
                item = copy.deepcopy(catalog.get(media_id))
            if not item:
                raise WorkflowError("not_found", "素材库中没有该素材，请刷新页面后重试。", 404)
            if not int(item.get("width") or 0):
                raise WorkflowError("invalid_media", "只有视频素材可以参与 AI 剪辑，请取消选择音频文件。", 422)
            if ai_analyzer is None and not ffmpeg:
                raise WorkflowError("ffmpeg_unavailable", "未找到 FFmpeg，请设置 LINGJIAN_FFMPEG 后重启服务。", 503)
            with lock:
                stamp = ensure_capture_order(catalog[media_id]) if media_id in catalog else ""
            return MediaSource(
                str(item["id"]), Path(item["path"]), str(item["name"]), float(item["duration"]),
                bool(item.get("has_audio")), stamp,
            )

        def commit_project(self, project_id: str, owner_id: str, candidate: Project,
                           expected_revision: int, *, expected_token: str | None = None) -> ProjectSnapshot:
            self._check(project_id, owner_id)
            with lock:
                if revision != expected_revision:
                    raise RevisionConflict()
                payload = candidate.to_dict()
                try:
                    _atomic_json(project_path, payload)
                except OSError:
                    raise WorkflowError("save_failed", "工程写入磁盘失败，请检查磁盘空间后重试。", 503) from None
                replace_project(Project.from_dict(payload))
                return ProjectSnapshot(copy.deepcopy(project), revision)

    # Cloud AI configuration: settings saved by an administrator in the web UI win over
    # the server environment. Keys stay on the server and are never returned to browsers.
    env_config = config_from_environment()
    ai_settings = _load_ai_settings(ai_settings_path)
    check_cloud = cloud_tester or _default_cloud_tester
    check_transcription = transcription_tester or _default_transcription_tester

    def cloud_config_from(saved: dict | None) -> APIConfig:
        if not saved or not saved.get("api_key"):
            return env_config
        return APIConfig(
            base_url=str(saved.get("base_url") or env_config.base_url), api_key=str(saved["api_key"]),
            model=str(saved.get("model") or env_config.model),
            transcription_model=str(saved.get("transcription_model") or env_config.transcription_model),
            timeout=int(saved.get("timeout") or env_config.timeout),
        )

    workflow_options = {"caption_limit": CAPTION_MAX_CHARS}
    if ai_analyzer is not None:
        workflow_options["local_analyzer"] = ai_analyzer
    try:
        workflow = AIWorkflow(EditorAIBackend(), ffmpeg or "", cloud_config=cloud_config_from(ai_settings), **workflow_options)
    except ValueError as exc:
        app.logger.warning("云端 AI 配置无效，已回退为仅本地模式：%s", exc)
        workflow = AIWorkflow(EditorAIBackend(), ffmpeg or "", **workflow_options)
    app.ai_workflow = workflow  # Tests and embedders close it explicitly.
    atexit.register(workflow.close)

    def ai_config_public() -> dict:
        config = workflow.config
        key = config.api_key or ""
        return {
            "base_url": config.base_url, "model": config.model, "transcription_model": config.transcription_model,
            "timeout": config.timeout, "api_key_set": bool(key),
            "api_key_hint": f"{key[:3]}…{key[-4:]}" if len(key) >= 12 else ("•••" if key else ""),
            "source": "settings" if ai_settings else ("environment" if env_config.api_key else "none"),
            "cloud_available": workflow.capabilities()["cloud_available"],
            "updated_at": str((ai_settings or {}).get("updated_at") or ""),
            "updated_by": str((ai_settings or {}).get("updated_by") or ""),
        }

    def parse_ai_config(payload: dict) -> APIConfig:
        current = workflow.config

        def text(name: str, default: str, limit: int) -> str:
            value = payload.get(name, default)
            if value is None:
                value = default
            if not isinstance(value, str):
                raise ValueError("请求格式不正确")
            value = value.strip()
            if len(value) > limit:
                raise ValueError("字段过长，请检查输入")
            return value

        base_url = text("base_url", current.base_url, 300) or current.base_url
        if not base_url.lower().startswith("https://"):
            raise ValueError("接口地址必须以 https:// 开头")
        model = text("model", current.model, 100) or current.model
        transcription_model = text("transcription_model", current.transcription_model, 100) or current.transcription_model
        timeout = payload.get("timeout", current.timeout)
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 1 <= timeout <= 180:
            raise ValueError("单次请求超时需为 1–180 秒")
        api_key = text("api_key", "", 512)
        if any(character.isspace() for character in api_key):
            raise ValueError("API Key 不能包含空格或换行")
        api_key = api_key or current.api_key or ""
        if not api_key:
            raise ValueError("请填写 API Key")
        config = APIConfig(base_url=base_url, api_key=api_key, model=model,
                           transcription_model=transcription_model, timeout=int(timeout))
        try:
            validate_cloud_config(config)
        except ValueError as exc:
            raise ValueError(str(exc)) from None
        return config

    @app.get("/api/admin/ai-config")
    @require_admin
    def get_ai_config():
        return jsonify(ai_config_public())

    @app.put("/api/admin/ai-config")
    @require_admin
    def save_ai_config():
        nonlocal ai_settings
        config = parse_ai_config(request.get_json(silent=True) or {})
        record = {
            "base_url": config.base_url, "api_key": config.api_key, "model": config.model,
            "transcription_model": config.transcription_model, "timeout": config.timeout,
            "updated_at": utc_now(), "updated_by": current_account()["username"],
        }
        _save_ai_settings(ai_settings_path, record)
        workflow.configure_cloud(config)
        ai_settings = record
        return jsonify(ai_config_public())

    @app.delete("/api/admin/ai-config")
    @require_admin
    def clear_ai_config():
        nonlocal ai_settings
        ai_settings_path.unlink(missing_ok=True)
        ai_settings = None
        try:
            workflow.configure_cloud(env_config)
        except ValueError:
            workflow.configure_cloud(None)
        return jsonify(ai_config_public())

    @app.post("/api/admin/ai-config/test")
    @require_admin
    def test_ai_config():
        config = parse_ai_config(request.get_json(silent=True) or {})
        try:
            models = check_cloud(config)
        except AIRequestError as exc:
            return jsonify(ok=False, code=exc.code, error=str(exc))
        except ValueError as exc:
            return jsonify(ok=False, code="invalid_config", error=str(exc))
        listed = isinstance(models, list)
        transcription_error = None
        try:
            check_transcription(config)
        except AIRequestError as exc:
            transcription_error = str(exc)
            looks_like_speech_model = any(word in config.transcription_model.lower() for word in ("transcribe", "whisper", "speech", "asr"))
            if not looks_like_speech_model:
                transcription_error += " 转写模型需要是语音转写模型，例如 gpt-4o-mini-transcribe。"
        return jsonify(
            ok=transcription_error is None, models_listed=listed, model_count=len(models) if listed else 0,
            model_found=(config.model in models) if listed else None,
            transcription_model_found=(config.transcription_model in models) if listed else None,
            transcription_ok=transcription_error is None, transcription_error=transcription_error,
        )

    def ai_owner() -> str:
        user = current_account()
        return f"user-{user['id']}" if user else ""

    def ai_payload() -> dict:
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            raise WorkflowError("invalid_request", "请求格式不正确。", 422)
        return payload

    def ai_revision(value) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise WorkflowError("invalid_revision", "缺少工程版本，请刷新页面后重试。", 422)
        return value

    @app.errorhandler(WorkflowError)
    def workflow_error(error: WorkflowError):
        return jsonify(error=str(error), code=error.code), error.status

    @app.get("/api/ai/capabilities")
    def ai_capabilities():
        return jsonify(workflow.capabilities())

    @app.get("/api/ai/sources")
    def ai_sources():
        with lock:
            items = [
                {"id": item["id"], "name": item["name"], "duration": item["duration"], "has_audio": bool(item.get("has_audio")),
                 "capture_time": format_stamp(ensure_capture_order(item))}
                for item in sorted(catalog.values(), key=lambda value: value.get("created_at", ""))
                if int(item.get("width") or 0)
            ]
            items.sort(key=lambda value: (value["capture_time"] == "", value["capture_time"], value["name"].lower()))
            return jsonify(items=items, revision=revision)

    @app.get("/api/ai/plans")
    def ai_list_plans():
        return jsonify(plans=workflow.list(WEB_PROJECT_ID, ai_owner()))

    @app.post("/api/ai/plans")
    def ai_create_plan():
        payload = ai_payload()
        media_ids = payload.get("media_ids")
        if not isinstance(media_ids, list) or not all(isinstance(value, str) for value in media_ids):
            raise WorkflowError("invalid_sources", "请选择 1 到 20 份素材。", 422)
        target = payload.get("target_duration", 30)
        if isinstance(target, bool) or not isinstance(target, (int, float)):
            raise WorkflowError("invalid_duration", "目标时长必须为 5 到 180 秒。", 422)
        mode, prompt = payload.get("mode", "local"), payload.get("prompt", "")
        opening, style = payload.get("opening", "hook"), payload.get("style", "")
        language = payload.get("language", "zh")
        if not all(isinstance(value, str) for value in (mode, prompt, opening, style, language)):
            raise WorkflowError("invalid_request", "请求格式不正确。", 422)
        plan = workflow.create(
            WEB_PROJECT_ID, ai_owner(), media_ids=media_ids, revision=ai_revision(payload.get("revision")),
            mode=mode, target_duration=target, prompt=prompt, cloud_consent=payload.get("cloud_consent") is True,
            opening=opening, style=style.strip(), language=language,
        )
        return jsonify(plan), 202

    @app.get("/api/ai/plans/<plan_id>")
    def ai_get_plan(plan_id: str):
        return jsonify(workflow.get(WEB_PROJECT_ID, plan_id, ai_owner()))

    @app.post("/api/ai/plans/<plan_id>/cancel")
    def ai_cancel_plan(plan_id: str):
        return jsonify(workflow.cancel(WEB_PROJECT_ID, plan_id, ai_owner()))

    @app.post("/api/ai/plans/<plan_id>/opening")
    def ai_set_opening(plan_id: str):
        payload = ai_payload()
        preset = payload.get("preset", "smart")
        if not isinstance(preset, str):
            raise WorkflowError("invalid_request", "请求格式不正确。", 422)
        return jsonify(workflow.set_opening(WEB_PROJECT_ID, plan_id, ai_owner(), preset=preset))

    @app.post("/api/ai/plans/<plan_id>/apply")
    def ai_apply_plan(plan_id: str):
        payload = ai_payload()
        plan = workflow.apply(
            WEB_PROJECT_ID, plan_id, ai_owner(),
            revision=ai_revision(payload.get("revision")), confirm=payload.get("confirm") is True,
        )
        with lock:
            return jsonify(plan=plan, **state_json())

    @app.post("/api/ai/plans/<plan_id>/undo")
    def ai_undo_plan(plan_id: str):
        payload = ai_payload()
        plan = workflow.undo(WEB_PROJECT_ID, plan_id, ai_owner(), revision=ai_revision(payload.get("revision")))
        with lock:
            return jsonify(plan=plan, **state_json())

    @app.post("/api/export")
    def export_project():
        with lock:
            if not project.clips:
                raise ValueError("时间线为空，无法导出")
            if export_runner is None and not ffmpeg:
                raise ValueError("未找到 FFmpeg，当前无法导出。请配置 LINGJIAN_FFMPEG 后重启服务。")
            snapshot = Project.from_dict(project.to_dict())
        if not export_slot.acquire(blocking=False):
            return jsonify(error="已有视频正在导出，请等待完成后再试"), 409
        job_id = uuid.uuid4().hex
        output = export_path / f"{job_id}.mp4"
        jobs[job_id] = {"status": "queued", "progress": 0}
        try:
            threading.Thread(target=export_worker, args=(job_id, snapshot, output), daemon=True).start()
        except Exception:
            jobs.pop(job_id, None)
            export_slot.release()
            raise
        return jsonify(job_id=job_id, status_url=f"/api/export/{job_id}"), 202

    @app.get("/api/export/<job_id>")
    def export_status(job_id: str):
        job = jobs.get(job_id)
        if not job:
            raise ValueError("找不到该导出任务")
        return jsonify(job)

    @app.get("/api/exports/<path:filename>")
    def download_export(filename: str):
        return send_from_directory(export_path, filename, as_attachment=True)

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")), debug=False)
