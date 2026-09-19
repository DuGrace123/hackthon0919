"""Run the portable core regression checks without external test frameworks."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TESTS = Path(__file__).resolve().parent
PORTABLE_TESTS = [
    "test_edit_plan.py",
    "test_edit_plan_ordering.py",
    "test_sequence_continuity.py",
    "test_editing_preferences.py",
    "test_long_form_ordering.py",
    "test_capture_chronology.py",
    "test_project_store.py",
    "test_backend_api.py",
]


def run(path: Path, *args: str) -> None:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT)
    print(f"\n==> {path.name}", flush=True)
    subprocess.run([sys.executable, str(path), *args], cwd=ROOT, env=env, check=True)


def main() -> None:
    for filename in PORTABLE_TESTS:
        run(TESTS / filename)

    with tempfile.TemporaryDirectory(prefix="lingjian-tests-") as folder:
        fixture = Path(folder) / "contact-sheet.jpg"
        fixture.write_bytes(b"lingjian-test-fixture")
        run(TESTS / "test_ai_story_planner.py", str(fixture))

    print("\nAll portable regression checks passed.")


if __name__ == "__main__":
    main()
