"""Puts the plugin's code (plugin/) and the demo (repo root) on the import path for the tests."""

import sys
from pathlib import Path

import os

REPO = Path(__file__).resolve().parent.parent
os.environ.setdefault("PRECHECK_WORKDIR", str(REPO))  # the repo is the working folder for the tests (decks/ fixtures)
os.environ.setdefault("PRECHECK_CONFIG", str(Path(__import__("tempfile").mkdtemp()) / "config.json"))  # never the person's saved settings
for folder in (REPO / "plugin",):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))
