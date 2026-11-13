"""A run writes into the working folder, and the plugin's own folders are only read."""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "plugin"  # the plugin: code and ground truth
TESTS = Path(__file__).resolve().parent
PASSING = TESTS / "fixtures" / "serial_passing.json"


def test_a_passing_protocol_is_written_to_the_working_folder_not_the_plugin(tmp_path):
    assert not (ROOT / "healed").exists()  # the plugin has no run outputs
    script = (
        "import json, sys\n"
        "from pipeline import paths\n"
        "from pipeline.deck import load_deck_config\n"
        "from pipeline.flow import finish\n"
        f"p = json.load(open({str(PASSING)!r}))\n"
        f"deck = load_deck_config({str(TESTS / 'fixtures' / 'serial_deck.json')!r})\n"
        "report = finish(p, deck, 'workdir_check', [], status='PASSED')\n"
        "print(paths.WORK)\n"
    )
    env = dict(os.environ, PRECHECK_WORKDIR=str(tmp_path), PYTHONPATH=str(ROOT))
    run = subprocess.run([sys.executable, "-W", "ignore", "-c", script], cwd=tmp_path, env=env,
                         capture_output=True, text=True)
    assert run.returncode == 0, run.stderr[-800:]
    assert Path(run.stdout.strip().splitlines()[-1]) == tmp_path.resolve()
    assert (tmp_path / "healed" / "workdir_check.json").exists()
    assert (tmp_path / "knowledge" / "diagnostics.json").exists()
    assert not (ROOT / "healed").exists()  # the run wrote into the working folder, not the plugin


def test_setup_makes_the_working_folders_and_seeds_the_knowledge_base(tmp_path):
    env = dict(os.environ, PRECHECK_WORKDIR=str(tmp_path), PYTHONPATH=str(ROOT))
    run = subprocess.run([sys.executable, "-W", "ignore", "-c",
                          "from pipeline import workfolder; print(workfolder.report(workfolder.setup()))"],
                         cwd=tmp_path, env=env, capture_output=True, text=True)
    assert run.returncode == 0, run.stderr[-800:]
    for folder in ("healed", "drafts", "decks", "build"):
        assert (tmp_path / folder).is_dir()
    assert (tmp_path / "knowledge" / "diagnostics.json").exists()
    assert "Working folders present" in run.stdout


def test_interactive_setup_creates_the_task_folder_the_person_names(tmp_path):
    """Typing a folder path at the setup prompt creates that folder (and nothing is created in this one)."""
    target = tmp_path / "new_task"
    env = dict(os.environ, PRECHECK_WORKDIR=str(tmp_path / "here"), PYTHONPATH=str(ROOT))
    (tmp_path / "here").mkdir()
    script = (
        "from pipeline import workfolder\n"
        "answers = iter([%r])\n"  # the library is already linked, so the only question is the folder
        "workfolder.interactive_setup(ask=lambda prompt: next(answers), out=lambda *a: None)\n"
    ) % str(target)
    run = subprocess.run([sys.executable, "-W", "ignore", "-c", script], cwd=tmp_path, env=env,
                         capture_output=True, text=True)
    assert run.returncode == 0, run.stderr[-800:]
    assert target.is_dir()
    assert not (tmp_path / "here" / "healed").exists()
