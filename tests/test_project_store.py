"""Portable checks for backend.project_store: validation, atomic saves, revisions, id boundary."""
from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from backend.project_store import (
    SCHEMA_VERSION,
    InvalidProject,
    InvalidProjectId,
    ProjectCorrupt,
    ProjectNotFound,
    ProjectStore,
    RevisionConflict,
    validate_project_payload,
)
from video_editing_engine import Clip, Project

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "examples" / "projects" / "creator_controls_sample_01.ljproject"


def sample_payload(title="测试工程"):
    project = Project(title)
    project.clips = [Clip("D:/footage/a.mp4", 0, 2, "a.mp4"),
                     Clip("D:/footage/b.mp4", 1, 3.5, "b.mp4", caption="你好", transition="dissolve")]
    return project.to_dict()


class ValidationTests(unittest.TestCase):
    def errors(self, payload):
        with self.assertRaises(InvalidProject) as ctx:
            validate_project_payload(payload)
        return {e["path"]: e["message"] for e in ctx.exception.errors}

    def test_canonical_form_is_version_5_with_defaults(self):
        clean = validate_project_payload({"title": "最小工程", "clips": [{"path": "a.mp4", "start": 0, "end": 1}]})
        self.assertEqual(clean["version"], SCHEMA_VERSION)
        self.assertEqual(clean["ratio"], "9:16")
        clip = clean["clips"][0]
        self.assertEqual((clip["transition"], clip["caption_effect"], clip["volume"]), ("fade", "clean", 1.0))
        self.assertTrue(clip["id"])
        self.assertEqual(Project.from_dict(clean).to_dict(), clean)

    def test_reports_every_problem_at_once(self):
        errors = self.errors({
            "version": 6, "title": "x" * 121, "ratio": "vertical", "bgm_volume": 3, "typo": 1,
            "clips": [
                {"start": "1", "end": 0.5, "extra": True},
                {"path": "b.mp4", "start": 2, "end": 1, "transition": "made_up", "position": "left", "id": "dup"},
                {"path": "c.mp4", "start": 0, "end": 1, "id": "dup"},
            ],
            "overlays": [{"path": "o.mp4", "start": 0, "end": 1, "timeline_start": 0, "track": 9}],
            "sfx": [{"path": "", "start": -1}],
        })
        for path in ("version", "title", "ratio", "bgm_volume", "", "clips[0].path", "clips[0].start", "clips[0]",
                     "clips[1].end", "clips[1].transition", "clips[1].position", "clips[2].id",
                     "overlays[0].track", "sfx[0].path", "sfx[0].start"):
            self.assertIn(path, errors, errors)
        self.assertIn("extra", errors["clips[0]"])
        self.assertIn("typo", errors[""])

    def test_rejects_non_object_and_wrong_types(self):
        self.assertIn("", self.errors([1, 2]))
        errors = self.errors({"clips": {}, "edit_plan": [], "edit_log": {}, "bgm_ducking": "yes", "title": 5})
        for path in ("clips", "edit_plan", "edit_log", "bgm_ducking", "title"):
            self.assertIn(path, errors, errors)
        self.assertIn("clips[0].volume", self.errors({"clips": [{"path": "a", "start": 0, "end": 1, "volume": True}]}))
        self.assertIn("clips[0].caption_size", self.errors({"clips": [{"path": "a", "start": 0, "end": 1, "caption_size": 4.5}]}))

    def test_envelope_keys_are_ignored(self):
        clean = validate_project_payload({**sample_payload(), "id": "x", "revision": 9, "created_at": "y",
                                          "updated_at": "z", "recovered_from_backup": True})
        self.assertNotIn("revision", clean)
        self.assertNotIn("id", clean)

    def test_non_finite_numbers_are_rejected_everywhere(self):
        nan, inf = float("nan"), float("inf")
        errors = self.errors({
            "bgm_volume": nan,
            "clips": [
                {"path": "a.mp4", "start": 0, "end": inf, "mask_feather": nan},
                {"path": "b.mp4", "start": 0, "end": 1, "title_fill_segments": [
                    {"path": "c.mp4", "start": "1", "duration": {}}, "x", {"path": "", "extra": 1}]},
            ],
            "edit_plan": {"scores": [1, nan]},
            "edit_log": [{"value": inf}],
        })
        for path in ("bgm_volume", "clips[0].end", "clips[0].mask_feather",
                     "clips[1].title_fill_segments[0].start", "clips[1].title_fill_segments[0].duration",
                     "clips[1].title_fill_segments[1]", "clips[1].title_fill_segments[2].path",
                     "clips[1].title_fill_segments[2]", "edit_plan.scores[1]", "edit_log[0].value"):
            self.assertIn(path, errors, errors)
        self.assertIn("clips[0].end", self.errors({"clips": [{"path": "a", "start": 0, "end": 10 ** 400}]}))
        clean = validate_project_payload({"clips": [{"path": "a", "start": 0, "end": 1, "title_fill_segments": [
            {"path": "b", "start": 0.5, "duration": 0.4, "name": "b"}]}]})
        self.assertEqual(clean["clips"][0]["title_fill_segments"][0]["duration"], 0.4)

    def test_old_desktop_version_is_upgraded(self):
        if not SAMPLE.exists():
            self.skipTest("sample project not present")
        raw = json.loads(SAMPLE.read_text(encoding="utf-8"))
        self.assertEqual(raw["version"], 3)
        clean = validate_project_payload(raw)
        self.assertEqual(clean["version"], SCHEMA_VERSION)
        self.assertEqual(len(clean["clips"]), len(raw["clips"]))
        self.assertEqual(clean["clips"][0]["caption_effect"], "clean")


class AtomicWriteTests(unittest.TestCase):
    def test_project_save_is_atomic(self):
        with tempfile.TemporaryDirectory(prefix="lingjian-atomic-") as folder:
            target = Path(folder) / "p.ljproject"
            Project("一").save(target)
            with mock.patch("video_editing_engine.os.replace", side_effect=OSError("boom")):
                with self.assertRaises(OSError):
                    Project("二").save(target)
            self.assertEqual(Project.load(target).title, "一")
            self.assertEqual([p.name for p in Path(folder).iterdir()], ["p.ljproject"])


class ProjectStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="lingjian-store-")
        self.addCleanup(self.tmp.cleanup)
        self.store = ProjectStore(self.tmp.name)
        # The damaged-file tests deliberately trigger recovery warnings; keep the runner output clean.
        logger = logging.getLogger("backend.project_store")
        previous = logger.level
        logger.setLevel(logging.ERROR)
        self.addCleanup(logger.setLevel, previous)

    def file(self, project_id, suffix=".ljproject"):
        return self.store.projects_dir / f"{project_id}{suffix}"

    def test_create_get_list_save_delete(self):
        record = self.store.create("我的工程")
        self.assertEqual(record.revision, 1)
        self.assertRegex(record.id, r"^[0-9a-f]{32}$")
        self.assertTrue(self.file(record.id).exists())
        self.assertEqual(self.store.get(record.id).to_dict(), record.to_dict())
        self.assertEqual([x["id"] for x in self.store.list()], [record.id])
        saved = self.store.save(record.id, sample_payload("改名"), 1)
        self.assertEqual((saved.revision, saved.project["title"], len(saved.project["clips"])), (2, "改名", 2))
        self.assertEqual(saved.created_at, record.created_at)
        self.assertEqual(self.store.save(record.id, saved.project, 2).revision, 3)
        summary = self.store.list()[0]
        self.assertEqual((summary["revision"], summary["clip_count"], summary["duration"]), (3, 2, 4.5))
        self.assertTrue(self.file(record.id, ".ljproject.bak").exists())
        self.assertEqual(json.loads(self.file(record.id, ".meta.json").read_text(encoding="utf-8"))["revision"], 3)
        self.store.delete(record.id)
        for suffix in (".ljproject", ".ljproject.bak", ".meta.json"):
            self.assertFalse(self.file(record.id, suffix).exists(), suffix)
        with self.assertRaises(ProjectNotFound):
            self.store.get(record.id)
        with self.assertRaises(ProjectNotFound):
            self.store.delete(record.id)
        self.assertEqual(self.store.list(), [])

    def test_create_can_import_a_desktop_project(self):
        record = self.store.create(project=sample_payload("导入"), ratio="16:9")
        self.assertEqual((record.project["title"], record.project["ratio"], len(record.project["clips"])), ("导入", "16:9", 2))
        if SAMPLE.exists():
            imported = self.store.create(project=json.loads(SAMPLE.read_text(encoding="utf-8")))
            self.assertEqual(imported.project["version"], SCHEMA_VERSION)
            self.assertEqual(self.store.get(imported.id).project, imported.project)

    def test_stale_revision_is_rejected_and_file_untouched(self):
        record = self.store.create("冲突")
        self.store.save(record.id, sample_payload("第一次"), 1)
        before = self.file(record.id).read_text(encoding="utf-8")
        with self.assertRaises(RevisionConflict) as ctx:
            self.store.save(record.id, sample_payload("第二次"), 1)
        self.assertEqual(ctx.exception.current.revision, 2)
        self.assertEqual(ctx.exception.current.project["title"], "第一次")
        self.assertEqual(ctx.exception.to_detail()["code"], "revision_conflict")
        self.assertEqual(self.file(record.id).read_text(encoding="utf-8"), before)
        with self.assertRaises(InvalidProject):
            self.store.save(record.id, sample_payload(), 0)

    def test_invalid_ids_never_touch_the_filesystem(self):
        for bad in ("../x", "/etc/passwd", "..", "", "ABCDEF0123456789ABCDEF0123456789", "0123456789abcdef",
                    "0123456789abcdef0123456789abcdef.ljproject", None, 12):
            with self.assertRaises(InvalidProjectId, msg=repr(bad)):
                self.store.get(bad)
            with self.assertRaises(InvalidProjectId, msg=repr(bad)):
                self.store.save(bad, sample_payload(), 1)
            with self.assertRaises(InvalidProjectId, msg=repr(bad)):
                self.store.delete(bad)
        self.assertEqual(sorted(p.name for p in Path(self.tmp.name).rglob("*")), ["projects"])

    def test_invalid_payload_is_rejected_before_any_write(self):
        record = self.store.create("校验")
        with self.assertRaises(InvalidProject) as ctx:
            self.store.save(record.id, {"clips": [{"path": "a.mp4", "start": 3, "end": 1}]}, 1)
        self.assertEqual(ctx.exception.errors[0]["path"], "clips[0].end")
        self.assertEqual(self.store.get(record.id).revision, 1)
        with self.assertRaises(InvalidProject):
            self.store.create(project=["not", "a", "dict"])
        with self.assertRaises(InvalidProject):
            self.store.create(title="x" * 121)

    def test_failed_write_keeps_old_file_and_leaves_no_temp(self):
        record = self.store.create("原子")
        self.store.save(record.id, sample_payload("旧版本"), 1)
        before = self.file(record.id).read_text(encoding="utf-8")
        with mock.patch("video_editing_engine.os.replace", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                self.store.save(record.id, sample_payload("写到一半"), 2)
        self.assertEqual(self.file(record.id).read_text(encoding="utf-8"), before)
        self.assertEqual([p.name for p in self.store.projects_dir.iterdir() if ".tmp-" in p.name], [])
        current = self.store.get(record.id)
        self.assertEqual((current.revision, current.project["title"]), (2, "旧版本"))
        self.assertEqual(self.store.save(record.id, sample_payload("恢复后"), 2).revision, 3)

    def test_damaged_main_file_is_served_from_backup(self):
        record = self.store.create("损坏")
        self.store.save(record.id, sample_payload("好的版本"), 1)
        self.file(record.id).write_text('{"id": "half written', encoding="utf-8")
        recovered = self.store.get(record.id)
        self.assertTrue(recovered.recovered_from_backup)
        # The backup body differs from the last write, so it is served as a newer revision (2 -> 3), never an older one.
        self.assertEqual((recovered.revision, recovered.project["title"]), (3, "损坏"))
        with self.assertRaises(RevisionConflict):
            self.store.save(record.id, sample_payload("拿着损坏前 revision 的客户端"), 2)
        # Saving on top of the recovered copy must not overwrite the good backup with the damaged file.
        saved = self.store.save(record.id, sample_payload("修复"), 3)
        self.assertEqual(saved.revision, 4)
        self.assertFalse(self.store.get(record.id).recovered_from_backup)
        backup = json.loads(self.file(record.id, ".ljproject.bak").read_text(encoding="utf-8"))
        self.assertEqual(backup["title"], "损坏")

    def test_damaged_file_without_backup_is_reported_and_skipped_in_listing(self):
        record = self.store.create("无备份")
        self.file(record.id).write_text("not json", encoding="utf-8")
        with self.assertRaises(ProjectCorrupt):
            self.store.get(record.id)
        self.assertEqual(self.store.list(), [])

    def test_desktop_application_can_open_store_files(self):
        record = self.store.create(project=sample_payload("桌面兼容"))
        desktop = Project.load(self.file(record.id))
        self.assertEqual(desktop.to_dict(), record.project)
        # A desktop save in place strips the envelope; it must count as a newer revision, not reset to 1.
        desktop.title = "桌面端另存"
        desktop.save(self.file(record.id))
        external = self.store.get(record.id)
        self.assertEqual((external.project["title"], external.revision), ("桌面端另存", 2))
        self.assertEqual(external.created_at, record.created_at)
        with self.assertRaises(RevisionConflict):
            self.store.save(record.id, sample_payload("拿着旧 revision 的网页端"), 1)
        self.assertEqual(self.store.get(record.id).project["title"], "桌面端另存")
        self.assertEqual(self.store.save(record.id, sample_payload("网页端合并后"), 2).revision, 3)
        self.assertEqual(self.store.get(record.id).revision, 3)

    def test_crash_between_project_and_metadata_write_stays_consistent(self):
        record = self.store.create("半途")
        self.store.save(record.id, sample_payload("旧版本"), 1)
        real_replace = os.replace
        calls = []

        def flaky(src, dst):
            calls.append(str(dst))
            if len(calls) == 2:  # the project file is already replaced; the metadata write dies
                raise OSError("power loss")
            return real_replace(src, dst)

        with mock.patch("video_editing_engine.os.replace", side_effect=flaky):
            with self.assertRaises(OSError):
                self.store.save(record.id, sample_payload("新版本"), 2)
        current = self.store.get(record.id)
        self.assertEqual((current.revision, current.project["title"]), (3, "新版本"))
        with self.assertRaises(RevisionConflict):
            self.store.save(record.id, sample_payload("旧客户端"), 2)
        self.assertEqual(self.store.save(record.id, sample_payload("继续"), 3).revision, 4)
        self.assertEqual(self.store.get(record.id).revision, 4)

    def test_concurrent_saves_exactly_one_wins(self):
        record = self.store.create("并发")
        barrier = threading.Barrier(2)
        results = []

        def worker(title):
            barrier.wait()
            try:
                results.append(self.store.save(record.id, sample_payload(title), 1).revision)
            except RevisionConflict:
                results.append("conflict")

        threads = [threading.Thread(target=worker, args=(f"写入者{i}",)) for i in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(sorted(map(str, results)), ["2", "conflict"])
        self.assertEqual(self.store.get(record.id).revision, 2)


if __name__ == "__main__":
    unittest.main()
