"""Escalation and knowledge-base proposals: a failure that keeps coming back makes the model reason
past the knowledge base and propose a change to it; a proposal whose fix healed the protocol waits
for a person, and approving it changes the entries."""

import datetime
import json
from pathlib import Path

import pytest

from pipeline import diagnostics, proposals
from pipeline.deck import load_deck_config
from pipeline.self_heal import ESCALATION_SCHEMA, SelfHealer

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config"
DAY = datetime.date(2026, 10, 30)

LOWER = {"op": "replace_step", "step": 28, "new_steps": [
    {"action": "aspirate", "labware": "wash_buffer_trough", "volume_ul": 100, "channels": list(range(8))}]}
LOAD_MORE = {"op": "set_initial_volume", "labware": "wash_buffer_trough", "volume_ul": 7050}
PROPOSAL = {"kind": "replace_fixes", "why": "Lowering the volume is always rejected; loading more is not.",
            "fix": "Load more into wash_buffer_trough before step 28: {needed} uL plus 10% is enough."}


class Scripted:
    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls = []

    def propose_edits(self, system, prompt, schema=None):
        self.calls.append({"prompt": prompt, "schema": schema})
        return self.replies.pop(0) if self.replies else {"reasoning": "", "edits": []}


@pytest.fixture
def kb_copy(tmp_path):
    kb = json.loads(diagnostics.KNOWLEDGE_BASE.read_text())
    for entry in kb["entries"]:
        entry.pop("observed", None)
    kb.pop("proposals", None)
    path = tmp_path / "kb" / "diagnostics.json"
    path.parent.mkdir()
    path.write_text(json.dumps(kb))
    return path


def escalating_backend():
    return Scripted({"reasoning": "Take less.", "edits": [LOWER]},
                    {"reasoning": "Loading more keeps the experiment.", "edits": [LOAD_MORE], "knowledge_proposal": PROPOSAL})


def unrecognized_round(proposal):
    return {"round": 2, "kb_entry": "unrecognized", "step": 5, "raw_error": "RuntimeError: gripper jammed at C3",
            "match": {"error": "RuntimeError", "message": "gripper jammed at C3", "action": "dispense", "labware": "plate"},
            "repeats": 1, "mode": "escalated", "edits": [LOAD_MORE], "edits_applied": [0], "knowledge_proposal": proposal}


def test_a_new_entry_goes_above_the_catch_all(kb_copy):
    c = proposals.candidate(unrecognized_round({
        "kind": "add_fix", "code": "GRIPPER_JAM", "title": "Gripper jammed", "match_text": "gripper jammed",
        "explanation": "Step 5 jammed the gripper.", "fix": "Retry step 5.", "why": "Seen once."}), True, True)
    assert c["problems"] == [] and c["kind"] == "new_entry"  # the catch-all can only grow a new entry
    assert c["proposed"]["when"] == {"error": "RuntimeError", "message_contains": "gripper jammed", "action": "dispense"}
    [stored] = proposals.submit([c], "demo.json", "qwen", kb_copy, DAY)
    entry = proposals.approve(stored["id"], kb_copy, today=DAY)
    entries = diagnostics.knowledge_base(kb_copy)
    assert entries[-2]["id"] == entry["id"] == "gripper_jam"
    assert entries[-2]["explanation"] == "Step {n} jammed the gripper."
    assert entries[-1]["id"] == "unrecognized"


def test_bad_new_entries_are_not_kept():
    c = proposals.candidate(unrecognized_round({"kind": "new_entry", "fix": "Retry.", "why": "", "code": "jam",
                                                "match_text": "not in the message"}), True, True)
    assert "a new entry needs a code in UPPER_SNAKE_CASE" in c["problems"]
    assert "a new entry needs a title and an explanation" in c["problems"]
    assert any("does not appear in the error message" in p for p in c["problems"])


def test_braces_that_are_not_placeholders_stay_literal():
    text = proposals._template('Use {"op": "set_initial_volume"} on {labware}', ["labware"], None, None)
    assert text.format(labware="x") == 'Use {"op": "set_initial_volume"} on {labware}'


