import copy
import json
import tempfile
import threading
import time
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from ai_story_planner import APIConfig, AIRequestError
from ai_workflow import AIWorkflow, MediaSource, ProjectSnapshot, RevisionConflict, WorkflowError
from video_editing_engine import Clip, OverlayClip, Project, SFXCue


class MemoryBackend:
    """Test-only adapter illustrating atomic revision checks, not production storage."""
    def __init__(self, root):
        self.lock = threading.Lock()
        self.revision = 1
        self.commits = 0
        self.allowed = True
        path = Path(root) / 'footage.mp4'
        path.write_bytes(b'fixture-media')
        self.source = MediaSource('media-1', path, 'DJI_20260919080000.mp4', 20.0, False, '20260919080000')
        self.project = Project('用户作品', clips=[Clip(str(path), 1, 5, caption='用户手写字幕', has_audio=False)],
                               bgm='keep.wav', overlays=[OverlayClip(str(path), 1, 3, 0)],
                               sfx=[SFXCue('cue.wav', 1)])

    def access(self, project_id, owner_id):
        if not self.allowed or project_id != 'project-1' or owner_id != 'owner-1':
            raise WorkflowError('not_found', '工程不可用。', 404)

    def get_project(self, project_id, owner_id):
        self.access(project_id, owner_id)
        with self.lock:
            return ProjectSnapshot(copy.deepcopy(self.project), self.revision)

    def resolve_media(self, project_id, media_id, owner_id):
        self.access(project_id, owner_id)
        if media_id != self.source.id:
            raise WorkflowError('not_found', '素材不可用。', 404)
        return self.source

    def commit_project(self, project_id, owner_id, project, expected_revision):
        self.access(project_id, owner_id)
        with self.lock:
            if self.revision != expected_revision:
                raise RevisionConflict()
            self.project = copy.deepcopy(project)
            self.revision += 1
            self.commits += 1
            return ProjectSnapshot(copy.deepcopy(self.project), self.revision)


def fake_local(ffmpeg, source, checkpoint):
    checkpoint()
    return [dict(start=0., end=4., score=80, caption='', reason='本地镜头', role='setup'),
            dict(start=7., end=11., score=90, caption='', reason='本地镜头', role='outro')]


def completed(workflow, plan_id):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        result = workflow.get('project-1', plan_id, 'owner-1')
        if result['status'] not in ('queued', 'running'):
            return result
        time.sleep(.01)
    raise AssertionError('AI job did not finish')


class AIWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.backend = MemoryBackend(self.folder.name)
        self.workflow = self.make_workflow()

    def make_workflow(self, **kwargs):
        workflow = AIWorkflow(self.backend, 'unused-ffmpeg', local_analyzer=fake_local, **kwargs)
        self.addCleanup(workflow.close)
        return workflow

    def create(self, workflow=None, **kwargs):
        params = dict(media_ids=['media-1'], revision=1, target_duration=8)
        params.update(kwargs)
        workflow = workflow or self.workflow
        return workflow.create('project-1', 'owner-1', **params)

    def ready(self, workflow=None, **kwargs):
        workflow = workflow or self.workflow
        job = self.create(workflow, **kwargs)
        result = completed(workflow, job['id'])
        self.assertEqual(result['status'], 'ready', result)
        return result

    def test_preview_apply_undo_restores_full_project_and_silent_audio(self):
        before = self.backend.project.to_dict()
        result = self.ready()
        self.assertEqual(self.backend.project.to_dict(), before)
        self.assertEqual(self.backend.commits, 0)
        self.assertNotIn(str(self.backend.source.path), json.dumps(result))
        self.assertNotIn('source_path', json.dumps(result))
        self.assertEqual(result['result']['changes']['remove_overlays'], 1)
        result['result']['shots'][0]['caption'] = '客户端篡改'
        applied = self.workflow.apply('project-1', result['id'], 'owner-1', revision=1, confirm=True)
        self.assertEqual(applied['revision'], 2)
        self.assertFalse(self.backend.project.clips[0].has_audio)
        self.assertNotEqual(self.backend.project.clips[0].caption, '客户端篡改')
        self.assertEqual(self.backend.project.bgm, 'keep.wav', 'existing background music is kept')
        self.assertTrue(all(overlay.ai_selected for overlay in self.backend.project.overlays), 'old overlays are replaced by the plan\'s own layers')
        self.assertEqual(len(self.backend.project.overlays), result['result']['changes']['add_overlays'])
        self.assertEqual(len(self.backend.project.sfx), result['result']['changes']['add_sound_effects'])
        self.assertTrue(all(Path(cue.path).exists() for cue in self.backend.project.sfx))
        self.assertEqual(self.backend.project.edit_log[-1]['opening'], result['result']['creative']['preset_id'])
        undone = self.workflow.undo('project-1', result['id'], 'owner-1', revision=2)
        self.assertEqual(undone['revision'], 3)
        self.assertEqual(self.backend.project.to_dict(), before)

    def test_apply_requires_explicit_confirmation_and_is_single_transaction(self):
        result = self.ready()
        for value in (False, None, 1, 'true'):
            with self.subTest(value=value), self.assertRaises(WorkflowError):
                self.workflow.apply('project-1', result['id'], 'owner-1', revision=1, confirm=value)
        self.assertEqual(self.backend.commits, 0)
        self.workflow.apply('project-1', result['id'], 'owner-1', revision=1, confirm=True)
        with self.assertRaises(WorkflowError):
            self.workflow.apply('project-1', result['id'], 'owner-1', revision=1, confirm=True)
        self.assertEqual(self.backend.commits, 1)

    def test_concurrent_project_edit_blocks_apply_without_data_loss(self):
        result = self.ready()
        changed = copy.deepcopy(self.backend.project)
        changed.title = '另一位成员修改'
        self.backend.commit_project('project-1', 'owner-1', changed, 1)
        with self.assertRaises(RevisionConflict):
            self.workflow.apply('project-1', result['id'], 'owner-1', revision=1, confirm=True)
        self.assertEqual(self.backend.project.title, changed.title)
        self.assertEqual(self.backend.commits, 1)

    def test_concurrent_edit_blocks_undo(self):
        result = self.ready()
        self.workflow.apply('project-1', result['id'], 'owner-1', revision=1, confirm=True)
        self.backend.commit_project('project-1', 'owner-1', self.backend.project, 2)
        with self.assertRaises(RevisionConflict):
            self.workflow.undo('project-1', result['id'], 'owner-1', revision=2)

    def test_other_owner_project_and_revoked_access_cannot_read_or_apply(self):
        result = self.ready()
        for project_id, owner in [('project-1', 'owner-2'), ('project-2', 'owner-1')]:
            with self.assertRaises(WorkflowError) as raised:
                self.workflow.get(project_id, result['id'], owner)
            self.assertEqual(raised.exception.status, 404)
        self.backend.allowed = False
        with self.assertRaises(WorkflowError):
            self.workflow.apply('project-1', result['id'], 'owner-1', revision=1, confirm=True)
        self.assertEqual(self.backend.commits, 0)

    def test_changed_or_missing_media_blocks_apply(self):
        for change in ('rewrite', 'delete', 'metadata'):
            with self.subTest(change=change):
                self.backend.source.path.write_bytes(b'fixture-media')
                result = self.ready()
                if change == 'rewrite':
                    self.backend.source.path.write_bytes(b'new-and-different-media')
                elif change == 'delete':
                    self.backend.source.path.unlink()
                else:
                    self.backend.source = replace(self.backend.source, duration=19)
                with self.assertRaises(WorkflowError):
                    self.workflow.apply('project-1', result['id'], 'owner-1', revision=1, confirm=True)
                self.assertEqual(self.backend.commits, 0)

    def test_invalid_inputs_rejected_before_work(self):
        for params in [{'media_ids': []}, {'media_ids': ['../secret']}, {'media_ids': ['media-1'] * 2},
                       {'target_duration': float('nan')}, {'target_duration': float('inf')},
                       {'target_duration': True}, {'target_duration': 181}, {'revision': True},
                       {'prompt': 'x' * 2001}, {'mode': 'unknown'}, {'revision': 99}]:
            with self.subTest(params=params), self.assertRaises(WorkflowError):
                self.create(**params)
        self.assertEqual(self.backend.commits, 0)

    def test_cloud_consent_and_server_key_required(self):
        with patch('ai_workflow.analyze_video') as analyze:
            with self.assertRaises(WorkflowError) as raised:
                self.create(mode='cloud')
            self.assertEqual(raised.exception.code, 'consent_required')
            with self.assertRaises(WorkflowError) as raised:
                self.create(mode='cloud', cloud_consent=True)
            self.assertEqual(raised.exception.code, 'cloud_unavailable')
            analyze.assert_not_called()

    def test_cloud_failure_is_explicit_and_does_not_fallback_or_expose_secret(self):
        cfg = APIConfig(api_key='test-private-token')
        workflow = self.make_workflow(cloud_config=cfg)
        with patch('ai_workflow.analyze_video', side_effect=RuntimeError('test-private-token /private/source.mov')):
            result = completed(workflow, self.create(workflow, mode='cloud', cloud_consent=True)['id'])
        self.assertEqual(result['status'], 'failed')
        self.assertNotIn(cfg.api_key, json.dumps(result))
        self.assertNotIn('/private', json.dumps(result))
        self.assertEqual(self.backend.commits, 0)
        self.assertNotIn(cfg.api_key, repr(cfg))

    def test_cloud_second_step_failure_stays_failed(self):
        workflow = self.make_workflow(cloud_config=APIConfig(api_key='test-key'))
        with patch('ai_workflow.analyze_video', return_value=fake_local('', self.backend.source, lambda: None)), \
             patch('ai_workflow.plan_sequence', side_effect=AIRequestError('AI 服务受限。', 'rate_limited', True)) as planner:
            result = completed(workflow, self.create(workflow, mode='cloud', cloud_consent=True)['id'])
        self.assertEqual(result['status'], 'failed')
        self.assertTrue(result['error']['retryable'])
        self.assertFalse(planner.call_args.kwargs['allow_fallback'])

    def test_local_mode_never_calls_cloud(self):
        with patch('ai_workflow.analyze_video') as analyze, patch('ai_workflow.plan_sequence') as planner:
            self.ready()
            analyze.assert_not_called()
            planner.assert_not_called()

    def test_cancel_running_task_and_bounded_queue(self):
        started, release = threading.Event(), threading.Event()
        workflow = self.make_workflow(max_workers=1, max_pending=0)
        def slow(ffmpeg, source, checkpoint):
            started.set()
            release.wait(3)
            checkpoint()
            return fake_local(ffmpeg, source, checkpoint)
        workflow.local_analyzer = slow
        result = self.create(workflow)
        self.assertTrue(started.wait(2))
        try:
            with self.assertRaises(WorkflowError) as raised:
                self.create(workflow)
            self.assertEqual(raised.exception.status, 429)
            cancelled = workflow.cancel('project-1', result['id'], 'owner-1')
            self.assertEqual(cancelled['status'], 'cancelled')
        finally:
            release.set()
        workflow.close()
        self.assertEqual(workflow.get('project-1', result['id'], 'owner-1')['status'], 'cancelled')
        self.assertEqual(self.backend.commits, 0)

    def test_result_carries_a_readable_report(self):
        result = self.ready()
        report = result['result']['report']
        self.assertIn('本地', report['story'])
        self.assertEqual(report['order_basis'], 'capture_time')
        self.assertTrue(any('冷开场' in line for line in report['structure']))
        self.assertTrue(any('本地分析' in line for line in report['techniques']))
        self.assertEqual(report['sources'][0]['shots_used'], len(result['result']['shots']))
        self.assertEqual(report['sources'][0]['capture_time'], '2026-09-19 08:00:00')
        self.assertIn('镜头方案', report['report_text'])
        self.assertNotIn(str(self.backend.source.path), report['report_text'])
        self.assertEqual(result['result']['shots'][0]['role'], 'hook')
        self.assertIn('capture_stamp', result['result']['shots'][0])

    def test_chronological_opening_and_duplicate_caption_cleanup(self):
        def talky(ffmpeg, source, checkpoint):
            return [dict(start=0., end=3., score=70, caption='同一句话', reason='第一段', role='setup'),
                    dict(start=4., end=7., score=95, caption='同一句话', reason='第二段', role='hook'),
                    dict(start=9., end=12., score=60, caption='结尾', reason='第三段', role='outro')]
        workflow = AIWorkflow(self.backend, 'unused-ffmpeg', local_analyzer=talky)
        self.addCleanup(workflow.close)
        cold_open = completed(workflow, self.create(workflow, target_duration=9)['id'])
        self.assertEqual(cold_open['result']['shots'][0]['start'], 4.0, 'default keeps the best shot as a cold open')
        ordered = completed(workflow, self.create(workflow, target_duration=9, opening='chronological', style='纪录片')['id'])
        shots = ordered['result']['shots']
        self.assertEqual([shot['start'] for shot in shots], [0.0, 4.0, 9.0])
        self.assertEqual([shot['role'] for shot in shots], ['setup', 'development', 'outro'])
        self.assertEqual([shot['caption'] for shot in shots], ['同一句话', '', '结尾'])
        self.assertTrue(any('对白相同' in note for note in ordered['result']['repairs']))
        report = ordered['result']['report']
        self.assertEqual(report['opening'], 'chronological')
        self.assertTrue(any('纯时间顺序' in line for line in report['structure']))
        self.assertTrue(any('纪录片' in line for line in report['techniques']))
        with self.assertRaises(WorkflowError):
            self.create(workflow, opening='random')

    def test_sources_without_capture_time_follow_selection_order(self):
        class TwoSources(MemoryBackend):
            def __init__(inner, root):
                super().__init__(root)
                second = Path(root) / 'second.mp4'
                second.write_bytes(b'fixture-media-2')
                inner.sources = {'media-1': replace(inner.source, capture_order=''),
                                 'media-2': MediaSource('media-2', second, 'second.mp4', 12.0, False, '')}
            def resolve_media(inner, project_id, media_id, owner_id):
                inner.access(project_id, owner_id)
                if media_id not in inner.sources:
                    raise WorkflowError('not_found', '素材不可用。', 404)
                return inner.sources[media_id]
        backend = TwoSources(self.folder.name)
        workflow = AIWorkflow(backend, 'unused-ffmpeg', local_analyzer=fake_local)
        self.addCleanup(workflow.close)
        job = workflow.create('project-1', 'owner-1', media_ids=['media-2', 'media-1'], revision=1,
                              target_duration=16, opening='chronological')
        result = completed(workflow, job['id'])
        self.assertEqual(result['status'], 'ready', result)
        order = [shot['media_id'] for shot in result['result']['shots']]
        self.assertEqual(order[0], 'media-2', 'selection order stands in for missing capture times')
        self.assertEqual(order, sorted(order, key=lambda value: ['media-2', 'media-1'].index(value)))
        self.assertEqual(result['result']['report']['order_basis'], 'selection')
        self.assertEqual(result['result']['report']['sources'][0]['capture_time'], '')

    def test_opening_presets_switch_as_a_set_and_music_fills_an_empty_project(self):
        self.backend.project.bgm = ''
        result = self.ready(style='旅行叙事')
        creative = result['result']['creative']
        self.assertEqual(creative['preset_id'], 'cinematic_window', 'smart recommendation for travel')
        self.assertEqual(creative['requested'], 'smart')
        self.assertIn('smart', [item['value'] for item in result['result']['opening_presets']])
        self.assertEqual(result['result']['global_direction']['music_name'], '旅行微风')
        self.assertEqual(result['result']['changes']['music'], '旅行微风')
        self.assertIn('高级开篇', result['result']['report']['report_text'])
        self.assertIn('全片创意编排', result['result']['report']['report_text'])
        self.assertTrue(result['result']['validation']['ok'])

        switched = self.workflow.set_opening('project-1', result['id'], 'owner-1', preset='minimal_film')
        self.assertEqual(switched['result']['creative']['preset_id'], 'minimal_film')
        self.assertEqual(switched['result']['creative']['requested'], 'minimal_film')
        self.assertEqual([shot['start'] for shot in switched['result']['shots']],
                         [shot['start'] for shot in result['result']['shots']], 'switching the opening never reorders the cut')
        with self.assertRaises(WorkflowError):
            self.workflow.set_opening('project-1', result['id'], 'owner-1', preset='nope')

        applied = self.workflow.apply('project-1', result['id'], 'owner-1', revision=1, confirm=True)
        self.assertEqual(applied['status'], 'applied')
        self.assertEqual(self.backend.project.bgm_id, 'travel_breeze')
        self.assertTrue(self.backend.project.bgm.endswith('travel_breeze.wav'))
        self.assertEqual(self.backend.project.edit_log[-1]['opening'], 'minimal_film')
        self.assertEqual(self.backend.project.clips[0].transition, 'none')
        with self.assertRaises(WorkflowError):
            self.workflow.set_opening('project-1', result['id'], 'owner-1', preset='smart')

    def test_expired_plan_is_unavailable(self):
        result = self.ready()
        self.workflow._records[result['id']].finished.wait(2)
        self.workflow._records[result['id']].expires_at = 0
        with self.assertRaises(WorkflowError) as raised:
            self.workflow.get('project-1', result['id'], 'owner-1')
        self.assertEqual(raised.exception.status, 404)


if __name__ == '__main__':
    unittest.main()
