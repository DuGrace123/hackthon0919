"""HTTP-layer checks for backend.api using FastAPI's TestClient (skipped when fastapi is absent)."""
from __future__ import annotations

import sys
import tempfile
import unittest

try:
    from fastapi.testclient import TestClient
except ImportError:  # fastapi and httpx are backend-only dependencies
    print("SKIPPED: fastapi 未安装（pip install -r requirements-backend.txt）", flush=True)
    sys.exit(0)

from backend.api import create_app
from backend.project_store import ProjectStore
from video_editing_engine import Clip, Project


def payload(title="接口测试"):
    project = Project(title)
    project.clips = [Clip("D:/footage/a.mp4", 0, 2, "a.mp4")]
    return project.to_dict()


class BackendApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="lingjian-api-")
        self.addCleanup(self.tmp.cleanup)
        self.store = ProjectStore(self.tmp.name)
        self.client = TestClient(create_app(self.store))

    def test_health_and_docs(self):
        health = self.client.get("/api/v1/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["status"], "ok")
        self.assertEqual(self.client.get("/docs").status_code, 200)
        self.assertIn("/api/v1/projects/{project_id}", self.client.get("/openapi.json").json()["paths"])

    def test_project_lifecycle_with_optimistic_lock(self):
        created = self.client.post("/api/v1/projects", json={"title": "新工程"})
        self.assertEqual(created.status_code, 201, created.text)
        record = created.json()
        pid = record["id"]
        self.assertEqual((record["revision"], record["project"]["title"], record["project"]["version"]), (1, "新工程", 5))
        self.assertEqual(self.client.get(f"/api/v1/projects/{pid}").json(), record)
        self.assertEqual([x["id"] for x in self.client.get("/api/v1/projects").json()], [pid])
        saved = self.client.put(f"/api/v1/projects/{pid}", json={"revision": 1, "project": payload("改过")})
        self.assertEqual(saved.status_code, 200, saved.text)
        self.assertEqual(saved.json()["revision"], 2)
        stale = self.client.put(f"/api/v1/projects/{pid}", json={"revision": 1, "project": payload("过期")})
        self.assertEqual(stale.status_code, 409)
        detail = stale.json()["detail"]
        self.assertEqual((detail["code"], detail["expected"], detail["current"]["revision"], detail["current"]["project"]["title"]),
                         ("revision_conflict", 1, 2, "改过"))
        # "Refresh": a brand-new app process on the same workspace still sees the project.
        fresh = TestClient(create_app(ProjectStore(self.tmp.name)))
        self.assertEqual(fresh.get(f"/api/v1/projects/{pid}").json()["project"]["title"], "改过")
        self.assertEqual(self.client.delete(f"/api/v1/projects/{pid}").status_code, 204)
        self.assertEqual(self.client.get(f"/api/v1/projects/{pid}").status_code, 404)
        self.assertEqual(self.client.delete(f"/api/v1/projects/{pid}").status_code, 404)

    def test_error_shapes(self):
        bad = self.client.get("/api/v1/projects/not-a-valid-id")
        self.assertEqual(bad.status_code, 400)
        self.assertEqual(bad.json()["detail"]["code"], "invalid_project_id")
        # Encoded traversal is stopped by the router (404) or by the id check (400); it never reaches a file.
        self.assertIn(self.client.get("/api/v1/projects/..%2F..%2Fetc%2Fpasswd").status_code, (400, 404))
        self.assertEqual(self.client.get("/api/v1/projects/" + "A" * 32).json()["detail"]["code"], "invalid_project_id")
        missing = self.client.get("/api/v1/projects/" + "0" * 32)
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(missing.json()["detail"]["code"], "project_not_found")
        pid = self.client.post("/api/v1/projects", json={}).json()["id"]
        invalid = self.client.put(f"/api/v1/projects/{pid}", json={
            "revision": 1, "project": {"clips": [{"path": "a.mp4", "start": 5, "end": 1, "transition": "nope"}]}})
        self.assertEqual(invalid.status_code, 422, invalid.text)
        detail = invalid.json()["detail"]
        self.assertEqual(detail["code"], "invalid_project")
        self.assertEqual({e["path"] for e in detail["errors"]}, {"clips[0].end", "clips[0].transition"})
        malformed = self.client.put(f"/api/v1/projects/{pid}", json={"project": {}})
        self.assertEqual(malformed.status_code, 422)
        self.assertEqual(malformed.json()["detail"]["code"], "invalid_request")
        self.assertEqual(malformed.json()["detail"]["errors"][0]["path"], "revision")
        self.assertEqual(self.client.post("/api/v1/projects", json={"title": "x" * 200}).status_code, 422)
        future = self.client.post("/api/v1/projects", json={"project": {"version": 99}})
        self.assertEqual(future.status_code, 422)
        self.assertEqual(future.json()["detail"]["errors"][0]["path"], "version")

    def test_cors_allows_browser_frontends(self):
        preflight = self.client.options("/api/v1/projects", headers={
            "Origin": "http://localhost:5173", "Access-Control-Request-Method": "PUT"})
        self.assertEqual(preflight.status_code, 200)
        self.assertEqual(preflight.headers.get("access-control-allow-origin"), "http://localhost:5173")
        plain = self.client.get("/api/v1/health", headers={"Origin": "http://localhost:5173"})
        self.assertEqual(plain.headers.get("access-control-allow-origin"), "http://localhost:5173")

    def test_import_desktop_project_upgrades_version(self):
        old = {"version": 3, "title": "旧版", "clips": [{
            "path": "a.mp4", "start": 0.0, "end": 1.0, "name": "镜头1", "caption": "字幕", "position": "bottom",
            "transition": "none", "volume": 1, "has_audio": True}]}
        imported = self.client.post("/api/v1/projects", json={"project": old})
        self.assertEqual(imported.status_code, 201, imported.text)
        project = imported.json()["project"]
        self.assertEqual((project["version"], project["clips"][0]["caption_effect"]), (5, "clean"))


if __name__ == "__main__":
    unittest.main()
