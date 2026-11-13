"""The static library that describes the real system: VENUS's labware library (config/Labware), the
instrument (config/instrument/, config/ML_Starlet.tpl) and the hand-off to AHC (pipeline/ahc_export.py)."""

import asyncio
import copy
import json
from pathlib import Path

import pytest
import pylabrobot.resources as plr
from pylabrobot.legacy.liquid_handling.backends import STARBackend

from pipeline.ahc_export import load_ahc_types, to_ahc_layout
from pipeline.deck import INSTRUMENT_DECK, DeckError, build_deck, load_deck_config
from pipeline.labware_limits import labware_limits
from pipeline.self_heal import SelfHealer
from pipeline.setup_guide import _used_labware
from pipeline.stage0_drafter import deck_summary
from pipeline.stage1_verifier import Verifier
from pipeline.instrument import InstrumentError, apply_to_deck, check, head96_a1, load_instrument
from pipeline.venus_labware import (VenusLabwareError, carrier_sites, check_map, compare, find, make, rack_geometry,
                                    read_cfg)
from pipeline.venus_layout import compare_with_deck, deck_config_from_lay, load_venus_map, read_lay

ROOT = Path(__file__).resolve().parent.parent / "plugin"  # the plugin: code and ground truth
TESTS = Path(__file__).resolve().parent


# --- VENUS's labware library ---

def test_find_takes_venus_paths_in_any_case_and_escaped():
    assert find("ML_STAR\\STF_L.rck").name == "STF_L.rck"
    assert find("CORNING-COSTAR\\\\cos_96_pcr.ctr").name == "Cos_96_PCR.ctr"  # as a .rck cites its .ctr
    with pytest.raises(VenusLabwareError):
        find("ML_STAR/NO_SUCH.rck")


def test_carrier_sites_are_front_first_with_venus_positions():
    sites = carrier_sites(read_cfg(find("ML_STAR/PLT_CAR_L5_DWP.tml")))
    assert [(s["position"], s["y"]) for s in sites] == [(5, 9.0), (4, 105.0), (3, 201.0), (2, 297.0), (1, 393.0)]


def test_rack_a1_is_at_the_back_left():
    geometry = rack_geometry(read_cfg(find("ML_STAR/STF_L.rck")))
    assert geometry["a1"] == (11.7, 72.8)  # PyLabRobot's 300 uL rack has its A1 there too


def test_plr_definitions_against_venus():
    assert compare("TIP_CAR_480_A00", "ML_STAR/TIP_CAR_480_A00.tml") == []
    assert compare("PLT_CAR_L5AC_A00", "ML_STAR/PLT_CAR_L5AC_A00.tml") == []
    assert compare("hamilton_96_tiprack_300uL_filter", "ML_STAR/STF_L.rck") == []
    diffs = compare("PLT_CAR_L5_DWP", "ML_STAR/PLT_CAR_L5_DWP.tml")
    assert "position 3 y: PyLabRobot 200.2, VENUS 201 (-0.80 mm)" in diffs


def test_a_carrier_built_from_venus_keeps_plrs_classes():
    carrier = make("ML_STAR/PLT_CAR_L5_DWP.tml", "car", factory="PLT_CAR_L5_DWP")
    assert type(carrier).__name__ == "PlateCarrier"
    assert [round(s.location.y, 2) for s in carrier.sites.values()] == [9.0, 105.0, 201.0, 297.0, 393.0]


def test_a_plate_built_from_venus_has_its_wells_and_volumes():
    plate = make("CORNING-COSTAR/Cos_96_PCR.rck", "pcr")
    a1 = plate.get_item("A1")
    center = a1.location + a1.center()
    assert (plate.get_size_x(), plate.get_size_y(), plate.get_size_z()) == (127.0, 86.0, 22.5)
    assert (round(center.x, 2), round(center.y, 2)) == (14.0, 74.5)
    # VENUS: 0-11.5 mm at 6.545 mm2, 11.5-20.5 mm at 23.8237 mm2
    assert a1.compute_volume_from_height(11.5) == pytest.approx(75.27, abs=0.01)
    assert a1.max_volume == pytest.approx(289.68, abs=0.01)
    assert a1.compute_height_from_volume(a1.compute_volume_from_height(15.0)) == pytest.approx(15.0)


def test_the_map_refuses_plr_geometry_that_differs_from_venus():
    venus_map = load_venus_map(ROOT)
    assert check_map(venus_map, ROOT)["TIP_CAR_480_A00"] == []
    venus_map["labware"]["PLT_CAR_L5_DWP"]["build"] = "plr"
    with pytest.raises(VenusLabwareError, match="Set \"build\": \"venus\""):
        check_map(venus_map, ROOT)


# --- the instrument ---

def test_the_instrument_matches_its_sources():
    instrument = load_instrument()
    assert instrument["serial"] == "F553" and instrument["head96"]["eject"]["z_mm"] == 229.0


def test_a_stale_fact_fails_on_load():
    instrument = load_instrument()
    firmware = json.loads((ROOT / instrument["firmware_configuration"]).read_text())["device"]
    template = read_lay((ROOT / instrument["deck_template"]["file"]).read_bytes())
    layout = read_lay((ROOT / instrument["deck_layout"]["file"]).read_bytes())
    assert check(instrument, firmware, template, layout) == []
    stale = copy.deepcopy(instrument)
    stale["channels"]["count"] = 4
    stale["head96"]["eject"]["y_mm"] = 178.8
    problems = " ".join(check(stale, firmware, template, layout))
    assert "channels.count" in problems and "head96.eject" in problems


def test_plr_alone_lowers_the_96_head_further_than_venus():
    assert head96_a1(plr.STARLetDeck()).z == pytest.approx(216.4)


def test_the_deck_initializes_the_96_head_as_venus_does():
    deck, _ = build_deck(load_deck_config(str(ROOT / INSTRUMENT_DECK)))
    sent = {}

    async def send_command(**kwargs):
        sent.update(kwargs)

    backend = STARBackend()
    backend.set_deck(deck)
    backend.send_command = send_command
    asyncio.run(backend.initialize_core_96_head(trash96=deck.get_trash_area96()))
    # VENUS: C0EI xs00420 xd1 yh1203, lowered to 229.0 mm
    assert (sent["xs"], sent["xd"], sent["yh"], sent["za"]) == ("00420", 1, "1203", "2290")


def test_apply_refuses_a_deck_whose_96_waste_moved():
    deck = plr.STARLetDeck()
    trash = deck.get_trash_area96()
    trash.location = plr.Coordinate(trash.location.x, trash.location.y + 58.5, trash.location.z)
    with pytest.raises(InstrumentError, match="not at VENUS's"):
        apply_to_deck(deck, load_instrument())


# --- AHC ---

def lay_deck():
    lay = read_lay((ROOT / "config" / "instrument" / "ahc_deck.lay").read_bytes())
    return deck_config_from_lay(lay, load_venus_map(ROOT))[0]


AHC_COPY = dict(root=ROOT, plugins=ROOT / "no-ahc-installed-here")  # the repo's copy of AHC's list, on any machine


def test_ahc_gets_the_whole_real_deck_and_hears_where_its_models_differ():
    layout, problems, warnings = to_ahc_layout(lay_deck(), load_ahc_types(**AHC_COPY))
    tips = next(c for c in layout["carriers"] if c["type"] == "TIP_CAR_480_A00")
    assert tips["track"] == 7 and tips["sites"]["4"] == {"name": "STF_L_0001", "type": "hamilton_96_tiprack_300uL_filter"}
    assert problems == []
    plates = next(c for c in layout["carriers"] if c["type"] == "PLT_CAR_L5_DWP")["sites"]
    assert {s["name"]: s["type"] for s in plates.values()} == {  # VENUS's PCR plate, by its declared AHC equivalent
        "Cos_96_PCR_0001": "Cor_96_wellplate_360ul_Fb", "Cos_96_PCR_0002": "Cor_96_wellplate_360ul_Fb"}
    assert "PLT_CAR_L5_DWP" in warnings[0] and "0.80 mm" in warnings[0]
    assert sum("Cos_96_PCR goes to AHC as Cor_96_wellplate_360ul_Fb" in w for w in warnings) == 2


# --- the real deck as ground truth ---

def instrument_deck():
    return load_deck_config(str(ROOT / INSTRUMENT_DECK))


def test_the_instrument_deck_is_the_venus_layout():
    deck = instrument_deck()
    assert deck["instrument"] == "config/instrument/starlet_F553.json"
    assert {lid for lid, s in deck["labware"].items() if s["kind"] == "plate"} == {"Cos_96_PCR_0001", "Cos_96_PCR_0002"}


def test_a_layout_with_an_unbuildable_item_is_not_a_deck(monkeypatch):
    import pipeline.venus_layout as venus_layout
    real = venus_layout.load_venus_map

    def without_pcr(root):
        venus_map = real(root)
        venus_map["labware"]["Cos_96_PCR"] = {"factory": None, "kind": "plate"}
        return venus_map

    monkeypatch.setattr(venus_layout, "load_venus_map", without_pcr)
    with pytest.raises(DeckError, match="Cos_96_PCR_0001"):
        load_deck_config(str(ROOT / INSTRUMENT_DECK))


def test_plate_limits_come_from_venus_geometry_and_policy():
    pcr = labware_limits(instrument_deck())["plates"]["Cos_96_PCR_0001"]["well_specifications"]["well_volume_range"]
    assert (pcr["min_ul"], pcr["max_ul"], pcr["capacity_ul"]) == (30, 260.7, 289.7)  # 0.9 of VENUS's 289.7 uL


def test_the_verifier_tracks_each_plate_on_its_own(tmp_path):
    tips = {"step": 1, "action": "tips_on", "labware": "STF_L_0001", "column": 1, "volume_ul": 0, "channels": [0]}
    fill = {"step": 2, "action": "dispense", "labware": "Cos_96_PCR_0001", "column": 1, "volume_ul": 100, "channels": [0]}
    draw = {"step": 3, "action": "aspirate", "labware": "Cos_96_PCR_0002", "column": 1, "volume_ul": 50, "channels": [0]}
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps({"steps": [tips, fill, draw]}))
    verdict = Verifier(labware_limits(instrument_deck()), str(plan)).run_verification()
    assert verdict["error_code"] == "DRY_ASPIRATE"  # plate 2 is empty, whatever plate 1 holds


def test_a_protocol_on_the_instrument_deck_passes_stages_1_to_3_and_matches_the_layout(tmp_path):
    deck = instrument_deck()
    protocol = {"protocol_name": "tip check", "deck_config": INSTRUMENT_DECK, "steps": [
        {"step": 1, "action": "tips_on", "labware": "STF_L_0001", "column": 1, "volume_ul": 0, "channels": list(range(8))},
        {"step": 2, "action": "tips_off", "labware": "waste", "volume_ul": 0, "channels": list(range(8))}]}
    gate = SelfHealer(deck, work_dir=str(tmp_path)).evaluate(protocol, 0)
    assert gate.passed, gate.summary
    assert compare_with_deck(lay_deck(), deck, _used_labware(protocol))["ok"]


def test_the_drafter_sees_the_real_labware_and_its_limits():
    summary = deck_summary(instrument_deck())
    assert "Cos_96_PCR_0001: 96-well plate, 289.7 uL wells, usable 30-260.7 uL" in summary["deck"]
    assert (summary["well_min"], summary["well_max"]) == (30, 260.7)
