"""Deployment boundaries: safe bootstrap, persistent state, and bounded exports."""
import io
import os
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from web_app import create_app


class WebDeploymentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.env = patch.dict(os.environ, {
            "LINGJIAN_ENV": "production",
            "LINGJIAN_SECRET_KEY": "test-session-secret-" * 3,
            "LINGJIAN_SETUP_TOKEN": "test-setup-secret-" * 3,
            "LINGJIAN_MAX_UPLOAD_MB": "1",
        })
        self.env.start()
        self.addCleanup(self.env.stop)

    def make_app(self, **kwargs):
        app = create_app(self.temp.name, **kwargs)
        app.config["TESTING"] = True
        self.addCleanup(app.ai_workflow.close)
        return app

    def setup_admin(self, client, token=None):
        status = client.get("/api/auth/status").get_json()
        return client.post("/api/auth/setup", headers={"X-CSRF-Token": status["csrf_token"]}, json={
            "username": "deploy-admin", "password": "disposable-test-password",
            "confirm_password": "disposable-test-password",
            "setup_token": os.environ["LINGJIAN_SETUP_TOKEN"] if token is None else token,
        })

    def test_production_refuses_missing_secrets(self):
        with patch.dict(os.environ, {"LINGJIAN_SECRET_KEY": ""}):
            with self.assertRaisesRegex(ValueError, "LINGJIAN_SECRET_KEY"):
                self.make_app()
        with patch.dict(os.environ, {"LINGJIAN_SETUP_TOKEN": "short"}):
            with self.assertRaisesRegex(ValueError, "LINGJIAN_SETUP_TOKEN"):
                self.make_app()

    def test_bootstrap_requires_secret_then_closes_and_sets_secure_cookie(self):
        client = self.make_app().test_client()
        status = client.get("/api/auth/status")
        self.assertTrue(status.get_json()["setup_token_required"])
        self.assertNotIn(os.environ["LINGJIAN_SETUP_TOKEN"], status.get_data(as_text=True))
        self.assertEqual(self.setup_admin(client, "").status_code, 403)
        self.assertEqual(self.setup_admin(client, "错误密钥").status_code, 403)
        created = self.setup_admin(client)
        self.assertEqual(created.status_code, 201)
        cookie = created.headers["Set-Cookie"]
        for flag in ("Secure", "HttpOnly", "SameSite=Lax"):
            self.assertIn(flag, cookie)
        self.assertEqual(self.setup_admin(client).status_code, 409)
        self.assertFalse(client.get("/api/auth/status").get_json()["setup_token_required"])

    def test_restart_preserves_accounts_session_media_and_saved_project(self):
        def probe(_ffmpeg, path):
            return dict(path=path, duration=3, width=640, height=360, has_audio=False)

        client = self.make_app(probe_fn=probe).test_client()
        created = self.setup_admin(client)
        headers = {"X-CSRF-Token": created.get_json()["csrf_token"]}
        media = client.post("/api/media/upload", headers=headers,
                            data={"files": (io.BytesIO(b"persisted-media"), "clip.mp4")}).get_json()["media"][0]
        self.assertEqual(client.post("/api/timeline/clips", headers=headers,
                                     json={"media_id": media["id"]}).status_code, 201)
        self.assertEqual(client.post("/api/project/save", headers=headers).status_code, 200)
        # After first setup, the bootstrap key can be removed from the host.
        with patch.dict(os.environ, {"LINGJIAN_SETUP_TOKEN": ""}):
            restarted = self.make_app(probe_fn=probe).test_client()
        restarted.set_cookie("session", client.get_cookie("session").value)
        self.assertTrue(restarted.get("/api/auth/status").get_json()["authenticated"])
        state = restarted.get("/api/project").get_json()
        self.assertEqual(len(state["project"]["clips"]), 1)
        self.assertEqual(state["media"][0]["id"], media["id"])
        self.assertEqual(restarted.get(media["url"]).data, b"persisted-media")

    def test_configured_upload_limit_returns_useful_error(self):
        client = self.make_app().test_client()
        created = self.setup_admin(client).get_json()
        result = client.post("/api/media/upload", headers={"X-CSRF-Token": created["csrf_token"]},
                             data={"files": (io.BytesIO(b"x" * (1024 * 1024 + 1)), "large.mp4")})
        self.assertEqual(result.status_code, 413)
        self.assertIn("1 MB", result.get_json()["error"])

    def test_only_one_export_runs_and_slot_is_released_after_failure(self):
        release = threading.Event()
        self.addCleanup(release.set)

        def render(_ffmpeg, _project, _output):
            release.wait(timeout=5)
            raise RuntimeError("test render failure")

        app = self.make_app(
            probe_fn=lambda _ffmpeg, path: dict(path=path, duration=3, width=640, height=360, has_audio=False),
            export_runner=render,
        )
        client = app.test_client()
        headers = {"X-CSRF-Token": self.setup_admin(client).get_json()["csrf_token"]}
        media = client.post("/api/media/upload", headers=headers,
                            data={"files": (io.BytesIO(b"video"), "clip.mp4")}).get_json()["media"][0]
        client.post("/api/timeline/clips", headers=headers, json={"media_id": media["id"]})
        first = client.post("/api/export", headers=headers)
        self.assertEqual(first.status_code, 202)
        self.assertEqual(client.post("/api/export", headers=headers).status_code, 409)
        release.set()
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            status = client.get(first.get_json()["status_url"]).get_json()
            if status["status"] == "error":
                break
            time.sleep(0.01)
        self.assertEqual(status["status"], "error")
        self.assertEqual(client.post("/api/export", headers=headers).status_code, 202)


if __name__ == "__main__":
    unittest.main()
