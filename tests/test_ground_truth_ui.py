"""The demo's Library, Check and Execute pages show only ground truth: VENUS's labware library and the deck on the
STARlet (config/instrument/ahc_deck.lay). Nothing hand-written."""

import json
import warnings
from pathlib import Path

import pytest

warnings.simplefilter("ignore")
ROOT = Path(__file__).resolve().parent.parent
REFERENCE_ONLY = {"corning_3595", "reservoir_50ml", "tube_15ml", "hamilton_tiprack_96", "cor_96_wellplate_360uL_Fb"}


def test_the_library_lists_venus_labware_and_nothing_hand_written():
    from pipeline import library_view

    inv = library_view.inventory(ROOT)
    listed = {k for group in ("plates", "tips", "reagent_containers") for k in inv[group]}
    assert listed and not (listed & REFERENCE_ONLY)
    assert "Cos_96_PCR" in inv["plates"] and "STF_L" in inv["tips"]
    # every item says which VENUS file it came from
    assert all(item["source"].lower().endswith((".rck", ".ctr", ".tml")) for g in ("plates", "tips", "reagent_containers")
               for item in inv[g].values())


def test_the_library_deck_is_the_stararlet_layout_from_venus():
    from pipeline import library_view

    deck = library_view.instrument_deck(ROOT)
    assert deck["file"] == "ahc_deck.lay"
    labware = {spec["factory"] for spec in deck["labware"].values() if "factory" in spec}
    assert not (labware & REFERENCE_ONLY)
    assert {spec["venus_type"] for spec in deck["labware"].values() if spec.get("venus_type")} <= set(
        library_view.inventory(ROOT)["plates"]) | set(library_view.inventory(ROOT)["tips"]) | {
        "Cos_96_PCR", "STF_L", "Reservoir", "RGT_CONT_50ml_A00", "Tube_CAR_24_A00"} | {
        s["venus_type"] for s in deck["carriers"]}


@pytest.mark.parametrize("path", ["/api/library", "/api/protocols"])
def test_the_api_serves_no_reference_labware(path):
    import demo.server as server

    body = json.dumps(server.app.test_client().get(path).get_json())
    for name in ("corning_3595", "reservoir_50ml", "config/reference"):
        assert name not in body, name


