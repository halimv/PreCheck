"""Reproducibility checks on protocols/serial_dilution_v1.json.

v1 is the reference "known-bad" protocol: it passes Stage 1 but fails in simulation, and is the
input for self-healing runs. Repairs are written to build/ as *_healed.json and must never
replace this file. If one of these tests fails, the original was changed or a stage's
behaviour on it drifted.
"""

import copy
import json
from pathlib import Path

from pipeline.deck import load_deck_config
from pipeline.self_heal import apply_edits
from pipeline.stage1_verifier import Verifier
from pipeline.stage2_compiler import compile_protocol
from pipeline.stage3_simulator import PLRSimulator

ROOT = Path(__file__).resolve().parent.parent
V1 = ROOT / "protocols" / "serial_dilution_v1.json"
CONFIG = ROOT / "config"


def load_v1():
    return json.loads(V1.read_text())


def kinds(deck_config):
    return {lid: spec["kind"] for lid, spec in deck_config["labware"].items()}


def test_original_still_has_its_known_defects():
    p = load_v1()
    assert len(p["steps"]) == 68
    assert p["initial_volumes_ul"]["tube_15ml"] == 600
    assert p["steps"][1]["labware"] == "tube_15ml"
    assert p["steps"][1]["channels"] == list(range(8))


def test_stage1_passes_original():
    result = Verifier(str(CONFIG / "labware.json"), str(V1), str(CONFIG / "protocol_defaults.json")).run_verification()
    assert result["status"] == "PASSED"


def test_stage3_fails_original_at_step_2_channel_spacing():
    deck_config = load_deck_config(str(CONFIG / "plr_deck.json"))
    p = load_v1()
    sim = PLRSimulator(deck_config).run(compile_protocol(p, deck_config), p)
    assert sim.status == "FAILED"
    assert sim.diagnostic["step"] == 2
    assert sim.diagnostic["error_code"] == "CHANNEL_SPACING"


def test_reference_repair_passes_and_leaves_original_untouched():
    deck_config = load_deck_config(str(CONFIG / "plr_deck.json"))
    original = load_v1()
    snapshot = copy.deepcopy(original)

    split = [{"action": "aspirate", "labware": "tube_15ml", "volume_ul": 100.0, "channels": [ch],
              "description": f"channel {ch}"} for ch in range(8)]
    repaired, errors = apply_edits(original, [{"op": "replace_step", "step": 2, "new_steps": split}],
                                   kinds(deck_config), allowed_step=2)
    assert errors == []
    repaired, errors = apply_edits(repaired, [{"op": "set_initial_volume", "labware": "tube_15ml", "volume_ul": 900}],
                                   kinds(deck_config), allowed_step=8)
    assert errors == []

    sim = PLRSimulator(deck_config).run(compile_protocol(repaired, deck_config), repaired)
    assert sim.status == "PASSED"
    assert original == snapshot            # in-memory input not mutated
    assert load_v1() == snapshot           # file on disk not rewritten
