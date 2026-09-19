from __future__ import annotations

import io
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from ai_story_planner import AIRequestError, unprotect_secret
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

    def test_media_can_be_deleted_unless_it_is_on_the_timeline(self):
        media = self.upload()
        other = self.upload("camera-two.mp4")
        clip = self.add_clip(media["id"])
        blocked = self.client.delete(f"/api/media/{media['id']}", headers={"X-CSRF-Token": self.csrf})
        self.assertEqual(blocked.status_code, 409, blocked.get_json())
        self.assertEqual(blocked.get_json()["code"], "media_in_use")
        self.assertTrue(Path(media["path"]).exists())
        removed = self.client.delete(f"/api/media/{other['id']}", headers={"X-CSRF-Token": self.csrf})
        self.assertEqual(removed.status_code, 200, removed.get_json())
        self.assertEqual([item["id"] for item in removed.get_json()["media"]], [media["id"]])
        self.assertFalse(Path(other["path"]).exists())
        self.assertEqual(self.client.get("/api/project").get_json()["project"]["clips"][0]["id"], clip["id"])
        self.client.delete(f"/api/timeline/clips/{clip['id']}", headers={"X-CSRF-Token": self.csrf})
        freed = self.client.delete(f"/api/media/{media['id']}", headers={"X-CSRF-Token": self.csrf})
        self.assertEqual(freed.status_code, 200, freed.get_json())
        self.assertEqual(self.client.get("/api/project").get_json()["media"], [])
        missing = self.client.delete(f"/api/media/{media['id']}", headers={"X-CSRF-Token": self.csrf})
        self.assertEqual(missing.status_code, 400)

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

    def test_failed_batch_keeps_existing_media_without_partial_imports(self):
        original = self.upload("existing.mp4")
        before = self.client.get("/api/project").get_json()["media"]
        response = self.client.post(
            "/api/media/upload",
            data={"files": [(io.BytesIO(b"video"), "valid.mp4"), (io.BytesIO(b"text"), "invalid.txt")]},
            headers={"X-CSRF-Token": self.csrf},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.get("/api/project").get_json()["media"], before)
        workspace = Path(self.temp.name)
        self.assertEqual([p.name for p in (workspace / "uploads").iterdir()], [original["stored_name"]])
        self.assertEqual(set(json.loads((workspace / "media_catalog.json").read_text())), {original["id"]})

    def test_catalog_write_failure_rolls_back_new_files_and_memory(self):
        original = self.upload("existing.mp4")
        with patch("web_app._atomic_json", side_effect=OSError("disk full")):
            response = self.client.post(
                "/api/media/upload", data={"files": (io.BytesIO(b"video"), "new.mp4")},
                headers={"X-CSRF-Token": self.csrf},
            )
        self.assertEqual(response.status_code, 500)
        media = self.client.get("/api/project").get_json()["media"]
        self.assertEqual([item["id"] for item in media], [original["id"]])
        self.assertEqual(len(list((Path(self.temp.name) / "uploads").iterdir())), 1)

    def test_audio_uses_audio_probe_and_cannot_create_unrenderable_video_clip(self):
        with patch("web_app.resolve_ffmpeg", return_value="test-ffmpeg"):
            app = create_app(self.temp.name)
        self.addCleanup(app.ai_workflow.close)
        client = app.test_client()
        token = client.get("/api/auth/status").get_json()["csrf_token"]
        login = client.post("/api/auth/login", json={"username": "test-admin", "password": "testing-pass-123"}, headers={"X-CSRF-Token": token})
        token = login.get_json()["csrf_token"]
        metadata = {"duration": 3, "has_audio": True, "width": 0, "height": 0}
        with patch("web_app.probe_media", return_value=metadata) as probe:
            response = client.post("/api/media/upload", data={"files": (io.BytesIO(b"audio"), "sound.wav")}, headers={"X-CSRF-Token": token})
        self.assertEqual(response.status_code, 201, response.get_json())
        self.assertFalse(probe.call_args.kwargs["require_video"])
        media = response.get_json()["media"][0]
        preview = client.get(media["url"])
        self.assertEqual(preview.data, b"audio")
        preview.close()
        rejected = client.post("/api/timeline/clips", json={"media_id": media["id"]}, headers={"X-CSRF-Token": token})
        self.assertEqual(rejected.status_code, 400)
        self.assertEqual(client.get("/api/project").get_json()["project"]["clips"], [])


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


def fake_probe_by_type(ffmpeg, path):
    meta = fake_probe(ffmpeg, path)
    if Path(path).suffix.lower() in {".mp3", ".wav"}:
        meta.update(width=0, height=0, codec="mp3")
    return meta


def fake_analyzer(_ffmpeg, source, checkpoint):
    checkpoint()
    return [
        dict(start=0.0, end=4.0, score=80, caption="", reason="本地镜头", role="setup"),
        dict(start=7.0, end=11.0, score=90, caption="", reason="本地镜头", role="outro"),
    ]


class AIDirectorTests(unittest.TestCase):
    """The AI planning workflow mounted on the web editor: preview, apply, undo, conflicts, privacy."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"FIGSTUDIO_AI_API_KEY": ""})
        self.env.start()
        self.app = create_app(self.temp.name, probe_fn=fake_probe_by_type, export_runner=fake_export, ai_analyzer=fake_analyzer)
        self.app.config.update(TESTING=True)
        self.client = self.app.test_client()
        status = self.client.get("/api/auth/status").get_json()
        created = self.client.post(
            "/api/auth/setup",
            json={"username": "test-admin", "password": "testing-pass-123", "confirm_password": "testing-pass-123"},
            headers={"X-CSRF-Token": status["csrf_token"]},
        )
        self.assertEqual(created.status_code, 201, created.get_json())
        self.csrf = created.get_json()["csrf_token"]
        self.headers = {"X-CSRF-Token": self.csrf}

    def tearDown(self):
        self.app.ai_workflow.close()
        self.env.stop()
        self.temp.cleanup()

    def upload(self, name="camera-one.mp4"):
        response = self.client.post(
            "/api/media/upload",
            data={"files": (io.BytesIO(b"fake video"), name)},
            content_type="multipart/form-data",
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()["media"][0]

    def add_clip(self, media_id):
        response = self.client.post("/api/timeline/clips", json={"media_id": media_id}, headers=self.headers)
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()["project"]["clips"][-1]

    def project(self):
        return self.client.get("/api/project").get_json()["project"]

    def project_file(self):
        return json.loads((Path(self.temp.name) / "project.ljproject").read_text(encoding="utf-8"))

    def create_plan(self, media, **overrides):
        body = {"media_ids": [media["id"]], "revision": self.project()["revision"], "target_duration": 8}
        body.update(overrides)
        return self.client.post("/api/ai/plans", json=body, headers=self.headers)

    def wait(self, plan_id):
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            plan = self.client.get(f"/api/ai/plans/{plan_id}").get_json()
            if plan["status"] not in {"queued", "running"}:
                return plan
            time.sleep(0.02)
        raise AssertionError("AI plan did not finish")

    def test_capabilities_and_sources_only_list_video_media(self):
        video = self.upload()
        self.upload("voice.mp3")
        capabilities = self.client.get("/api/ai/capabilities").get_json()
        self.assertTrue(capabilities["local_available"])
        self.assertFalse(capabilities["cloud_available"])
        sources = self.client.get("/api/ai/sources").get_json()
        self.assertEqual([item["id"] for item in sources["items"]], [video["id"]])
        self.assertIn("capture_time", sources["items"][0])
        self.assertEqual(sources["revision"], self.project()["revision"])

    def test_local_plan_preview_apply_persist_and_undo(self):
        media = self.upload()
        manual = self.add_clip(media["id"])
        before = self.project()

        started = self.create_plan(media, prompt="保留开头和结尾")
        self.assertEqual(started.status_code, 202, started.get_json())
        plan = self.wait(started.get_json()["id"])
        self.assertEqual(plan["status"], "ready", plan)
        shots = plan["result"]["shots"]
        self.assertGreaterEqual(len(shots), 2)
        self.assertEqual({shot["media_id"] for shot in shots}, {media["id"]})
        self.assertNotIn("source_path", json.dumps(plan))
        self.assertNotIn(self.temp.name, json.dumps(plan))
        self.assertEqual(plan["result"]["changes"]["replace_video_clips"], 1)
        self.assertEqual(self.project(), before, "previewing a plan must not touch the project")

        applied = self.client.post(
            f"/api/ai/plans/{plan['id']}/apply", json={"revision": before["revision"], "confirm": True}, headers=self.headers
        )
        self.assertEqual(applied.status_code, 200, applied.get_json())
        body = applied.get_json()
        self.assertEqual(body["plan"]["status"], "applied")
        clips = body["project"]["clips"]
        self.assertEqual(len(clips), len(shots))
        self.assertTrue(all(clip["ai_selected"] for clip in clips))
        self.assertTrue(all(clip["media_url"] for clip in clips), "AI clips must stay previewable in the browser")
        self.assertGreater(body["project"]["revision"], before["revision"])
        on_disk = self.project_file()
        self.assertEqual(len(on_disk["clips"]), len(shots))
        self.assertEqual(on_disk["edit_log"][-1]["type"], "apply_ai_plan")

        undone = self.client.post(
            f"/api/ai/plans/{plan['id']}/undo", json={"revision": body["project"]["revision"]}, headers=self.headers
        )
        self.assertEqual(undone.status_code, 200, undone.get_json())
        self.assertEqual(undone.get_json()["plan"]["status"], "undone")
        self.assertEqual([clip["id"] for clip in undone.get_json()["project"]["clips"]], [manual["id"]])
        self.assertEqual([clip["id"] for clip in self.project_file()["clips"]], [manual["id"]])

    def test_opening_and_style_options_reach_the_report(self):
        media = self.upload()
        started = self.create_plan(media, opening="chronological", style="纪录片 · 尊重事件顺序与完整语义")
        self.assertEqual(started.status_code, 202, started.get_json())
        plan = self.wait(started.get_json()["id"])
        self.assertEqual(plan["status"], "ready", plan)
        self.assertEqual(plan["result"]["shots"][0]["role"], "setup")
        report = plan["result"]["report"]
        self.assertEqual(report["opening"], "chronological")
        self.assertTrue(any("纪录片" in line for line in report["techniques"]))
        self.assertIn("故事线", report["report_text"])
        invalid = self.create_plan(media, opening="sideways")
        self.assertEqual(invalid.status_code, 422)
        self.assertEqual(invalid.get_json()["code"], "invalid_opening")

    def test_opening_preset_can_be_switched_and_applied_with_layers(self):
        media = self.upload()
        plan = self.wait(self.create_plan(media).get_json()["id"])
        self.assertTrue(plan["result"]["validation"]["ok"])
        self.assertTrue(plan["result"]["opening_presets"])
        switched = self.client.post(f"/api/ai/plans/{plan['id']}/opening", json={"preset": "tear_flash"}, headers=self.headers)
        self.assertEqual(switched.status_code, 200, switched.get_json())
        self.assertEqual(switched.get_json()["result"]["creative"]["preset_id"], "tear_flash")
        applied = self.client.post(
            f"/api/ai/plans/{plan['id']}/apply", json={"revision": self.project()["revision"], "confirm": True}, headers=self.headers
        )
        self.assertEqual(applied.status_code, 200, applied.get_json())
        project = applied.get_json()["project"]
        self.assertEqual(project["overlay_count"], switched.get_json()["result"]["changes"]["add_overlays"])
        self.assertEqual(project["sfx_count"], switched.get_json()["result"]["changes"]["add_sound_effects"])
        self.assertTrue(project["bgm_name"])
        on_disk = self.project_file()
        self.assertEqual(len(on_disk["overlays"]), project["overlay_count"])
        self.assertEqual(on_disk["edit_log"][-1]["opening"], "tear_flash")

    def test_manual_edit_after_plan_generation_blocks_apply(self):
        media = self.upload()
        clip = self.add_clip(media["id"])
        plan = self.wait(self.create_plan(media).get_json()["id"])
        self.assertEqual(plan["status"], "ready", plan)
        edited = self.client.patch(f"/api/timeline/clips/{clip['id']}", json={"caption": "手工字幕"}, headers=self.headers)
        self.assertEqual(edited.status_code, 200, edited.get_json())
        applied = self.client.post(
            f"/api/ai/plans/{plan['id']}/apply", json={"revision": self.project()["revision"], "confirm": True}, headers=self.headers
        )
        self.assertEqual(applied.status_code, 409, applied.get_json())
        self.assertEqual(applied.get_json()["code"], "revision_conflict")
        self.assertEqual(self.project()["clips"][0]["caption"], "手工字幕")

    def test_unchanged_project_patch_keeps_plan_applicable(self):
        media = self.upload()
        plan = self.wait(self.create_plan(media).get_json()["id"])
        current = self.project()
        touched = self.client.patch("/api/project", json={"title": current["title"], "ratio": current["ratio"]}, headers=self.headers)
        self.assertEqual(touched.get_json()["project"]["revision"], current["revision"])
        applied = self.client.post(
            f"/api/ai/plans/{plan['id']}/apply", json={"revision": current["revision"], "confirm": True}, headers=self.headers
        )
        self.assertEqual(applied.status_code, 200, applied.get_json())

    def test_apply_needs_confirmation_and_create_needs_current_revision(self):
        media = self.upload()
        plan = self.wait(self.create_plan(media).get_json()["id"])
        denied = self.client.post(
            f"/api/ai/plans/{plan['id']}/apply", json={"revision": self.project()["revision"], "confirm": False}, headers=self.headers
        )
        self.assertEqual(denied.status_code, 422)
        self.assertEqual(denied.get_json()["code"], "confirmation_required")
        stale = self.create_plan(media, revision=self.project()["revision"] + 5)
        self.assertEqual(stale.status_code, 409)
        missing = self.create_plan(media, revision="3")
        self.assertEqual(missing.status_code, 422)
        self.assertEqual(missing.get_json()["code"], "invalid_revision")

    def test_cancel_discards_plan_without_touching_project(self):
        media = self.upload()
        self.add_clip(media["id"])
        before = self.project()
        plan = self.wait(self.create_plan(media).get_json()["id"])
        cancelled = self.client.post(f"/api/ai/plans/{plan['id']}/cancel", headers=self.headers)
        self.assertEqual(cancelled.status_code, 200, cancelled.get_json())
        self.assertEqual(cancelled.get_json()["status"], "cancelled")
        self.assertEqual(self.project(), before)
        applied = self.client.post(
            f"/api/ai/plans/{plan['id']}/apply", json={"revision": before["revision"], "confirm": True}, headers=self.headers
        )
        self.assertEqual(applied.status_code, 409)
        self.assertEqual(applied.get_json()["code"], "invalid_state")

    def test_audio_only_media_is_rejected(self):
        audio = self.upload("voice.mp3")
        response = self.create_plan(audio)
        self.assertEqual(response.status_code, 422, response.get_json())
        self.assertEqual(response.get_json()["code"], "invalid_media")

    def test_cloud_mode_needs_consent_and_server_configuration(self):
        media = self.upload()
        no_consent = self.create_plan(media, mode="cloud")
        self.assertEqual(no_consent.status_code, 422)
        self.assertEqual(no_consent.get_json()["code"], "consent_required")
        unavailable = self.create_plan(media, mode="cloud", cloud_consent=True)
        self.assertEqual(unavailable.status_code, 503)
        self.assertEqual(unavailable.get_json()["code"], "cloud_unavailable")

    def test_ai_clip_transitions_survive_manual_edits(self):
        media = self.upload()
        plan = self.wait(self.create_plan(media).get_json()["id"])
        applied = self.client.post(
            f"/api/ai/plans/{plan['id']}/apply", json={"revision": self.project()["revision"], "confirm": True}, headers=self.headers
        ).get_json()
        clip = applied["project"]["clips"][-1]
        edited = self.client.patch(
            f"/api/timeline/clips/{clip['id']}",
            json={"caption": "改一下字幕", "transition": "pip_zoom"}, headers=self.headers,
        )
        self.assertEqual(edited.status_code, 200, edited.get_json())

    def test_plan_list_lets_a_reloaded_page_recover_the_latest_plan(self):
        media = self.upload()
        first = self.wait(self.create_plan(media).get_json()["id"])
        self.client.post(f"/api/ai/plans/{first['id']}/cancel", headers=self.headers)
        second = self.wait(self.create_plan(media).get_json()["id"])
        listed = self.client.get("/api/ai/plans").get_json()["plans"]
        self.assertEqual([plan["id"] for plan in listed], [second["id"], first["id"]])
        self.assertEqual(listed[0]["status"], "ready")
        self.assertEqual(listed[1]["status"], "cancelled")
        applied = self.client.post(
            f"/api/ai/plans/{second['id']}/apply", json={"revision": self.project()["revision"], "confirm": True}, headers=self.headers
        )
        self.assertEqual(applied.status_code, 200, applied.get_json())
        self.assertEqual(self.client.get("/api/ai/plans").get_json()["plans"][0]["status"], "applied")

    def test_plans_are_private_and_require_login(self):
        media = self.upload()
        plan_id = self.create_plan(media).get_json()["id"]
        created = self.client.post(
            "/api/admin/users", json={"username": "editor-one", "password": "editor-pass-123", "role": "editor"}, headers=self.headers
        )
        self.assertEqual(created.status_code, 201, created.get_json())
        other = self.app.test_client()
        status = other.get("/api/auth/status").get_json()
        login = other.post(
            "/api/auth/login", json={"username": "editor-one", "password": "editor-pass-123"},
            headers={"X-CSRF-Token": status["csrf_token"]},
        )
        self.assertEqual(login.status_code, 200, login.get_json())
        self.assertEqual(other.get(f"/api/ai/plans/{plan_id}").status_code, 404)
        self.assertEqual(other.get("/api/ai/plans").get_json()["plans"], [])
        anonymous = self.app.test_client()
        self.assertEqual(anonymous.get("/api/ai/capabilities").status_code, 401)


class AIServiceSettingsTests(unittest.TestCase):
    """Administrators configure the cloud AI service in the web UI; keys never return to the browser."""

    KEY = "sk-test-1234567890abcd"

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"FIGSTUDIO_AI_API_KEY": ""})
        self.env.start()
        self.tester_calls = []
        self.tester_result = ["gpt-5-mini", "gpt-4o-mini-transcribe", "other-model"]
        self.transcription_calls = []
        self.transcription_result = None
        self.app = self.make_app()
        self.client = self.app.test_client()
        status = self.client.get("/api/auth/status").get_json()
        created = self.client.post(
            "/api/auth/setup",
            json={"username": "test-admin", "password": "testing-pass-123", "confirm_password": "testing-pass-123"},
            headers={"X-CSRF-Token": status["csrf_token"]},
        )
        self.assertEqual(created.status_code, 201, created.get_json())
        self.headers = {"X-CSRF-Token": created.get_json()["csrf_token"]}

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def fake_tester(self, config):
        self.tester_calls.append(config)
        if isinstance(self.tester_result, Exception):
            raise self.tester_result
        return self.tester_result

    def fake_transcription(self, config):
        self.transcription_calls.append(config)
        if isinstance(self.transcription_result, Exception):
            raise self.transcription_result

    def make_app(self):
        app = create_app(self.temp.name, probe_fn=fake_probe, export_runner=fake_export, ai_analyzer=fake_analyzer,
                         cloud_tester=self.fake_tester, transcription_tester=self.fake_transcription)
        app.config.update(TESTING=True)
        self.addCleanup(app.ai_workflow.close)
        return app

    def settings(self):
        return self.client.get("/api/admin/ai-config").get_json()

    def save(self, **overrides):
        body = {"base_url": "https://ai.example.test/v1", "api_key": self.KEY, "model": "gpt-5-mini",
                "transcription_model": "gpt-4o-mini-transcribe", "timeout": 45}
        body.update(overrides)
        return self.client.put("/api/admin/ai-config", json=body, headers=self.headers)

    def test_starts_unconfigured_with_local_mode_only(self):
        current = self.settings()
        self.assertFalse(current["api_key_set"])
        self.assertEqual(current["source"], "none")
        self.assertFalse(current["cloud_available"])
        self.assertFalse(self.client.get("/api/ai/capabilities").get_json()["cloud_available"])

    def test_saving_enables_cloud_mode_masks_key_and_protects_file(self):
        saved = self.save()
        self.assertEqual(saved.status_code, 200, saved.get_json())
        body = saved.get_json()
        self.assertTrue(body["api_key_set"])
        self.assertEqual(body["api_key_hint"], "sk-…abcd")
        self.assertNotIn(self.KEY, json.dumps(body))
        self.assertEqual(body["source"], "settings")
        self.assertTrue(body["cloud_available"])
        self.assertEqual(body["updated_by"], "test-admin")
        self.assertEqual(body["timeout"], 45)
        self.assertTrue(self.client.get("/api/ai/capabilities").get_json()["cloud_available"])

        settings_file = Path(self.temp.name) / "ai_settings.json"
        raw = settings_file.read_text(encoding="utf-8")
        self.assertNotIn(self.KEY, raw, "the key must not be stored in clear text")
        self.assertEqual(unprotect_secret(json.loads(raw)["api_key"]), self.KEY)
        if os.name != "nt":
            self.assertEqual(settings_file.stat().st_mode & 0o777, 0o600)

        edited = self.save(api_key="", model="gpt-5")
        self.assertEqual(edited.status_code, 200, edited.get_json())
        self.assertEqual(edited.get_json()["model"], "gpt-5")
        self.assertEqual(edited.get_json()["api_key_hint"], "sk-…abcd", "a blank key keeps the saved one")

    def test_settings_survive_a_server_restart(self):
        self.assertEqual(self.save().status_code, 200)
        restarted = self.make_app().test_client()
        status = restarted.get("/api/auth/status").get_json()
        login = restarted.post("/api/auth/login", json={"username": "test-admin", "password": "testing-pass-123"},
                               headers={"X-CSRF-Token": status["csrf_token"]})
        self.assertEqual(login.status_code, 200, login.get_json())
        current = restarted.get("/api/admin/ai-config").get_json()
        self.assertTrue(current["api_key_set"])
        self.assertEqual(current["source"], "settings")
        self.assertTrue(current["cloud_available"])
        self.assertEqual(current["base_url"], "https://ai.example.test/v1")

    def test_rejects_plain_http_missing_key_and_bad_timeout(self):
        insecure = self.save(base_url="http://ai.example.test")
        self.assertEqual(insecure.status_code, 400)
        self.assertIn("https", insecure.get_json()["error"])
        missing = self.save(api_key="")
        self.assertEqual(missing.status_code, 400)
        self.assertIn("API Key", missing.get_json()["error"])
        slow = self.save(timeout=0)
        self.assertEqual(slow.status_code, 400)
        spaced = self.save(api_key="sk-with space")
        self.assertEqual(spaced.status_code, 400)
        self.assertFalse(self.settings()["api_key_set"])

    def test_connection_test_uses_saved_key_and_reports_model_names(self):
        self.assertEqual(self.save().status_code, 200)
        body = {"base_url": "https://ai.example.test/v1", "model": "gpt-5-mini", "transcription_model": "gpt-4o-mini-transcribe", "timeout": 45}
        result = self.client.post("/api/admin/ai-config/test", json=body, headers=self.headers).get_json()
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["model_found"])
        self.assertTrue(result["transcription_model_found"])
        self.assertEqual(result["model_count"], 3)
        self.assertTrue(result["transcription_ok"])
        self.assertEqual(self.tester_calls[-1].api_key, self.KEY)
        self.assertEqual(self.tester_calls[-1].base_url, "https://ai.example.test/v1")
        self.assertEqual(self.transcription_calls[-1].transcription_model, "gpt-4o-mini-transcribe")

        # A chat model in the transcription slot exists in the model list but cannot transcribe.
        self.transcription_result = AIRequestError("AI 服务请求失败（HTTP 431）。", "provider_http_error")
        result = self.client.post("/api/admin/ai-config/test", json={**body, "transcription_model": "gpt-5-mini"}, headers=self.headers).get_json()
        self.assertFalse(result["ok"])
        self.assertTrue(result["transcription_model_found"])
        self.assertFalse(result["transcription_ok"])
        self.assertIn("HTTP 431", result["transcription_error"])
        self.assertIn("gpt-4o-mini-transcribe", result["transcription_error"])
        self.transcription_result = None

        self.tester_result = ["something-else"]
        result = self.client.post("/api/admin/ai-config/test", json=body, headers=self.headers).get_json()
        self.assertTrue(result["ok"])
        self.assertFalse(result["model_found"])

        self.tester_result = None
        result = self.client.post("/api/admin/ai-config/test", json=body, headers=self.headers).get_json()
        self.assertTrue(result["ok"])
        self.assertFalse(result["models_listed"])

        self.tester_result = AIRequestError("AI 服务认证失败，请检查服务端密钥与权限。", "authentication_failed")
        result = self.client.post("/api/admin/ai-config/test", json=body, headers=self.headers).get_json()
        self.assertFalse(result["ok"])
        self.assertEqual(result["code"], "authentication_failed")
        self.assertNotIn(self.KEY, json.dumps(result))

    def test_clearing_settings_disables_cloud_mode(self):
        self.assertEqual(self.save().status_code, 200)
        cleared = self.client.delete("/api/admin/ai-config", headers=self.headers)
        self.assertEqual(cleared.status_code, 200, cleared.get_json())
        self.assertFalse(cleared.get_json()["api_key_set"])
        self.assertEqual(cleared.get_json()["source"], "none")
        self.assertFalse(self.client.get("/api/ai/capabilities").get_json()["cloud_available"])
        self.assertFalse((Path(self.temp.name) / "ai_settings.json").exists())

    def test_environment_key_is_used_until_web_settings_exist(self):
        with patch.dict(os.environ, {"FIGSTUDIO_AI_API_KEY": "env-key-1234567890", "FIGSTUDIO_AI_BASE_URL": "https://env.example.test"}):
            app = self.make_app()
        client = app.test_client()
        status = client.get("/api/auth/status").get_json()
        client.post("/api/auth/login", json={"username": "test-admin", "password": "testing-pass-123"}, headers={"X-CSRF-Token": status["csrf_token"]})
        current = client.get("/api/admin/ai-config").get_json()
        self.assertEqual(current["source"], "environment")
        self.assertTrue(current["api_key_set"])
        self.assertTrue(current["cloud_available"])
        self.assertNotIn("env-key", json.dumps(current))

    def test_editors_cannot_read_or_change_the_service_settings(self):
        created = self.client.post(
            "/api/admin/users", json={"username": "editor-one", "password": "editor-pass-123", "role": "editor"}, headers=self.headers
        )
        self.assertEqual(created.status_code, 201, created.get_json())
        other = self.app.test_client()
        status = other.get("/api/auth/status").get_json()
        login = other.post("/api/auth/login", json={"username": "editor-one", "password": "editor-pass-123"},
                           headers={"X-CSRF-Token": status["csrf_token"]})
        self.assertEqual(login.status_code, 200, login.get_json())
        csrf = login.get_json()["csrf_token"]
        self.assertEqual(other.get("/api/admin/ai-config").status_code, 403)
        self.assertEqual(other.put("/api/admin/ai-config", json={"api_key": "x"}, headers={"X-CSRF-Token": csrf}).status_code, 403)
        self.assertEqual(other.post("/api/admin/ai-config/test", json={}, headers={"X-CSRF-Token": csrf}).status_code, 403)
        self.assertFalse(self.settings()["api_key_set"])
