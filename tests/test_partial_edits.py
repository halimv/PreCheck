"""Partial acceptance in the self-healing loop: edits that pass their checks are applied even when
another edit in the same reply is rejected.

The scripted replies are the ones qwen2.5-coder:7b actually sent: a correct set_initial_volume
bundled with a replace_step that fails to compile, or that changes how much liquid moves.
"""

import json
from pathlib import Path

from pipeline.deck import load_deck_config
from pipeline.self_heal import SelfHealer, apply_valid_edits

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config"
ALL = list(range(8))


class Scripted:
    """Backend that returns the given replies in order (and no edits after that)."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.prompts = []

    def propose_edits(self, system, prompt):
        self.prompts.append(prompt)
        return self.replies.pop(0) if self.replies else {"reasoning": "", "edits": []}


def healer(tmp_path, deck_file, backend):
    return SelfHealer(load_deck_config(str(CONFIG / "reference" / deck_file)), backend, str(tmp_path))


def test_correct_edit_survives_an_uncompilable_one(tmp_path):
    demo = json.loads((ROOT / "protocols" / "plate_wash_incubate_demo.json").read_text())
    reply = {"reasoning": "Load more wash buffer.", "edits": [
        {"op": "set_initial_volume", "labware": "wash_buffer_trough", "volume_ul": 7050},
        {"op": "replace_step", "step": 28, "new_steps": [
            {"action": "aspirate", "labware": "wash_buffer_trough", "volume_ul": 200, "channels": ALL, "description": ""},
            {"action": "dispense", "labware": "corning_3595", "volume_ul": 200, "channels": ALL, "description": ""},
        ]},
    ]}
    backend = Scripted(reply)
    result = healer(tmp_path, "plr_deck_plate_assay.json", backend).heal(demo, max_rounds=2)

    assert result.status == "HEALED"
    first = result.rounds[0]
    assert first["edits_applied"] == [0]
    assert any("needs a 'column'" in e for e in first["edit_errors"])
    assert result.protocol["initial_volumes_ul"]["wash_buffer_trough"] == 7050
    assert len(result.protocol["steps"]) == len(demo["steps"])  # the bad replace_step was not applied


def test_correct_edit_survives_an_intent_violation(tmp_path):
    v1 = json.loads((ROOT / "docs" / "runs" / "2026-10-21_v1_qwen2.5-coder-7b" / "serial_dilution_v1_healed.json").read_text())
    v1["initial_volumes_ul"]["tube_15ml"] = 550
    sim = healer(tmp_path, "plr_deck.json", Scripted()).evaluate(v1, 0)
    assert not sim.passed
    step = sim.step
    failing = next(s for s in v1["steps"] if s["step"] == step)
    reply = {"reasoning": "Load more stock and take less.", "edits": [
        {"op": "set_initial_volume", "labware": "tube_15ml", "volume_ul": 900},
        {"op": "replace_step", "step": step, "new_steps": [{**failing, "volume_ul": failing["volume_ul"] / 2}]},
    ]}
    backend = Scripted(reply)
    result = healer(tmp_path, "plr_deck.json", backend).heal(v1, max_rounds=2)

    assert result.status == "HEALED"
    assert result.rounds[0]["edits_applied"] == [0]
    assert any("changes how much liquid is moved" in e for e in result.rounds[0]["edit_errors"])
    assert next(s for s in result.protocol["steps"] if s["step"] == step)["volume_ul"] == failing["volume_ul"]


def test_rejected_part_is_reported_to_the_model(tmp_path):
    demo = json.loads((ROOT / "protocols" / "plate_wash_incubate_demo.json").read_text())
    demo["steps"][6]["temperature_c"] = 120  # a second, unrelated fault after the first repair
    reply = {"reasoning": "", "edits": [
        {"op": "set_initial_volume", "labware": "wash_buffer_trough", "volume_ul": 7050},
        {"op": "replace_step", "step": 99, "new_steps": []},
    ]}
    # The temperature fault (step 7) comes before step 28, so round 0 fails there; the
    # set_initial_volume still applies and the bad replace_step is reported back.
    backend = Scripted(reply)
    result = healer(tmp_path, "plr_deck_plate_assay.json", backend).heal(demo, max_rounds=2)
    assert result.status == "GAVE_UP"  # the temperature fault needs the scientist
    assert result.rounds[0]["edits_applied"] == [0]
    assert result.protocol["initial_volumes_ul"]["wash_buffer_trough"] == 7050
    assert len(backend.prompts) == 2
    assert "Part of your previous attempt was applied" in backend.prompts[1]
    assert "step 99, which does not exist" in backend.prompts[1]
    assert "wash_buffer_trough to 7050" in backend.prompts[1]  # listed under earlier repair rounds


def test_apply_valid_edits_keeps_order_and_indices():
    kinds = {"tube_15ml": "container", "corning_3595": "plate"}
    p = {"steps": [{"step": 1, "action": "tips_off"}], "initial_volumes_ul": {}}
    new, applied, errors = apply_valid_edits(p, [
        {"op": "bogus"},
        {"op": "set_initial_volume", "labware": "tube_15ml", "volume_ul": 10},
        {"op": "set_initial_volume", "labware": "corning_3595", "volume_ul": 10},
    ], kinds)
    assert applied == [1]
    assert len(errors) == 2
    assert new["initial_volumes_ul"] == {"tube_15ml": 10}
    assert p["initial_volumes_ul"] == {}
