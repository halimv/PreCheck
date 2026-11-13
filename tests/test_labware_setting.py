"""The VENUS Labware folder the person gives is saved outside the plugin, and every later run finds it."""

import os
import subprocess
import sys
from pathlib import Path

from pipeline import paths, workfolder

ROOT = Path(__file__).resolve().parent.parent


def _library(folder: Path) -> Path:
    (folder / "ML_STAR").mkdir(parents=True)
    return folder


def test_a_given_folder_with_ml_star_is_saved_and_found(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "CONFIG_FILE", tmp_path / "config.json")
    monkeypatch.delenv("PRECHECK_LABWARE", raising=False)
    library = _library(tmp_path / "Labware")
    assert "Saved" in workfolder.set_labware(str(library))
    assert paths.labware() == library


def test_a_folder_without_ml_star_is_refused_and_nothing_is_saved(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "CONFIG_FILE", tmp_path / "config.json")
    assert "not a VENUS Labware folder" in workfolder.set_labware(str(tmp_path))
    assert paths.saved_settings() == {}


def test_the_environment_overrides_the_saved_folder(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "CONFIG_FILE", tmp_path / "config.json")
    workfolder.set_labware(str(_library(tmp_path / "saved")))
    monkeypatch.setenv("PRECHECK_LABWARE", str(tmp_path / "other"))
    assert paths.labware() == tmp_path / "other"


def test_setup_with_labware_in_a_script_saves_it_without_a_prompt(tmp_path):
    library = _library(tmp_path / "Labware")
    config = tmp_path / "config.json"
    env = dict(os.environ, PRECHECK_WORKDIR=str(tmp_path / "work"), PRECHECK_CONFIG=str(config),
               PYTHONPATH=str(ROOT / "plugin"))
    (tmp_path / "work").mkdir()
    run = subprocess.run([sys.executable, "-W", "ignore", str(ROOT / "plugin" / "pipeline.py"), "--setup",
                          "--labware", str(library)],
                         cwd=tmp_path / "work", env=env, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    assert run.returncode == 0, run.stderr[-800:]
    assert "Saved the VENUS Labware folder" in run.stdout
    assert str(library) in config.read_text()
