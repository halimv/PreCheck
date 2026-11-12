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
ENTRY = "insufficient_liquid.loaded_reagent"

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


def heal_demo(tmp_path, backend, escalate_after=1, max_rounds=3):
    demo = json.loads((ROOT / "protocols" / "plate_wash_incubate_demo.json").read_text())
    healer = SelfHealer(load_deck_config(str(CONFIG / "reference" / "plr_deck_plate_assay.json")), backend, str(tmp_path / "work"))
    return healer.heal(demo, max_rounds=max_rounds, escalate_after=escalate_after)


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


def test_a_repeated_failure_escalates(tmp_path):
    backend = escalating_backend()
    result = heal_demo(tmp_path, backend)
    assert result.status == "HEALED"
    first, second = result.rounds[0], result.rounds[1]
    assert (first["mode"], first["repeats"]) == ("knowledge_base", 0)
    assert (second["mode"], second["repeats"]) == ("escalated", 1)
    assert second["previous_rejections"] == ["intent guard: moves a different volume"]
    assert backend.calls[0]["schema"] is None and backend.calls[1]["schema"] is ESCALATION_SCHEMA
    prompt = backend.calls[1]["prompt"]
    assert "come back 1 time(s) in a row (INSUFFICIENT_LIQUID at step 28)" in prompt
    assert "round 0: rejected by the harness" in prompt  # what was already tried
    assert "{needed}" in prompt  # the placeholders it may use


def test_no_escalation_unless_asked(tmp_path):
    backend = Scripted({"reasoning": "", "edits": [LOWER]}, {"reasoning": "", "edits": [LOAD_MORE]})
    result = heal_demo(tmp_path, backend, escalate_after=None)
    assert result.status == "HEALED"
    assert {r.get("mode") for r in result.rounds if "edits" in r} == {"knowledge_base"}
    assert all(c["schema"] is None for c in backend.calls)
    assert result.proposals == []


def test_a_proposal_that_healed_is_generalized_and_kept(tmp_path):
    result = heal_demo(tmp_path, escalating_backend())
    [p] = result.proposals
    assert p["problems"] == []
    assert (p["kind"], p["target"]) == ("replace_fixes", ENTRY)
    # This run's labware and step became placeholders; the known placeholder {needed} was kept.
    assert p["proposed"]["fix"] == "Load more into {labware} before step {n}: {needed} uL plus 10% is enough."
    assert p["evidence"]["edits_applied"] == [LOAD_MORE]
    # Shown filled in, so a misused placeholder is easy to spot; and flagged because the edit that
    # worked (set_initial_volume) is what the entry already suggests.
    assert p["proposed"]["fix_example"] == "Load more into wash_buffer_trough before step 28: 6400.0 uL plus 10% is enough."
    assert any("already suggests" in w for w in p["warnings"])


def test_a_partly_rejected_reply_is_not_kept(tmp_path):
    backend = Scripted({"reasoning": "", "edits": [LOWER]},
                       {"reasoning": "", "edits": [LOAD_MORE, {"op": "replace_step", "step": 99, "new_steps": []}],
                        "knowledge_proposal": PROPOSAL})
    result = heal_demo(tmp_path, backend)
    assert result.status == "HEALED"
    assert result.proposals[0]["problems"] == ["part of the model's reply was rejected, so the fix it describes was not what ran"]


@pytest.mark.parametrize("volume, problem", [
    (4000, "its edits did not fix the failure"),  # same failure, same step
    # 5000 uL moves the failure from step 28 to step 30: it counts as resolved, but the protocol
    # still fails, so the proposal is not kept.
    (5000, "the protocol did not pass every stage afterwards"),
])
def test_a_proposal_whose_fix_failed_is_not_kept(tmp_path, volume, problem):
    backend = Scripted({"reasoning": "", "edits": [LOWER]},
                       {"reasoning": "", "edits": [{**LOAD_MORE, "volume_ul": volume}], "knowledge_proposal": PROPOSAL})
    result = heal_demo(tmp_path, backend, max_rounds=2)
    assert result.status == "GAVE_UP"
    assert result.proposals[0]["problems"] == [problem]
    assert proposals.submit(result.proposals, "demo.json", "qwen") == []


def test_approving_replaces_the_fixes(tmp_path, kb_copy):
    result = heal_demo(tmp_path, escalating_backend())
    [stored] = proposals.submit(result.proposals, "demo.json", "qwen", kb_copy, DAY)
    assert proposals.pending(kb_copy)[0]["id"] == stored["id"]
    old = next(e for e in diagnostics.knowledge_base(kb_copy) if e["id"] == ENTRY)["fixes"]

    entry = proposals.approve(stored["id"], kb_copy, today=DAY)
    assert entry["fixes"] == [stored["proposed"]["fix"]]
    assert any(n.startswith("Fixes before 2026-10-30") for n in entry["notes"])
    assert any(stored["id"] in n for n in entry["notes"])
    assert diagnostics.knowledge_base(kb_copy)  # still loads
    assert proposals.pending(kb_copy) == []
    with pytest.raises(ValueError, match="already approved"):
        proposals.approve(stored["id"], kb_copy)
    assert old != entry["fixes"]


def test_rejecting_keeps_a_record(tmp_path, kb_copy):
    result = heal_demo(tmp_path, escalating_backend())
    [stored] = proposals.submit(result.proposals, "demo.json", "qwen", kb_copy, DAY)
    proposals.reject(stored["id"], kb_copy, comment="too specific", today=DAY)
    kb = json.loads(kb_copy.read_text())
    assert kb["proposals"][0]["status"] == "rejected"
    assert kb["proposals"][0]["reviewed"] == {"date": "2026-10-30", "comment": "too specific"}
    assert kb["entries"] == json.loads(kb_copy.read_text())["entries"]


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


def test_each_repair_decision_is_logged(tmp_path, kb_copy):
    result = heal_demo(tmp_path, escalating_backend())
    diagnostics.record_run(result.rounds, "demo.json", "qwen", kb_copy, DAY)
    lines = [json.loads(x) for x in diagnostics.decisions_path(kb_copy).read_text().splitlines()]
    assert [(d["mode"], d["repeats"], d["resolved"]) for d in lines] == [("knowledge_base", 0, False), ("escalated", 1, True)]
    assert lines[1]["previous_rejections"] == ["intent guard: moves a different volume"]
    assert lines[1]["entry_seen_before"] == 1  # features only use what was known before the decision
    assert lines[1]["run_status"] == "HEALED" and lines[1]["proposal"] is True
    obs = json.loads(kb_copy.read_text())["entries"][1]["observed"]
    assert (obs["escalations"], obs["escalations_resolved"]) == (1, 1)
