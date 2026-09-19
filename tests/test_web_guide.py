from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from web_app import create_app


class UserGuideLanguageTests(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.TemporaryDirectory()
        self.addCleanup(self.workspace.cleanup)
        self.client = create_app(self.workspace.name).test_client()

    def test_default_english_guide_and_download_are_public(self):
        response = self.client.get('/guide')
        self.assertEqual(response.status_code, 200)
        self.assertIn('<html lang="en">', response.text)
        self.assertIn('Import footage', response.text)
        self.assertIn('/guide/download?lang=en', response.text)
        self.assertEqual(response.headers['Content-Language'], 'en')
        self.assertEqual(self.client.get('/api/project').status_code, 401)

    def test_explicit_language_overrides_saved_preference(self):
        self.client.set_cookie('lingjian-language', 'zh')
        self.assertIn('导入素材', self.client.get('/guide').text)
        response = self.client.get('/guide?lang=en')
        self.assertIn('Import footage', response.text)
        self.assertNotIn('导入素材', response.text)
        self.assertEqual(response.headers['Cache-Control'], 'private, no-store')
        self.assertIn('Import footage', self.client.get('/guide?lang=unknown').text)

    def test_download_matches_language_and_is_an_attachment(self):
        root = Path(__file__).resolve().parents[1] / 'web/static/guides'
        for language, filename in [('en', 'lingjian-quick-start.en.pdf'), ('zh', 'lingjian-quick-start.pdf')]:
            with self.subTest(language=language):
                self.client.set_cookie('lingjian-language', language)
                for url in ['/guide/download', f'/guide/download?lang={language}']:
                    response = self.client.get(url)
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.mimetype, 'application/pdf')
                    self.assertEqual(response.headers['Content-Language'], language)
                    self.assertIn('attachment', response.headers['Content-Disposition'])
                    self.assertEqual(response.data, (root / filename).read_bytes())
                    response.close()
