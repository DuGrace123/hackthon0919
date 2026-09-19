"""Member 1 + Member 4: actual ProjectStore, mounted HTTP routes and FFmpeg."""
import copy
import json
import logging
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from ai_story_planner import run_analysis_command
from backend.api import create_app
from backend.project_store import InvalidProject, ProjectStore, RevisionConflict, project_version_token
from tests.test_ai_media_analysis import FFMPEG
from video_editing_engine import Clip, Project


class StoreIntegrationGuards(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = ProjectStore(self.tmp.name)

    def test_content_token_blocks_same_revision_desktop_replacement(self):
        original = self.store.create('原工程')
        token = project_version_token(original)
        # Desktop save has no revision envelope, so ProjectStore reads revision 1 again.
        file = self.store.projects_dir / (original.id + '.ljproject')
        Project('桌面端新修改').save(file)
        self.assertEqual(self.store.get(original.id).revision, 1)
        with self.assertRaises(RevisionConflict):
            self.store.save(original.id, original.project, 1, expected_token=token)
        self.assertEqual(self.store.get(original.id).project['title'], '桌面端新修改')

    def test_nonfinite_payload_is_rejected_before_persistence(self):
        for project in [{'bgm_volume': float('nan')}, {'edit_plan': {'score': float('inf')}},
                        {'clips': [{'path': 'a.mp4', 'start': 0, 'end': float('nan')}]}]:
            with self.subTest(project=project), self.assertRaises(InvalidProject):
                self.store.create(project=project)
        self.assertEqual(self.store.list(), [])

    def test_origin_and_local_network_guards(self):
        with TestClient(create_app(self.store, ffmpeg=''), base_url='http://127.0.0.1',
                        client=('127.0.0.1', 1234)) as client:
            capability = client.get('/api/v1/ai/capabilities')
            self.assertEqual(capability.status_code, 200)
            self.assertFalse(capability.json()['local_available'])
            denied = client.post('/api/v1/projects', json={}, headers={'Origin': 'https://untrusted.example'})
            self.assertEqual(denied.status_code, 403)
            self.assertEqual(self.store.list(), [])
            self.assertEqual(client.get('/api/v1/ai/capabilities', headers={'Host': 'untrusted.example'}).status_code, 403)
        with TestClient(create_app(self.store, ffmpeg=''), base_url='http://127.0.0.1',
                        client=('192.0.2.1', 1234)) as remote:
            self.assertEqual(remote.get('/api/v1/ai/capabilities').status_code, 403)


@unittest.skipUnless(FFMPEG, 'Install FFmpeg or set FIGSTUDIO_TEST_FFMPEG')
class BackendAIIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixtures = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.fixtures.cleanup)
        cls.video = Path(cls.fixtures.name) / 'source.mp4'
        run_analysis_command([FFMPEG, '-y', '-v', 'error', '-f', 'lavfi', '-i',
                              'testsrc2=size=160x90:rate=12', '-t', '8', '-c:v', 'libx264',
                              '-pix_fmt', 'yuv420p', str(cls.video)])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = ProjectStore(self.tmp.name)
        self.app = create_app(self.store, ffmpeg=FFMPEG)
        self.client = TestClient(self.app, base_url='http://127.0.0.1', client=('127.0.0.1', 1234))
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)
        self.media = self.store.workspace / 'media' / 'source.mp4'
        shutil.copy2(self.video, self.media)
        project = Project('待剪辑的工程', clips=[Clip('media/source.mp4', 0, 8, '旅行素材', has_audio=False)])
        response = self.client.post('/api/v1/projects', json={'project': project.to_dict()})
        self.assertEqual(response.status_code, 201, response.text)
        self.record = response.json()
        self.pid = self.record['id']
        self.url = f'/api/v1/projects/{self.pid}'

    def ready(self):
        sources = self.client.get(self.url + '/ai/sources')
        self.assertEqual(sources.status_code, 200, sources.text)
        data = sources.json()
        self.assertEqual(len(data['items']), 1, data)
        self.assertNotIn(str(self.store.workspace), sources.text)
        request = {'revision': data['revision'], 'media_ids': [data['items'][0]['id']], 'target_duration': 5}
        created = self.client.post(self.url + '/ai/plans', json=request)
        self.assertEqual(created.status_code, 202, created.text)
        plan_url = self.url + '/ai/plans/' + created.json()['id']
        for _ in range(500):
            result = self.client.get(plan_url).json()
            if result['status'] not in ('queued', 'running'):
                self.assertEqual(result['status'], 'ready', result)
                return plan_url, result
            time.sleep(.01)
        self.fail('Plan did not complete')

    def test_full_local_flow_persists_and_undo_restores_original(self):
        plan_url, result = self.ready()
        self.assertEqual(self.store.get(self.pid).project, self.record['project'])
        applied = self.client.post(plan_url + '/apply', json={'revision': 1, 'confirm': True})
        self.assertEqual(applied.status_code, 200, applied.text)
        self.assertEqual(applied.json()['revision'], 2)
        persisted = ProjectStore(self.tmp.name).get(self.pid)
        self.assertEqual(persisted.revision, 2)
        self.assertGreater(len(persisted.project['clips']), 0)
        self.assertFalse(persisted.project['clips'][0]['has_audio'])
        self.assertLessEqual(Project.from_dict(persisted.project).duration, 5)
        undone = self.client.post(plan_url + '/undo', json={'revision': 2})
        self.assertEqual(undone.status_code, 200, undone.text)
        restored = ProjectStore(self.tmp.name).get(self.pid)
        self.assertEqual(restored.revision, 3)
        self.assertEqual(restored.project, self.record['project'])

    def test_manual_save_wins_over_old_plan(self):
        plan_url, _ = self.ready()
        changed = copy.deepcopy(self.record['project'])
        changed['title'] = '成员手动修改'
        self.assertEqual(self.client.put(self.url, json={'revision': 1, 'project': changed}).status_code, 200)
        response = self.client.post(plan_url + '/apply', json={'revision': 1, 'confirm': True})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['detail']['code'], 'revision_conflict')
        self.assertEqual(self.store.get(self.pid).project['title'], changed['title'])

    def test_backup_recovery_cannot_resurrect_old_plan(self):
        plan_url, _ = self.ready()
        changed = copy.deepcopy(self.record['project'])
        changed['title'] = '新的人工修改'
        self.store.save(self.pid, changed, 1)
        (self.store.projects_dir / (self.pid + '.ljproject')).write_text('corrupt')
        with patch.object(logging.getLogger('backend.project_store'), 'warning'):
            recovered = self.store.get(self.pid)
            self.assertEqual(recovered.revision, 1)
            self.assertTrue(recovered.recovered_from_backup)
            response = self.client.post(plan_url + '/apply', json={'revision': 1, 'confirm': True})
        self.assertEqual(response.status_code, 409, response.text)

    def test_sources_deduplicate_and_reject_outside_paths_and_symlinks(self):
        outside = Path(self.tmp.name).parent / (Path(self.tmp.name).name + '-outside.mp4')
        shutil.copy2(self.video, outside)
        self.addCleanup(outside.unlink, missing_ok=True)
        link = self.media.parent / 'external-link.mp4'
        link.symlink_to(outside)
        project = Project('边界', clips=[Clip('media/source.mp4', 0, 8), Clip(str(self.media), 1, 4),
                                         Clip(str(outside), 0, 4), Clip(str(link), 0, 4)])
        self.store.save(self.pid, project.to_dict(), 1)
        response = self.client.get(self.url + '/ai/sources')
        self.assertEqual(len(response.json()['items']), 1)
        self.assertEqual(len(response.json()['unavailable']), 2)
        self.assertNotIn(str(outside), response.text)
        other = self.client.post('/api/v1/projects', json={}).json()['id']
        request = {'revision': 1, 'media_ids': [response.json()['items'][0]['id']], 'target_duration': 5}
        self.assertEqual(self.client.post(f'/api/v1/projects/{other}/ai/plans', json=request).status_code, 404)

    def test_captions_match_store_limit_before_preview_and_apply(self):
        def long_caption(ffmpeg, source, checkpoint):
            return [dict(start=0., end=4., score=90, caption='字' * 180, reason='镜头', role='setup')]
        self.app.state.ai_workflow.local_analyzer = long_caption
        plan_url, result = self.ready()
        self.assertEqual(len(result['result']['shots'][0]['caption']), 120)
        response = self.client.post(plan_url + '/apply', json={'revision': 1, 'confirm': True})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(self.store.get(self.pid).project['clips'][0]['caption']), 120)

    def test_failed_disk_write_keeps_original_project_and_allows_retry(self):
        plan_url, _ = self.ready()
        with patch('video_editing_engine.os.replace', side_effect=OSError('disk full')):
            failed = self.client.post(plan_url + '/apply', json={'revision': 1, 'confirm': True})
        self.assertEqual(failed.status_code, 503, failed.text)
        self.assertEqual(self.store.get(self.pid).project, self.record['project'])
        self.assertEqual(self.client.get(plan_url).json()['status'], 'ready')
        retry = self.client.post(plan_url + '/apply', json={'revision': 1, 'confirm': True})
        self.assertEqual(retry.status_code, 200, retry.text)

    def test_restarting_service_keeps_project_but_expires_in_memory_plans(self):
        plan_url, _ = self.ready()
        with TestClient(create_app(ProjectStore(self.tmp.name), ffmpeg=FFMPEG),
                        base_url='http://127.0.0.1', client=('127.0.0.1', 1234)) as restarted:
            self.assertEqual(restarted.get(self.url).json()['project'], self.record['project'])
            self.assertEqual(restarted.get(plan_url).status_code, 404)


if __name__ == '__main__':
    unittest.main()
