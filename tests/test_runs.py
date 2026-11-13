"""The run store: a run is written, listed, reopened and acknowledged, and never reads outside its folder."""

import json
from pathlib import Path

import pytest

from pipeline import runs

TESTS = Path(__file__).resolve().parent
PROTOCOL = json.loads((TESTS / "fixtures" / "serial_passing.json").read_text())
ROUNDS = [{"round": 0, "passed": True, "result": "passed"}]
TIERS = [{"model": "claude-haiku-5-5", "status": "ALREADY_PASSING", "rounds": ROUNDS}]
REPORT = {"needs_review": [{"severity": "must", "area": "deck", "item": "Place a carrier", "detail": "rail 13"}]}


@pytest.fixture
def run_dir(tmp_path):
    return runs.record("serial", "protocol text", PROTOCOL, ROUNDS, TIERS, True, "# Summary\n", REPORT,
                       script="print()", runs_dir=tmp_path)


def test_a_run_is_written_with_its_files_and_manifest(run_dir):
    assert list(run_dir.glob("input*")), "the protocol text is kept as input.txt"
    for name in ("protocol.json", "summary.md", "heal_log.json", "report.json", "script.py", "manifest.json"):
        assert (run_dir / name).exists(), name
    manifest = json.loads((run_dir / "manifest.json").read_text())
    assert manifest["status"] == "PASSED" and manifest["steps"] == len(PROTOCOL["steps"])
    assert manifest["models"] == [{"model": "claude-haiku-5-5", "rounds": 0, "status": "ALREADY_PASSING"}]


def test_provenance_records_the_ground_truth_and_versions(run_dir):
    prov = json.loads((run_dir / "manifest.json").read_text())["provenance"]
    assert prov["instrument_file_sha256"] and len(prov["instrument_file_sha256"]) == 64
    assert prov["labware_library_fingerprint"] and prov["pylabrobot"] != "unknown"
    assert set(prov) >= {"precheck_commit", "python", "venus_map_sha256", "policy_sha256", "firmware_report_sha256"}


def test_a_failed_run_is_recorded_as_not_ready_with_no_script(tmp_path):
    folder = runs.record("serial", None, PROTOCOL, ROUNDS, TIERS, False, "# Not ready\n", None, runs_dir=tmp_path)
    manifest = json.loads((folder / "manifest.json").read_text())
    assert manifest["status"] == "NOT READY" and not (folder / "script.py").exists()


def test_runs_are_listed_newest_first(tmp_path):
    names = [runs.record(stem, None, PROTOCOL, ROUNDS, TIERS, True, "x", None, runs_dir=tmp_path).name
             for stem in ("a", "b", "c")]
    listed = runs.list_runs(tmp_path)
    assert {m["id"] for m in listed} == set(names)
    created = [m["created"] for m in listed]
    assert created == sorted(created, reverse=True)


def test_a_file_outside_the_run_is_refused(run_dir, tmp_path):
    assert runs.run_file(run_dir.name, "summary.md", tmp_path) is not None
    assert runs.run_file(run_dir.name, "../../secret", tmp_path) is None
    assert runs.run_file("../" + run_dir.name, "summary.md", tmp_path) is not None  # the folder name is what counts
    assert runs.run_file(run_dir.name, "missing.md", tmp_path) is None


def test_a_review_item_is_acknowledged_with_a_name_and_a_note(run_dir, tmp_path):
    manifest = runs.acknowledge(run_dir.name, 0, "  Vania  ", "Carrier placed on rail 13.", tmp_path)
    ack = manifest["review"]["acknowledged"]["0"]
    assert ack["by"] == "Vania" and ack["note"].startswith("Carrier") and ack["at"]
    with pytest.raises(IndexError):
        runs.acknowledge(run_dir.name, 5, "Vania", "", tmp_path)
