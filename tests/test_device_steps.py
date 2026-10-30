"""Checks for the device and waste steps (empty, incubate, shake) on protocols/plate_wash_incubate_demo.json.

The demo is an uncorrected zero-shot draft and, like serial_dilution_v1.json, a fixed known-bad
input: it fails Stage 3 at step 28 because too little wash buffer is loaded. `repaired()` applies
the reference repair (load 7500 uL); each fault below is one change to that repaired version, and
must fail at the stage and with the lab-concept code a repair would see.
"""

import copy
import json
from pathlib import Path

from pipeline.deck import load_deck_config
from pipeline.self_heal import SelfHealer, apply_edits
from pipeline.stage1_verifier import Verifier
from pipeline.stage2_compiler import compile_protocol
from pipeline.stage3_simulator import PLRSimulator

ROOT = Path(__file__).resolve().parent.parent
DEMO = ROOT / "protocols" / "plate_wash_incubate_demo.json"
CONFIG = ROOT / "config"


def deck():
    return load_deck_config(str(CONFIG / "plr_deck_plate_assay.json"))


def demo():
    return json.loads(DEMO.read_text())


def repaired():
    p = demo()
    p["initial_volumes_ul"]["wash_buffer_trough"] = 7500
    return p


def verify(protocol, tmp_path):
    path = tmp_path / "protocol.json"
    path.write_text(json.dumps(protocol))
    return Verifier(str(CONFIG / "labware.json"), str(path), str(CONFIG / "protocol_defaults.json")).run_verification()


def simulate(protocol, deck_config=None):
    deck_config = deck_config or deck()
    return PLRSimulator(deck_config).run(compile_protocol(protocol, deck_config), protocol)


def step_of(protocol, action, which=0):
    return [s for s in protocol["steps"] if s["action"] == action][which]


def test_draft_keeps_its_known_defect(tmp_path):
    p = demo()
    assert p["initial_volumes_ul"]["wash_buffer_trough"] == 4000
    assert verify(p, tmp_path)["status"] == "PASSED"
    sim = simulate(p)
    assert sim.status == "FAILED"
    assert sim.diagnostic["step"] == 28
    assert sim.diagnostic["error_code"] == "INSUFFICIENT_LIQUID"


def test_reference_repair_passes_every_stage(tmp_path):
    original = demo()
    p, errors = apply_edits(original, [{"op": "set_initial_volume", "labware": "wash_buffer_trough", "volume_ul": 7500}],
                            {lid: s["kind"] for lid, s in deck()["labware"].items()}, allowed_step=28)
    assert errors == []
    assert p == repaired()
    assert demo() == original  # file on disk not rewritten
    assert verify(p, tmp_path)["status"] == "PASSED"
    sim = simulate(p)
    assert sim.status == "PASSED", sim.message
    # 1600 uL of coating and 6400 uL of wash buffer were drawn.
    assert sim.final_state["container_volumes_ul"]["reservoir_50ml"] == 400
    assert sim.final_state["container_volumes_ul"]["wash_buffer_trough"] == 1100


def test_empty_leaves_wells_at_zero_without_dead_volume_error(tmp_path):
    p = demo()
    p["steps"] = p["steps"][:10]  # coat, incubate, empty column 1
    assert verify(p, tmp_path)["status"] == "PASSED"
    assert simulate(p).status == "PASSED"


def test_cooling_fault_and_its_suggested_repair():
    p = repaired()
    last = p["steps"][-1]
    last["temperature_c"] = 30  # after the 37 C coat: the heater-shaker cannot cool
    sim = simulate(p)
    assert sim.status == "FAILED"
    assert sim.diagnostic["error_code"] == "HEATER_CANNOT_COOL"
    assert sim.diagnostic["step"] == last["step"]

    cool = {"action": "incubate", "labware": "corning_3595", "duration_s": 600, "volume_ul": 0,
            "channels": [0], "description": "cool down"}
    cooled, errors = apply_edits(p, [{"op": "replace_step", "step": last["step"], "new_steps": [cool, dict(last)]}],
                                 {lid: s["kind"] for lid, s in deck()["labware"].items()}, allowed_step=last["step"])
    assert errors == []
    assert simulate(cooled).status == "PASSED"
    # An added room-temperature hold is allowed by the intent guard.
    assert SelfHealer._intent_violations(_fingerprint(p), _fingerprint(cooled)) == []


def test_device_limits_come_back_as_lab_concept_codes():
    p = demo()
    step_of(p, "shake")["speed_rpm"] = 3000
    assert simulate(p).diagnostic["error_code"] == "SHAKE_SPEED_OUT_OF_RANGE"

    p = demo()
    step_of(p, "incubate")["temperature_c"] = 120
    assert simulate(p).diagnostic["error_code"] == "TEMPERATURE_OUT_OF_RANGE"


def test_plate_not_on_heater_shaker():
    deck_config = deck()
    plate = deck_config["labware"]["corning_3595"]
    del plate["on"]
    plate.update(carrier="plate_carrier", slot=0)
    sim = simulate(demo(), deck_config)
    assert sim.diagnostic["error_code"] == "NOT_ON_HEATER_SHAKER"
    assert sim.diagnostic["step"] == step_of(demo(), "incubate")["step"]


def test_verifier_rejects_hold_with_tips_mounted(tmp_path):
    p = demo()
    tips_off = p["steps"][5]
    assert tips_off["action"] == "tips_off"
    del p["steps"][5]
    result = verify(p, tmp_path)
    assert result["status"] == "FAILED"
    assert result["error_code"] == "TIPS_DURING_HOLD"


def _fingerprint(protocol):
    healer = SelfHealer.__new__(SelfHealer)
    healer.labware_kinds = {lid: s["kind"] for lid, s in deck()["labware"].items()}
    return healer._transfers(protocol)


def test_intent_guard_protects_device_steps_and_empties():
    p = demo()
    base = _fingerprint(p)

    shorter = copy.deepcopy(p)
    step_of(shorter, "incubate")["duration_s"] = 1800
    assert any("incubate corning_3595 at 37 C" in c for c in SelfHealer._intent_violations(base, _fingerprint(shorter)))

    slower = copy.deepcopy(p)
    step_of(slower, "shake")["speed_rpm"] = 600
    assert SelfHealer._intent_violations(base, _fingerprint(slower))

    no_rest = copy.deepcopy(p)
    no_rest["steps"] = no_rest["steps"][:-1]  # drop the room-temperature rest
    assert any("room temperature" in c for c in SelfHealer._intent_violations(base, _fingerprint(no_rest)))

    skipped = copy.deepcopy(p)
    skipped["steps"].remove(step_of(skipped, "empty"))
    assert any("empty" in c for c in SelfHealer._intent_violations(base, _fingerprint(skipped)))


def test_transfer_only_protocols_compile_as_before():
    v1 = json.loads((ROOT / "protocols" / "serial_dilution_v1.json").read_text())
    code = compile_protocol(v1, load_deck_config(str(CONFIG / "plr_deck.json")))
    assert "heater_shaker" not in code
    assert code.splitlines()[1:4] == ["", "", "async def run_protocol(lh, res):"]
