from __future__ import annotations

import copy
import hmac
import json
import os
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

from video_editing_engine import (
    AUDIO_EXT,
    VIDEO_EXT,
    Clip,
    Project,
    build_render_command,
    probe_media,
    validate_rendered_mp4,
)
from web_auth import AccountStore, validate_password, validate_role, validate_username


ROOT = Path(__file__).resolve().parent
ALLOWED_EXTENSIONS = VIDEO_EXT | AUDIO_EXT


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


def create_app(workspace: str | Path | None = None, probe_fn=None, export_runner=None) -> Flask:
    app = Flask(__name__, template_folder="web/templates", static_folder="web/static")
    app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024 * 1024

    workspace_path = Path(workspace or os.environ.get("LINGJIAN_WEB_WORKSPACE", ROOT / "web_workspace")).resolve()
    upload_path = workspace_path / "uploads"
    export_path = workspace_path / "exports"
    project_path = workspace_path / "project.ljproject"
    catalog_path = workspace_path / "media_catalog.json"
    upload_path.mkdir(parents=True, exist_ok=True)
    export_path.mkdir(parents=True, exist_ok=True)
    app.secret_key = _load_secret_key(workspace_path)
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        PERMANENT_SESSION_LIFETIME=timedelta(hours=12),
    )
    accounts = AccountStore(workspace_path / "accounts.sqlite3")

    configured_ffmpeg = os.environ.get("LINGJIAN_FFMPEG")
    bundled_ffmpeg = ROOT / "ffmpeg.exe"
    ffmpeg = configured_ffmpeg or (str(bundled_ffmpeg) if bundled_ffmpeg.exists() else shutil.which("ffmpeg"))
    probe = probe_fn or probe_media
    run_export = export_runner or _default_export_runner
    lock = threading.RLock()
    jobs: dict[str, dict] = {}

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

        public_endpoints = {"login_page", "auth_status", "auth_setup", "auth_login", "health", "static"}
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

    def save_catalog() -> None:
        _atomic_json(catalog_path, catalog)

    def catalog_item(media_id: str) -> dict:
        item = catalog.get(media_id)
        if not item:
            raise ValueError("找不到该素材")
        return item

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
                "clips": [clip_json(clip) for clip in project.clips],
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

    @app.errorhandler(413)
    def too_large(_error):
        return jsonify(error="文件过大，单次上传上限为 2 GB"), 413

    @app.errorhandler(ValueError)
    def invalid_request(error):
        return jsonify(error=str(error)), 400

    @app.errorhandler(Exception)
    def unexpected_error(error):
        app.logger.exception("Unhandled web editor error")
        return jsonify(error=f"服务器处理失败：{error}"), 500

    @app.get("/login")
    def login_page():
        if current_account():
            return redirect(url_for("index"))
        return render_template("login.html")

    @app.get("/api/auth/status")
    def auth_status():
        return jsonify(
            setup_required=accounts.count() == 0,
            authenticated=current_account() is not None,
            user=current_account(),
            csrf_token=csrf_token(),
        )

    @app.post("/api/auth/setup")
    def auth_setup():
        if accounts.count() != 0:
            return jsonify(error="管理员账户已经创建，请直接登录"), 409
        payload = request.get_json(silent=True) or {}
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
            if "title" in payload:
                title = str(payload["title"]).strip()
                if not title or len(title) > 120:
                    raise ValueError("工程名称应为 1–120 个字符")
                project.title = title
            if "ratio" in payload:
                ratio = str(payload["ratio"])
                if ratio not in {"9:16", "16:9", "1:1"}:
                    raise ValueError("不支持的画幅")
                project.ratio = ratio
            return jsonify(state_json())

    @app.post("/api/media/upload")
    def upload_media():
        files = request.files.getlist("files") or request.files.getlist("file")
        if not files or not any(item.filename for item in files):
            raise ValueError("请选择要上传的媒体文件")
        created = []
        for incoming in files:
            original_name = Path(incoming.filename or "").name
            extension = Path(original_name).suffix.lower()
            if extension not in ALLOWED_EXTENSIONS:
                raise ValueError(f"不支持的文件格式：{extension or '无扩展名'}")
            safe_name = secure_filename(original_name) or f"media{extension}"
            media_id = uuid.uuid4().hex
            stored_name = f"{media_id}-{safe_name}"
            destination = upload_path / stored_name
            incoming.save(destination)
            try:
                if probe_fn is None and not ffmpeg:
                    raise ValueError("未找到 FFmpeg。请将 ffmpeg.exe 放在项目根目录，或设置 LINGJIAN_FFMPEG 环境变量。")
                metadata = probe(ffmpeg, str(destination))
            except Exception:
                destination.unlink(missing_ok=True)
                raise
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
                "created_at": uuid.uuid1().hex,
            }
            catalog[media_id] = item
            created.append({**item, "url": f"/media/{stored_name}"})
        save_catalog()
        return jsonify(media=created), 201

    @app.get("/media/<path:filename>")
    def serve_media(filename: str):
        return send_from_directory(upload_path, filename, conditional=True)

    @app.post("/api/timeline/clips")
    def add_clip():
        payload = request.get_json(silent=True) or {}
        item = catalog_item(str(payload.get("media_id") or ""))
        start = float(payload.get("start", 0))
        end = float(payload.get("end", item["duration"]))
        if start < 0 or end <= start or end > float(item["duration"]) + 0.04:
            raise ValueError("裁剪范围超出素材时长")
        with lock:
            project.clips.append(
                Clip(item["path"], start, end, item["name"], has_audio=bool(item["has_audio"]))
            )
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
                if transition not in {"none", "fade", "dissolve", "wipeleft", "wiperight", "slideup", "slidedown"}:
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
            return jsonify(state_json())

    @app.delete("/api/timeline/clips/<clip_id>")
    def delete_clip(clip_id: str):
        with lock:
            index = next((i for i, item in enumerate(project.clips) if item.id == clip_id), -1)
            if index < 0:
                raise ValueError("找不到该时间线片段")
            project.clips.pop(index)
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
            return jsonify(state_json())

    @app.post("/api/project/save")
    def save_project():
        with lock:
            _atomic_json(project_path, project.to_dict())
            return jsonify(saved=True, path=str(project_path))

    @app.post("/api/export")
    def export_project():
        with lock:
            if not project.clips:
                raise ValueError("时间线为空，无法导出")
            if export_runner is None and not ffmpeg:
                raise ValueError("未找到 FFmpeg，当前无法导出。请配置 LINGJIAN_FFMPEG 后重启服务。")
            snapshot = Project.from_dict(project.to_dict())
        job_id = uuid.uuid4().hex
        output = export_path / f"{job_id}.mp4"
        jobs[job_id] = {"status": "queued", "progress": 0}
        threading.Thread(target=export_worker, args=(job_id, snapshot, output), daemon=True).start()
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
