import copy
import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from ai_story_planner import (
    APIConfig, AIRequestError, _NoRedirect, _json_object, _output_text, _request,
    plan_sequence, request_highlights, transcribe_audio,
)
from edit_plan import build_edit_plan, validate_edit_plan


class ProviderTests(unittest.TestCase):
    def test_normalizes_versioned_and_gateway_endpoints(self):
        for base, expected in [
            ('https://api.openai.com', 'https://api.openai.com/v1/responses'),
            ('https://api.openai.com/v1/', 'https://api.openai.com/v1/responses'),
            ('https://gateway.example/prefix/v1', 'https://gateway.example/prefix/v1/responses'),
        ]:
            self.assertEqual(APIConfig(base_url=base).endpoint('responses'), expected)
        for base in ['https://key@example.com', 'file:///etc/passwd', 'https://example.com?key=value']:
            with self.assertRaises(ValueError):
                APIConfig(base_url=base).endpoint('responses')

    def test_reads_all_output_text_and_handles_refusal_and_incomplete(self):
        result = {'status': 'completed', 'output': [
            {'type': 'reasoning'}, {'type': 'message', 'content': [
                {'type': 'output_text', 'text': '{"segments":'},
                {'type': 'output_text', 'text': '[]}'},
            ]}]}
        self.assertEqual(_json_object(_output_text(result)), {'segments': []})
        for result, code in [({'status': 'incomplete', 'output_text': '{}'}, 'incomplete_response'),
                             ({'output_text': '{}', 'output': [{'content': [{'type': 'refusal'}]}]}, 'refused'),
                             ({'output': ['unexpected']}, 'invalid_response')]:
            with self.assertRaises(AIRequestError) as raised:
                _output_text(result)
            self.assertEqual(raised.exception.code, code)

    def test_rejects_non_object_nonfinite_and_truncated_json(self):
        for raw in ['[]', '{', '{"start":NaN}', '{"end":Infinity}']:
            with self.assertRaises(AIRequestError):
                _json_object(raw)

    def test_http_errors_do_not_echo_provider_body_url_or_credentials(self):
        for status, code in [(401, 'authentication_failed'), (429, 'rate_limited'), (500, 'provider_http_error')]:
            error = urllib.error.HTTPError('https://secret-user@example.com', status, 'private-key', {},
                                           io.BytesIO(b'private-key /home/user/private-media.mp4'))
            with patch('urllib.request.OpenerDirector.open', side_effect=error):
                with self.assertRaises(AIRequestError) as raised:
                    _request('https://example.com/v1/responses', b'{}', {}, 1)
            self.assertEqual(raised.exception.code, code)
            self.assertNotIn('private', str(raised.exception))
            self.assertNotIn('secret', str(raised.exception))

    def test_authenticated_requests_never_follow_redirects(self):
        self.assertIsNone(_NoRedirect().redirect_request(None, None, 302, '', {}, 'https://other.example'))

    def test_oversized_transcription_fails_before_read_or_network(self):
        with tempfile.TemporaryDirectory() as folder:
            audio = Path(folder) / 'large.m4a'
            with audio.open('wb') as stream:
                stream.truncate(24_000_001)
            with patch('ai_story_planner._request') as request:
                with self.assertRaises(AIRequestError) as raised:
                    transcribe_audio(APIConfig(api_key='key'), str(audio))
                self.assertEqual(raised.exception.code, 'audio_too_large')
                request.assert_not_called()

    def test_highlights_use_store_false_and_validate_times(self):
        segment = dict(start=0, end=3, score=80, reason='真实镜头', caption='', role='setup')
        with tempfile.TemporaryDirectory() as folder:
            image = Path(folder) / 'sheet.jpg'
            image.write_bytes(b'fixture')
            with patch('ai_story_planner._request', return_value={'output_text': json.dumps({'segments': [segment]})}) as request:
                result = request_highlights(APIConfig(api_key='key'), '', str(image), 10, '旅行')
                self.assertEqual(result[0]['start'], 0)
                payload = json.loads(request.call_args.args[1])
                self.assertIs(payload['store'], False)
            for bad in [float('nan'), float('inf'), True]:
                with patch('ai_story_planner._request', return_value={'output_text': json.dumps({'segments': [{**segment, 'start': bad}]})}):
                    with self.assertRaises(AIRequestError):
                        request_highlights(APIConfig(), '', str(image), 10, '')

    def test_strict_planning_propagates_provider_error_legacy_fallback_is_preserved(self):
        analyses = [{'meta': {'name': 'footage.mp4', 'path': 'footage.mp4', 'duration': 10},
                     'segments': [dict(start=0, end=4, score=80, caption='', reason='镜头', role='setup')]}]
        with patch('ai_story_planner._request', side_effect=AIRequestError('请求受限。', 'rate_limited')):
            with self.assertRaises(AIRequestError):
                plan_sequence(APIConfig(), analyses, 5, '', allow_fallback=False)
            self.assertTrue(plan_sequence(APIConfig(), analyses, 5, ''))

    def test_plan_validation_rejects_nonfinite_before_mutating(self):
        analyses = [{'meta': {'path': 'a.mp4', 'name': 'a.mp4', 'duration': 10}}]
        original = build_edit_plan([dict(source_index=0, start=0, end=4)], analyses, 5)
        for field in ('start', 'end', 'source_duration', 'mask_x', 'mask_feather'):
            plan = copy.deepcopy(original)
            plan['decisions'][0][field] = float('nan')
            self.assertFalse(validate_edit_plan(plan)['ok'], field)


if __name__ == '__main__':
    unittest.main()
