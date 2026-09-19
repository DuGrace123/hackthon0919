"""Exercise the production entry point with real FFmpeg and a process restart.

Uses an isolated temporary workspace and disposable credentials. Plain HTTP is
only used on loopback, with cookies forwarded explicitly to model a TLS proxy.
Run from the repo or /app: python tests/cloud_smoke.py
"""
import http.client
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from http.cookies import SimpleCookie
from pathlib import Path


def main():
    root = Path.cwd()
    with tempfile.TemporaryDirectory(prefix="lingjian-cloud-smoke-") as temporary:
        base = Path(temporary)
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        setup_key = secrets.token_urlsafe(32)
        password = secrets.token_urlsafe(24)
        env = {**os.environ, "PORT": str(port), "LINGJIAN_ENV": "production",
               "LINGJIAN_WEB_WORKSPACE": str(base / "workspace"),
               "LINGJIAN_SECRET_KEY": secrets.token_urlsafe(48), "LINGJIAN_SETUP_TOKEN": setup_key}
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            import imageio_ffmpeg
            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        env["LINGJIAN_FFMPEG"] = ffmpeg
        sample = base / "source.mp4"
        subprocess.run([ffmpeg, "-y", "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=24",
                        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000", "-t", "2",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(sample)],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=30)
        cookie = ""
        csrf = ""

        def request(method, path, data=None, *, body=None, content_type=None, expected=200):
            nonlocal cookie, csrf
            headers = {"Cookie": cookie, "X-CSRF-Token": csrf}
            if data is not None:
                body = json.dumps(data).encode()
                content_type = "application/json"
            if content_type:
                headers["Content-Type"] = content_type
            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
            try:
                connection.request(method, path, body=body, headers=headers)
                response = connection.getresponse()
                raw = response.read()
                assert response.status == expected, (method, path, response.status, raw[:500])
                if response.getheader("Set-Cookie"):
                    values = SimpleCookie(response.getheader("Set-Cookie"))
                    cookie = "; ".join(f"{key}={item.value}" for key, item in values.items())
                    assert "Secure" in response.getheader("Set-Cookie")
                if "application/json" in response.getheader("Content-Type", ""):
                    result = json.loads(raw)
                    csrf = result.get("csrf_token", csrf)
                    return result
                return raw
            finally:
                connection.close()

        log_path = base / "gunicorn.log"
        server = None
        log_file = log_path.open("w+")

        def start():
            nonlocal server
            server = subprocess.Popen([sys.executable, "-m", "gunicorn", "--config", "gunicorn.conf.py", "web_app:app"],
                                      cwd=root, env=env, stdout=log_file, stderr=subprocess.STDOUT)
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                if server.poll() is not None:
                    raise AssertionError("Server exited: " + log_path.read_text()[-4000:])
                try:
                    health = request("GET", "/api/health")
                    assert health["export_ready"], health
                    return
                except (ConnectionError, OSError):
                    time.sleep(0.1)
            raise AssertionError("Server did not become ready")

        def stop():
            if server and server.poll() is None:
                server.terminate()
                try:
                    server.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait(timeout=5)

        try:
            start()
            request("GET", "/api/project", expected=401)
            assert b"setupToken" in request("GET", "/login")
            status = request("GET", "/api/auth/status")
            assert status["setup_token_required"]
            credentials = {"username": "smoke-admin", "password": password, "confirm_password": password}
            request("POST", "/api/auth/setup", credentials, expected=403)
            request("POST", "/api/auth/setup", {**credentials, "setup_token": setup_key}, expected=201)
            boundary = "----smoke" + secrets.token_hex(12)
            body = (f'--{boundary}\r\nContent-Disposition: form-data; name="files"; filename="source.mp4"\r\n'
                    'Content-Type: video/mp4\r\n\r\n').encode() + sample.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
            media = request("POST", "/api/media/upload", body=body,
                            content_type=f"multipart/form-data; boundary={boundary}", expected=201)["media"][0]
            clip = request("POST", "/api/timeline/clips", {"media_id": media["id"]}, expected=201)["project"]["clips"][0]
            request("PATCH", "/api/project", {"ratio": "16:9", "title": "Cloud smoke test"})
            request("PATCH", f"/api/timeline/clips/{clip['id']}", {"caption": "云端中文字幕 · Hello"})
            request("POST", "/api/project/save", {})
            job = request("POST", "/api/export", {}, expected=202)
            deadline = time.monotonic() + 120
            while time.monotonic() < deadline:
                rendered = request("GET", job["status_url"])
                if rendered["status"] in {"done", "error"}:
                    break
                time.sleep(0.2)
            assert rendered["status"] == "done", rendered
            exported = request("GET", rendered["download_url"])
            assert len(exported) > 1000
            stop()
            env.pop("LINGJIAN_SETUP_TOKEN")
            start()
            assert request("GET", "/api/auth/status")["authenticated"]
            project = request("GET", "/api/project")["project"]
            assert project["title"] == "Cloud smoke test" and len(project["clips"]) == 1
            assert request("GET", media["url"]) == sample.read_bytes()
            assert request("GET", rendered["download_url"]) == exported
            request("POST", "/api/auth/logout", {})
            request("GET", media["url"], expected=302)
            request("GET", "/api/auth/status")
            request("POST", "/api/auth/login", credentials)
            assert request("GET", "/api/auth/status")["authenticated"]
            print("PASS: production bootstrap, auth, upload, Chinese-caption MP4 export, and restart persistence")
        finally:
            stop()
            log_file.close()


if __name__ == "__main__":
    main()
