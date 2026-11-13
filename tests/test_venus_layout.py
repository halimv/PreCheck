"""Venus deck layout import (pipeline/venus_layout.py) on a real .lay: the deck on the lab's STARlet on
2026-11-11 (tests/fixtures/venus/ahc_deck.lay, saved by Venus 6.4), with VENUS's labware library in config/Labware."""

import json
from pathlib import Path

import pytest

from pipeline.deck import load_deck_config
from pipeline.setup_guide import _used_labware
from pipeline.venus_layout import (LayoutError, compare_with_deck, deck_config_from_lay, import_layout,
                                   load_venus_map, position_checks, read_lay)

ROOT = Path(__file__).resolve().parent.parent / "plugin"  # the plugin: code and ground truth
TESTS = Path(__file__).resolve().parent
LAY = TESTS / "fixtures" / "venus" / "ahc_deck.lay"


def pairs():
    return read_lay(LAY.read_bytes())


def test_reads_the_binary_layout():
    p = pairs()
    assert p["Deck"] == "ML_Starlet.dck"
    assert p["Labware.10.File"] == "ML_STAR\\STF_L.rck"
    assert p["Labware.10.Template"] == "TIP_CAR_480_A00_0001"


def test_rejects_a_file_that_is_not_a_layout():
    with pytest.raises(LayoutError):
        read_lay(b"HxCfgFile,3;\nnot binary")
    with pytest.raises(LayoutError):
        read_lay(b"\x00" * 64)


def test_carriers_go_on_rails_and_positions_count_from_the_back():
    config, _ = deck_config_from_lay(pairs(), load_venus_map(ROOT), "ahc_deck.lay")
    assert config["deck"] == "STARLetDeck"
    assert {c["name"]: (c["factory"], c["rails"]) for c in config["carriers"]} == {
        "PLT_CAR_L5_DWP_0001": ("PLT_CAR_L5_DWP", 1), "TIP_CAR_480_A00_0001": ("TIP_CAR_480_A00", 7)}
    # Hamilton position 1 (rear-most) of a 5-position carrier is PLR site 4.
    assert config["labware"]["STF_L_0001"]["slot"] == 4
    assert config["labware"]["STF_L_0002"]["slot"] == 3
    assert config["labware"]["waste"]["kind"] == "trash"


def test_labware_without_a_plr_definition_is_built_from_venus():
    config, problems = deck_config_from_lay(pairs(), load_venus_map(ROOT), "ahc_deck.lay")
    assert problems == []
    assert config["labware"]["Cos_96_PCR_0001"] == {
        "factory": "Cos_96_PCR", "venus": "CORNING-COSTAR/Cos_96_PCR.rck", "build": "venus", "venus_type": "Cos_96_PCR",
        "carrier": "PLT_CAR_L5_DWP_0001", "slot": 2, "kind": "plate", "venus_position": 3}


def test_labware_with_neither_definition_is_reported_not_guessed():
    venus_map = load_venus_map(ROOT)
    venus_map["labware"]["Cos_96_PCR"] = {"factory": None, "kind": "plate"}
    config, problems = deck_config_from_lay(pairs(), venus_map, "ahc_deck.lay")
    assert sorted(p["id"] for p in problems) == ["Cos_96_PCR_0001", "Cos_96_PCR_0002"]
    assert "Cos_96_PCR_0001" not in config["labware"]


def test_an_unknown_venus_type_is_a_problem():
    venus_map = load_venus_map(ROOT)
    del venus_map["labware"]["STF_L"]
    _, problems = deck_config_from_lay(pairs(), venus_map)
    assert {"STF_L_0001", "STF_L_0002"} <= {p["id"] for p in problems}


def test_plr_positions_agree_with_the_layout():
    config, _ = deck_config_from_lay(pairs(), load_venus_map(ROOT))
    checks = position_checks(pairs(), config)
    assert {c["id"] for c in checks} == {"PLT_CAR_L5_DWP_0001", "TIP_CAR_480_A00_0001", "STF_L_0001", "STF_L_0002",
                                         "Cos_96_PCR_0001", "Cos_96_PCR_0002", "waste"}
    assert all(c["ok"] for c in checks), checks


def test_a_factory_with_other_geometry_shows_up_as_a_position_difference():
    config, _ = deck_config_from_lay(pairs(), load_venus_map(ROOT))
    # A 384-well plate's A1 is not where a 96-well plate's is. (PyLabRobot 1.0 refuses a plate on a tip carrier
    # outright, so the mismatch is made on a plate position.)
    spec = config["labware"]["Cos_96_PCR_0001"]
    spec["factory"] = "Greiner_384_wellplate_28ul_Fb"
    del spec["build"], spec["venus"]
    bad = [c for c in position_checks(pairs(), config) if not c["ok"]]
    assert {c["id"] for c in bad} == {"Cos_96_PCR_0001"}


def test_tip_size_is_not_visible_in_positions():
    # 300 and 1000 uL racks share a footprint, so only the Venus type -> factory map guards the tip size.
    config, _ = deck_config_from_lay(pairs(), load_venus_map(ROOT))
    config["labware"]["STF_L_0001"]["factory"] = "hamilton_96_tiprack_1000uL_filter"
    checks = position_checks(pairs(), config)
    assert all(c["ok"] for c in checks if "dz" not in c)
    # ...but the heights do show it: a 1000 uL tip is not as long as VENUS's 300 uL one.
    assert {(c["id"], c["what"]) for c in checks if not c["ok"]} == {("STF_L_0001", "tip top height"),
                                                                    ("STF_L_0001", "tip end height")}


def test_a_protocol_on_the_layouts_own_deck_matches():
    lay_deck, _ = deck_config_from_lay(pairs(), load_venus_map(ROOT))
    result = compare_with_deck(lay_deck, lay_deck, ["STF_L_0001", "STF_L_0002", "waste"])
    assert result["ok"]
    assert [i["venus_id"] for i in result["items"]] == ["STF_L_0001", "STF_L_0002"]


def test_import_layout_bundles_everything_the_page_shows():
    report = import_layout(LAY.read_bytes(), "ahc_deck.lay", ROOT)
    assert report["venus_version"] == "6.4.0.51040"
    assert len(report["items"]) == 14
    assert report["problems"] == [] and all(c["ok"] for c in report["positions"])
