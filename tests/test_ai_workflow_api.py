import tempfile
import unittest

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from ai_workflow import AIWorkflow
from ai_workflow_api import create_ai_router
from tests.test_ai_workflow import MemoryBackend, completed, fake_local


class AIRouteTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.backend = MemoryBackend(self.folder.name)
        self.workflow = AIWorkflow(self.backend, 'test-ffmpeg', local_analyzer=fake_local)
        self.addCleanup(self.workflow.close)
        self.owner = 'owner-1'
        def authenticated_user():
            if self.owner is None:
                raise HTTPException(status_code=401)
            return self.owner
        app = FastAPI()
        app.include_router(create_ai_router(self.workflow, current_user=authenticated_user))
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.url = '/api/projects/project-1/ai/plans'
        self.payload = {'media_ids': ['media-1'], 'revision': 1, 'target_duration': 8}

    def test_browser_contract_create_poll_apply_undo(self):
        capabilities = self.client.get('/api/ai/capabilities')
        self.assertEqual(capabilities.status_code, 200)
        self.assertFalse(capabilities.json()['cloud_available'])
        response = self.client.post(self.url, json=self.payload)
        self.assertEqual(response.status_code, 202, response.text)
        plan_id = response.json()['id']
        completed(self.workflow, plan_id)
        detail = self.client.get(f'{self.url}/{plan_id}')
        self.assertEqual(detail.json()['status'], 'ready')
        self.assertTrue(detail.json()['result']['shots'])
        self.assertNotIn('source_path', detail.text)
        apply = self.client.post(f'{self.url}/{plan_id}/apply', json={'revision': 1, 'confirm': True})
        self.assertEqual(apply.status_code, 200, apply.text)
        self.assertEqual(apply.json()['revision'], 2)
        undo = self.client.post(f'{self.url}/{plan_id}/undo', json={'revision': 2})
        self.assertEqual(undo.status_code, 200)
        self.assertEqual(undo.json()['status'], 'undone')

    def test_authentication_is_required(self):
        self.owner = None
        self.assertEqual(self.client.post(self.url, json=self.payload).status_code, 401)
        self.assertEqual(self.client.get('/api/ai/capabilities').status_code, 401)

    def test_rejects_paths_keys_unknown_fields_and_coerced_consent(self):
        for fields in [{'api_key': 'not-accepted'}, {'base_url': 'http://localhost'},
                       {'media_ids': ['/etc/passwd']}, {'cloud_consent': 'true'},
                       {'revision': True}, {'target_duration': True}]:
            with self.subTest(fields=fields):
                response = self.client.post(self.url, json={**self.payload, **fields})
                self.assertEqual(response.status_code, 422, response.text)

    def test_stale_revision_returns_409(self):
        response = self.client.post(self.url, json={**self.payload, 'revision': 9})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['detail']['code'], 'revision_conflict')

    def test_cancel_prevents_apply(self):
        response = self.client.post(self.url, json=self.payload)
        url = self.url + '/' + response.json()['id']
        self.assertEqual(self.client.post(url + '/cancel').json()['status'], 'cancelled')
        self.assertEqual(self.client.post(url + '/apply', json={'revision': 1, 'confirm': True}).status_code, 409)


if __name__ == '__main__':
    unittest.main()
