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
        self.assertEqual(self.backend.project.bgm, 'keep.wav')
        self.assertEqual(self.backend.project.overlays, [])
        self.assertEqual(self.backend.project.sfx, [])
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

    def test_expired_plan_is_unavailable(self):
        result = self.ready()
        self.workflow._records[result['id']].finished.wait(2)
        self.workflow._records[result['id']].expires_at = 0
        with self.assertRaises(WorkflowError) as raised:
            self.workflow.get('project-1', result['id'], 'owner-1')
        self.assertEqual(raised.exception.status, 404)


if __name__ == '__main__':
    unittest.main()
