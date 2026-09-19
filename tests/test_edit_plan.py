import unittest

from video_editing_engine import Clip, Project
from edit_plan import (
    apply_controlled_tool,
    build_edit_plan,
    plan_to_clips,
    project_quality_gate,
    validate_edit_plan,
)


def analysis(name, stamp, duration=90):
    return {"meta": {"path": name, "name": name, "duration": duration,
                     "has_audio": True, "capture_order": stamp}, "segments": []}


class EditProtocol44Tests(unittest.TestCase):
    def setUp(self):
        self.analyses = [
            analysis("DJI_20260825045333_0306_D.MP4", "20260825045333"),
            analysis("DJI_20260825045608_0307_D.MP4", "20260825045608"),
            analysis("DJI_20260825045819_0308_D.MP4", "20260825045819"),
        ]

    def sequence(self):
        return [
            {"source_index": 2, "start": 70, "end": 73, "role": "hook",
             "caption": "最后发生了什么", "reason": "结果钩子", "transition": "cut"},
            {"source_index": 0, "start": 2, "end": 7, "role": "setup",
             "caption": "从这里开始", "reason": "建立目标", "transition": "cut"},
            {"source_index": 1, "start": 8, "end": 13, "role": "development",
             "caption": "继续向前", "reason": "行动推进", "transition": "dissolve"},
            {"source_index": 2, "start": 15, "end": 20, "role": "outro",
             "caption": "抵达终点", "reason": "结果回收", "transition": "fade"},
        ]

    def test_hook_may_preview_future_but_body_is_chronological(self):
        plan = build_edit_plan(self.sequence(), self.analyses, 60, "按真实拍摄顺序", "test")
        self.assertTrue(plan["capture_order_locked"])
        self.assertTrue(plan["validation"]["ok"])
        self.assertEqual(plan["validation"]["chronology_ratio"], 1.0)

    def test_reversed_body_is_automatically_repaired(self):
        seq = self.sequence()
        seq[1], seq[2] = seq[2], seq[1]
        plan = build_edit_plan(seq, self.analyses, 60, "按顺序拍摄", "test")
        self.assertTrue(plan["validation"]["ok"])
        self.assertEqual(plan["validation"]["chronology_ratio"],1.0)
        self.assertTrue(any("自动按真实拍摄时间" in x for x in plan["validation"]["repairs"]))
        self.assertEqual(plan["decisions"][0]["role"],"hook")
        self.assertEqual([x["source_index"] for x in plan["decisions"][1:]],[0,1,2])

    def test_unknown_transition_fails_closed_to_cut(self):
        seq = self.sequence()
        seq[2]["transition"] = "made_up_transition"
        plan = build_edit_plan(seq, self.analyses, 60, "时间顺序", "test")
        self.assertEqual(plan["decisions"][2]["transition"], "none")
        self.assertTrue(plan["validation"]["ok"])
        self.assertTrue(plan["validation"]["repairs"])

    def test_source_overrun_and_duplicate_are_blocked(self):
        plan = build_edit_plan(self.sequence(), self.analyses, 60, "时间顺序", "test")
        plan["decisions"][1]["end"] = 999
        plan["decisions"].append(dict(plan["decisions"][2]))
        report = validate_edit_plan(plan)
        self.assertFalse(report["ok"])
        self.assertTrue(any("超出原素材" in x for x in report["blockers"]))
        self.assertTrue(any("完全重复" in x for x in report["blockers"]))

    def test_plan_becomes_editable_clips_with_provenance(self):
        plan = build_edit_plan(self.sequence(), self.analyses, 60, "时间顺序", "test")
        clips = plan_to_clips(plan, Clip)
        self.assertEqual(len(clips), 4)
        self.assertTrue(all(c.ai_selected for c in clips))
        self.assertEqual(clips[0].role, "hook")
        self.assertEqual(clips[1].reason, "建立目标")

    def test_export_gate_blocks_unreadable_caption(self):
        plan = build_edit_plan(self.sequence(), self.analyses, 60, "时间顺序", "test")
        project = Project(clips=plan_to_clips(plan, Clip), edit_plan=plan)
        project.clips[1].end = project.clips[1].start + .5
        project.clips[1].caption = "这是一条在半秒钟内绝对无法正常阅读完成的超长字幕"
        report = project_quality_gate(project)
        self.assertFalse(report["ok"])
        self.assertTrue(any("不可读" in x for x in report["blockers"]))

    def test_controlled_tool_returns_reversible_transaction(self):
        plan = build_edit_plan(self.sequence(), self.analyses, 60, "时间顺序", "test")
        project = Project(clips=plan_to_clips(plan, Clip), edit_plan=plan)
        tx = apply_controlled_tool(project, "set_caption", {
            "clip_id": project.clips[1].id, "text": "新的忠实字幕",
        })
        self.assertNotEqual(tx["before"], tx["after"])
        self.assertEqual(project.clips[1].caption, "新的忠实字幕")
        restored = Project.from_dict(tx["before"])
        self.assertEqual(restored.clips[1].caption, "从这里开始")

    def test_controlled_move_cannot_break_capture_order(self):
        plan = build_edit_plan(self.sequence(), self.analyses, 60, "时间顺序", "test")
        project = Project(clips=plan_to_clips(plan, Clip), edit_plan=plan)
        with self.assertRaisesRegex(ValueError, "真实拍摄顺序"):
            apply_controlled_tool(project, "move_clip_with_order_guard", {
                "from_index": 3, "to_index": 1,
            }, capture_order_locked=True)

    def test_project_v2_load_is_backward_compatible(self):
        old = {"version": 2, "title": "旧工程", "clips": [{
            "path": "old.mp4", "start": 0, "end": 3, "name": "old",
        }]}
        project = Project.from_dict(old)
        self.assertEqual(project.title, "旧工程")
        self.assertEqual(project.edit_plan, {})
        self.assertEqual(project.clips[0].role, "")


if __name__ == "__main__":
    unittest.main()
