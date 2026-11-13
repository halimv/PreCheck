"""Stage 0b, the deck builder (pipeline/deck_builder.py): a protocol's labware needs resolved against the deck on
the STARlet (config/instrument/ahc_deck.lay) and VENUS's labware library (config/Labware), and the drafter's loop
that sends needs nothing fits back to Claude. Then the built deck through compile and simulate."""

import io
import json
import sys
from pathlib import Path

import pytest

from pipeline.deck import INSTRUMENT_DECK, build_deck, load_deck_config
from pipeline.deck_builder import catalog, need_errors, resolve
from pipeline.self_heal import SelfHealer
from pipeline.venus_labware import VenusLabwareError, volume_equation

ROOT = Path(__file__).resolve().parent.parent / "plugin"  # the plugin: code and ground truth
TESTS = Path(__file__).resolve().parent

SERIAL_DILUTION = {
    "tips": {"kind": "tip_rack", "tip_volume_ul": 300, "filter": True},
    "dilution_plate": {"kind": "plate", "wells": 96, "min_capacity_ul": 150},
    "saline": {"kind": "reservoir", "min_capacity_ul": 6000},
    "culture": {"kind": "tube", "min_capacity_ul": 5000},
    "waste": {"kind": "waste"},
}


def base():
    return load_deck_config(str(ROOT / INSTRUMENT_DECK))


def by_type(kind):
    return {e["venus_type"]: e for e in catalog() if e["kind"] == kind}


# --- the catalog ---

def test_the_catalog_reads_venus_labware_by_its_structure():
    assert "Cos_96_PCR" in by_type("plate")
    assert by_type("tip_rack")["STF_L"]["tip_volume_ul"] == 300 and by_type("tip_rack")["STF_L"]["filter"]
    assert by_type("reservoir")["RGT_CONT_50ml_A00"]["capacity_ul"] == 63000.0  # VENUS's 8 connected positions of 7875 uL
    assert by_type("tube_rack")["Car24_Cup15x100"]["positions"] == 24
    assert "RGT_CAR_5R60_A00" in by_type("carrier")
    excluded = {e["venus_type"].lower() for e in catalog()}
    assert not excluded & {"teachingneedle5ml", "verification", "rgt_20ml_lid_black"}  # parts and lids, not labware


def test_tip_racks_need_a_plr_tip_model():
    assert set(by_type("tip_rack")) == {"STF_L", "ST_L", "HTF_L", "HT_L", "LTF_L", "LT_L", "TIP_50ulF_L"}


def test_volume_equations_are_arithmetic_in_h_only():
    cap = volume_equation("h*h*(19.3208 - 1.0472*h)")  # a round tube bottom
    assert cap(6.15) == pytest.approx(487.1, abs=0.1)
    for bad in ("__import__('os').getcwd()", "h.real", "x*2", "[h]"):
        with pytest.raises(VenusLabwareError):
            volume_equation(bad)


# --- resolving needs ---

def test_a_serial_dilution_uses_the_deck_first_then_the_library():
    r = resolve(SERIAL_DILUTION, base(), name="test")
    assert r.ok, r.unresolved
    m = r.mapping["labware"]
    assert (m["tips"]["action"], m["tips"]["on_deck_as"], m["tips"]["barcode"]) == ("on_deck", "STF_L_0001", "235903************")
    assert m["dilution_plate"]["action"] == "on_deck" and m["dilution_plate"]["venus_type"] == "Cos_96_PCR"
    assert m["dilution_plate"]["carrier"]["barcode"] == "SR11****"
    assert (m["saline"]["action"], m["saline"]["venus_type"], m["saline"]["carrier"]["venus_type"]) == \
        ("add_carrier", "RGT_CONT_50ml_A00", "RGT_CAR_5R60_A00")
    assert m["saline"]["carrier"]["rails"] == 13  # the first free rail: the .lay's carriers take 1-12
    assert m["culture"]["action"] == "add_carrier" and m["culture"]["capacity_ul"] >= 5000
    assert len(r.mapping["operator_changes"]) == 2


def test_the_built_deck_names_labware_by_ir_name_and_keeps_the_rest():
    config = resolve(SERIAL_DILUTION, base()).deck_config
    assert {"tips", "dilution_plate", "saline", "culture", "waste"} <= set(config["labware"])
    assert config["labware"]["tips"]["venus_id"] == "STF_L_0001"
    assert "STF_L_0002" in config["labware"]  # still on the deck, unused
    _, res = build_deck(config)
    assert res["saline"].max_volume == pytest.approx(63000.0)  # the whole trough: 8 connected positions
    assert res["saline"].get_size_y() == pytest.approx(77.5) and len(res["saline"].venus_access_y) == 8


def test_two_tubes_share_one_new_tube_rack():
    needs = {"a": {"kind": "tube", "min_capacity_ul": 5000}, "b": {"kind": "tube", "min_capacity_ul": 5000}}
    m = resolve(needs, base()).mapping["labware"]
    assert m["a"]["carrier"]["name"] == m["b"]["carrier"]["name"]
    assert m["a"]["position"]["hamilton"] == 1 and m["b"]["position"]["hamilton"] == 2


def test_a_need_nothing_fits_comes_back_with_the_closest_options():
    r = resolve({"culture": {"kind": "tube", "min_capacity_ul": 500000}, "waste": {"kind": "waste"}}, base())
    assert not r.ok
    assert "no tube in the library fits at least 500000 uL" in r.unresolved["culture"]
    assert "Closest:" in r.unresolved["culture"] and "mL" in r.unresolved["culture"]


def test_need_errors_check_the_labware_section():
    assert need_errors({"x": {"kind": "beaker"}}) == ["labware 'x' needs a kind, one of tip_rack, plate, reservoir, tube, waste"]
    assert need_errors({}) and need_errors(None)


def test_a_protocol_on_the_built_deck_compiles_and_simulates(tmp_path):
    config = resolve(SERIAL_DILUTION, base()).deck_config
    protocol = {"initial_volumes_ul": {"saline": 5000, "culture": 4000}, "steps": [
        {"step": 1, "action": "tips_on", "labware": "tips", "column": 1, "volume_ul": 0, "channels": [0]},
        {"step": 2, "action": "aspirate", "labware": "saline", "volume_ul": 90, "channels": [0]},
        {"step": 3, "action": "dispense", "labware": "dilution_plate", "column": 1, "volume_ul": 90, "channels": [0]},
        {"step": 4, "action": "aspirate", "labware": "culture", "volume_ul": 10, "channels": [0]},
        {"step": 5, "action": "dispense", "labware": "dilution_plate", "column": 1, "volume_ul": 10, "channels": [0]},
        {"step": 6, "action": "tips_off", "labware": "waste", "volume_ul": 0, "channels": [0]}]}
    gate = SelfHealer(config, work_dir=str(tmp_path)).evaluate(protocol, 0)
    assert gate.passed, gate.summary


def test_the_verifier_is_out_of_the_loop(tmp_path):
    # Leaves 5 uL in a well: the stage 1 verifier's dead-volume rule would refuse it; the simulator does not.
    config = resolve(SERIAL_DILUTION, base()).deck_config
    protocol = {"initial_volumes_ul": {}, "steps": [
        {"step": 1, "action": "tips_on", "labware": "tips", "column": 1, "volume_ul": 0, "channels": [0]},
        {"step": 2, "action": "dispense", "labware": "dilution_plate", "column": 1, "volume_ul": 0, "channels": [0]},
        {"step": 3, "action": "tips_off", "labware": "waste", "volume_ul": 0, "channels": [0]}]}
    gate = SelfHealer(config, work_dir=str(tmp_path)).evaluate(protocol, 0)
    assert gate.stage == "simulate"


# --- the drafter's loop ---

def test_the_drafter_sends_unresolved_needs_back_to_claude(tmp_path, monkeypatch):
    """A stand-in CLI first asks for a tube nothing in the library holds, then, told so, a smaller one."""
    import pipeline.stage0_drafter as drafter

    plan = {"protocol_name": "dilution", "labware": {**SERIAL_DILUTION, "culture": {"kind": "tube", "min_capacity_ul": 500000}},
            "initial_volumes_ul": {"saline": 5000}, "steps": [
                {"action": "tips_on", "labware": "tips", "column": 1, "volume_ul": 0, "channels": [0]},
                {"action": "aspirate", "labware": "saline", "volume_ul": 90, "channels": [0]},
                {"action": "dispense", "labware": "dilution_plate", "column": 1, "volume_ul": 90, "channels": [0]},
                {"action": "tips_off", "labware": "waste", "volume_ul": 0, "channels": [0]}]}
    fixed = {**plan, "labware": SERIAL_DILUTION}
    prompts = tmp_path / "prompts.jsonl"
    fake = tmp_path / "claude"
    fake.write_text(f"""#!{sys.executable}
import json, sys
prompt = sys.stdin.read()
open({str(prompts)!r}, "a").write(json.dumps(prompt) + "\\n")
plan = {json.dumps(fixed)!r} if "No real labware was found" in prompt else {json.dumps(plan)!r}
print(json.dumps({{"type": "result", "is_error": False, "result": "```json\\n" + plan + "\\n```", "session_id": "s"}}))
""")
    fake.chmod(0o755)
    monkeypatch.setattr(drafter, "CLAUDE_BIN", str(fake))

    d = drafter.draft("Serially dilute the culture 1:10 in saline.", base(), out=io.StringIO(),
                      drafts_dir=tmp_path / "drafts", decks_dir=tmp_path / "decks", stem="dilution")
    sent = [json.loads(line) for line in prompts.read_text().splitlines()]
    assert len(sent) == 2 and d.deck_rounds == 1
    assert "On the deck now" in sent[0] and "rack of 96 300 uL tips with filter" in sent[0]
    assert "culture: no tube in the library fits at least 500000 uL" in sent[1]
    assert d.protocol["deck_config"] == str(d.deck_path) and d.deck_path == tmp_path / "decks" / "dilution.json"
    mapping = json.loads(d.mapping_path.read_text())
    assert mapping["labware"]["culture"]["action"] == "add_carrier"
    assert set(load_deck_config(str(d.deck_path))["labware"]) >= set(SERIAL_DILUTION)


# --- the Execute page's view of the real deck ---

def test_the_execute_page_draws_the_real_deck_with_what_the_protocol_adds():
    import demo.server as server

    config = resolve(SERIAL_DILUTION, base()).deck_config
    protocol = {"steps": [{"action": "aspirate", "labware": name} for name in ("tips", "saline", "dilution_plate")]}
    view = server._real_deck_view(protocol, config)
    carriers = {c["name"]: c for c in view["drawing"]["carriers"]}
    assert not carriers["TIP_CAR_480_A00_0001"]["added"] and carriers["RGT_CAR_5R60_A00_13"]["added"]
    sites = {lw["id"]: lw for c in carriers.values() for lw in c["labware"]}
    assert sites["tips"]["used"] and not sites["tips"]["added"]  # STF_L_0001, drawn under its IR name
    assert sites["saline"]["added"]
    assert "STF_L_0002" in sites and not sites["STF_L_0002"]["used"]  # on the deck, not used
    assert view["drawing"]["show_use"] and view["warning"] is None


def test_built_decks_serialize_for_the_visualizer():
    # PyLabRobot's visualizer sends every resource as JSON, volume functions included.
    from pylabrobot.serializer import serialize

    for config in (base(), resolve(SERIAL_DILUTION, base()).deck_config):
        deck, _ = build_deck(config)
        json.dumps(serialize(deck))
