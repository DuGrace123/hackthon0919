"""LingJian backend: project persistence and the HTTP API around the editing engine.

The package imports the root modules (video_editing_engine, edit_plan) directly,
so the project root is added to sys.path here for ``python -m backend`` and for
callers that import the package from another working directory.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

APP_VERSION = "4.13.0"
