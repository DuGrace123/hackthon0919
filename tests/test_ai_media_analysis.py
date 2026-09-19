"""Real FFmpeg checks. No cloud requests, GUI, personal footage or model required."""
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from ai_story_planner import AIRequestError, AnalysisCancelled, extract_assets, run_analysis_command
from ai_workflow import AIWorkflow, analyze_local
from tests.test_ai_workflow import MemoryBackend, completed


def find_ffmpeg():
    configured = os.environ.get('FIGSTUDIO_TEST_FFMPEG') or shutil.which('ffmpeg')
    if configured:
        return configured
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return None


FFMPEG = find_ffmpeg()


class ProcessControlTests(unittest.TestCase):
    def test_timeout_kills_child(self):
        with self.assertRaises(AIRequestError) as raised:
            run_analysis_command([sys.executable, '-c', 'import time; time.sleep(30)'], timeout=.05)
        self.assertEqual(raised.exception.code, 'analysis_timeout')

    def test_cancellation_reaps_running_child(self):
        calls = []
        def cancel():
            calls.append(True)
            if len(calls) > 2:
                raise AnalysisCancelled()
        with self.assertRaises(AnalysisCancelled):
            run_analysis_command([sys.executable, '-c', 'import time; time.sleep(30)'], checkpoint=cancel)
        self.assertGreater(len(calls), 2)


@unittest.skipUnless(FFMPEG, 'Set FIGSTUDIO_TEST_FFMPEG or install FFmpeg/imageio-ffmpeg')
class RealMediaTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.source = self.root / 'actual.mp4'
        run_analysis_command([FFMPEG, '-y', '-v', 'error', '-f', 'lavfi', '-i',
                              'testsrc2=size=160x90:rate=12', '-t', '8', '-c:v', 'libx264',
                              '-pix_fmt', 'yuv420p', str(self.source)])

    def test_real_silent_media_local_preview_apply_and_undo(self):
        backend = MemoryBackend(self.root)
        from dataclasses import replace
        backend.source = replace(backend.source, path=self.source, duration=8)
        workflow = AIWorkflow(backend, FFMPEG)
        self.addCleanup(workflow.close)
        before = backend.project.to_dict()
        job = workflow.create('project-1', 'owner-1', media_ids=['media-1'], revision=1, target_duration=5)
        result = completed(workflow, job['id'])
        self.assertEqual(result['status'], 'ready', result)
        self.assertEqual(backend.project.to_dict(), before)
        self.assertLessEqual(result['result']['duration'], 5)
        workflow.apply('project-1', job['id'], 'owner-1', revision=1, confirm=True)
        self.assertTrue(backend.project.clips)
        workflow.undo('project-1', job['id'], 'owner-1', revision=2)
        self.assertEqual(backend.project.to_dict(), before)

    def test_contact_sheet_silent_and_cache_invalidated_when_source_replaced(self):
        audio, sheet = extract_assets(FFMPEG, str(self.source), str(self.root / 'cache'), 8)
        self.assertFalse(Path(audio).exists())
        self.assertGreater(Path(sheet).stat().st_size, 100)
        self.assertEqual(Path(sheet).read_bytes()[:2], b'\xff\xd8')
        same = extract_assets(FFMPEG, str(self.source), str(self.root / 'cache'), 8)
        self.assertEqual(same, (audio, sheet))
        stat = self.source.stat()
        os.utime(self.source, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000))
        new = extract_assets(FFMPEG, str(self.source), str(self.root / 'cache'), 8)
        self.assertNotEqual(new[1], sheet)
        self.assertTrue(Path(new[1]).is_file())
        self.assertFalse(list((self.root / 'cache').glob('.extract-*')))

    def test_real_audio_asset_extraction(self):
        audible = self.root / 'with-audio.mp4'
        run_analysis_command([FFMPEG, '-y', '-v', 'error', '-i', str(self.source), '-f', 'lavfi', '-i',
                              'sine=frequency=440:sample_rate=16000', '-t', '8', '-c:v', 'copy',
                              '-c:a', 'aac', str(audible)])
        audio, sheet = extract_assets(FFMPEG, str(audible), str(self.root / 'audio-cache'), 8)
        self.assertGreater(Path(audio).stat().st_size, 1000)
        self.assertTrue(Path(sheet).is_file())


if __name__ == '__main__':
    unittest.main()
