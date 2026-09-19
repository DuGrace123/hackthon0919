from __future__ import annotations

import io
import json
import tempfile
import time
import unittest
from pathlib import Path

from web_app import create_app


def fake_probe(_ffmpeg, path):
    return {
        "path": path,
        "name": Path(path).name,
        "duration": 12.5,
        "has_audio": True,
        "width": 1920,
        "height": 1080,
        "codec": "h264",
    }


def fake_export(_ffmpeg, project, output):
    output.write_bytes(b"test-mp4")
    return {"duration": project.duration, "codec": "h264"}


class WebEditingWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = create_app(self.temp.name, probe_fn=fake_probe, export_runner=fake_export)
        self.app.config.update(TESTING=True)
        self.client = self.app.test_client()
        status = self.client.get("/api/auth/status").get_json()
        self.csrf = status["csrf_token"]
        created = self.client.post(
            "/api/auth/setup",
            json={"username": "test-admin", "password": "testing-pass-123", "confirm_password": "testing-pass-123"},
            headers={"X-CSRF-Token": self.csrf},
        )
        self.assertEqual(created.status_code, 201, created.get_json())
        self.csrf = created.get_json()["csrf_token"]

    def tearDown(self):
        self.temp.cleanup()

    def upload(self, name="camera-one.mp4"):
        response = self.client.post(
            "/api/media/upload",
            data={"files": (io.BytesIO(b"fake video"), name)},
            content_type="multipart/form-data",
            headers={"X-CSRF-Token": self.csrf},
        )
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()["media"][0]

    def add_clip(self, media_id):
        response = self.client.post("/api/timeline/clips", json={"media_id": media_id}, headers={"X-CSRF-Token": self.csrf})
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()["project"]["clips"][-1]

    def test_complete_upload_edit_reorder_save_workflow(self):
        first_media = self.upload()
        second_media = self.upload("camera-two.mp4")
        first = self.add_clip(first_media["id"])
        second = self.add_clip(second_media["id"])

        edited = self.client.patch(
            f"/api/timeline/clips/{first['id']}",
            json={"start": 1.25, "end": 8.75, "caption": "新的字幕", "transition": "dissolve", "volume": 0.8},
            headers={"X-CSRF-Token": self.csrf},
        )
        self.assertEqual(edited.status_code, 200, edited.get_json())
        clip = next(item for item in edited.get_json()["project"]["clips"] if item["id"] == first["id"])
        self.assertEqual(clip["caption"], "新的字幕")
        self.assertEqual(clip["start"], 1.25)

        reordered = self.client.post(
            "/api/timeline/reorder", json={"clip_ids": [second["id"], first["id"]]}, headers={"X-CSRF-Token": self.csrf}
        )
        self.assertEqual(reordered.status_code, 200)
        self.assertEqual(reordered.get_json()["project"]["clips"][0]["id"], second["id"])

        updated = self.client.patch("/api/project", json={"title": "Hackathon Demo", "ratio": "16:9"}, headers={"X-CSRF-Token": self.csrf})
        self.assertEqual(updated.status_code, 200)
        saved = self.client.post("/api/project/save", headers={"X-CSRF-Token": self.csrf})
        self.assertEqual(saved.status_code, 200)
        project_file = Path(self.temp.name) / "project.ljproject"
        self.assertTrue(project_file.exists())
        self.assertEqual(json.loads(project_file.read_text(encoding="utf-8"))["title"], "Hackathon Demo")

    def test_invalid_trim_is_rejected_without_corrupting_clip(self):
        media = self.upload()
        clip = self.add_clip(media["id"])
        response = self.client.patch(
            f"/api/timeline/clips/{clip['id']}", json={"start": 9, "end": 14}, headers={"X-CSRF-Token": self.csrf}
        )
        self.assertEqual(response.status_code, 400)
        current = self.client.get("/api/project").get_json()["project"]["clips"][0]
        self.assertEqual(current["start"], 0)
        self.assertEqual(current["end"], 12.5)

    def test_export_runs_asynchronously_and_returns_download(self):
        media = self.upload()
        self.add_clip(media["id"])
        started = self.client.post("/api/export", headers={"X-CSRF-Token": self.csrf})
        self.assertEqual(started.status_code, 202)
        status_url = started.get_json()["status_url"]
        job = None
        for _ in range(40):
            job = self.client.get(status_url).get_json()
            if job["status"] in {"done", "error"}:
                break
            time.sleep(0.025)
        self.assertEqual(job["status"], "done", job)
        downloaded = self.client.get(job["download_url"])
        self.assertEqual(downloaded.status_code, 200)
        self.assertEqual(downloaded.data, b"test-mp4")
        downloaded.close()

    def test_empty_timeline_has_clear_export_error(self):
        response = self.client.post("/api/export", headers={"X-CSRF-Token": self.csrf})
        self.assertEqual(response.status_code, 400)
        self.assertIn("时间线为空", response.get_json()["error"])


class AccountManagementTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = create_app(self.temp.name, probe_fn=fake_probe, export_runner=fake_export)
        self.app.config.update(TESTING=True)
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp.cleanup()

    def bootstrap_admin(self):
        status = self.client.get("/api/auth/status").get_json()
        response = self.client.post(
            "/api/auth/setup",
            json={"username": "owner", "password": "owner-pass-123", "confirm_password": "owner-pass-123"},
            headers={"X-CSRF-Token": status["csrf_token"]},
        )
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()["csrf_token"]

    def test_first_launch_setup_and_protected_editor(self):
        redirect_response = self.client.get("/")
        self.assertEqual(redirect_response.status_code, 302)
        self.assertTrue(redirect_response.headers["Location"].endswith("/login"))
        csrf = self.bootstrap_admin()
        editor = self.client.get("/")
        self.assertEqual(editor.status_code, 200)
        self.assertIn(b"logoutBtn", editor.data)
        missing_csrf = self.client.post("/api/project/save")
        self.assertEqual(missing_csrf.status_code, 403)
        saved = self.client.post("/api/project/save", headers={"X-CSRF-Token": csrf})
        self.assertEqual(saved.status_code, 200)

    def test_admin_can_create_disable_and_reset_accounts(self):
        csrf = self.bootstrap_admin()
        created = self.client.post(
            "/api/admin/users",
            json={"username": "editor-one", "password": "editor-pass-123", "role": "editor"},
            headers={"X-CSRF-Token": csrf},
        )
        self.assertEqual(created.status_code, 201, created.get_json())
        user_id = created.get_json()["user"]["id"]
        disabled = self.client.patch(
            f"/api/admin/users/{user_id}",
            json={"is_active": False, "password": "replacement-pass-123"},
            headers={"X-CSRF-Token": csrf},
        )
        self.assertEqual(disabled.status_code, 200, disabled.get_json())
        self.assertFalse(disabled.get_json()["user"]["is_active"])
        users = self.client.get("/api/admin/users").get_json()["users"]
        self.assertEqual(len(users), 2)
        self.assertNotIn("password_hash", users[0])

    def test_last_active_admin_cannot_be_disabled(self):
        csrf = self.bootstrap_admin()
        me = self.client.get("/api/auth/me").get_json()["user"]
        response = self.client.patch(
            f"/api/admin/users/{me['id']}",
            json={"is_active": False},
            headers={"X-CSRF-Token": csrf},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("管理员", response.get_json()["error"])


if __name__ == "__main__":
    unittest.main()
