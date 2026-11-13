"""The repair guard: a repair may restructure the steps, but every plate well must end with the same volume and reagents,
and every heated or shaken hold must keep its time. Air in the tip never reaches a well, so it is free."""

import json
from pathlib import Path

import pytest


from pipeline.deck import INSTRUMENT_DECK, load_deck_config
from pipeline.flow import NotPassing, finish
from pipeline.self_heal import SelfHealer

ROOT = Path(__file__).resolve().parent.parent / "plugin"  # the plugin: code and ground truth
TESTS = Path(__file__).resolve().parent


@pytest.fixture(scope="module")
def healer():
    # A protocol-sized deck with a reservoir ("diluent") to draw from and a plate ("dilution_plate") to fill.
    deck = load_deck_config(str(TESTS / "fixtures" / "serial_deck.json"))
    return SelfHealer(deck, work_dir="build/test_piston")


def _protocol(*steps, source="diluent"):
    return {"steps": [dict(s, step=i + 1) for i, s in enumerate(steps)],
            "initial_volumes_ul": {source: 5000}, "reagents": {source: "saline" if source == "diluent" else "culture"}}


def _fill(volume, column=1):
    return {"action": "dispense", "labware": "dilution_plate", "column": column, "volume_ul": volume, "channels": [0]}


def _draw(volume, labware="diluent"):
    return {"action": "aspirate", "labware": labware, "volume_ul": volume, "channels": [0]}


def _violations(healer, plan, candidate):
    return healer._intent_violations(healer._transfers(plan), healer._transfers(candidate))


def test_more_air_drawn_with_the_same_wells_is_allowed(healer):
    # 90 uL dispensed into the well either way; the first draw takes 5 uL more, which stays in the tip.
    plan = _protocol(_draw(90), _fill(90))
    more_air = _protocol(_draw(95), _fill(90))
    assert _violations(healer, plan, more_air) == []


def test_restructuring_that_keeps_the_wells_is_allowed(healer):
    # One aspirate of 180 uL split into two of 90 uL, each dispensed as planned.
    plan = _protocol(_draw(180), _fill(90, column=2), _fill(90, column=3))
    split = _protocol(_draw(90), _fill(90, column=2), _draw(90), _fill(90, column=3))
    assert _violations(healer, plan, split) == []


def test_a_changed_well_volume_is_refused(healer):
    plan = _protocol(_draw(90), _fill(90))
    smaller = _protocol(_draw(80), _fill(80))  # a dilution changed to avoid an error
    changed = _violations(healer, plan, smaller)
    assert changed and any("ends with" in c for c in changed)


def test_a_changed_reagent_mix_is_refused_even_at_the_same_volume(healer):
    # Same 90 uL in the well, but drawn from a different reagent: a different experiment.
    plan = _protocol(_draw(90, labware="diluent"), _fill(90), source="diluent")
    other = _protocol(_draw(90, labware="culture"), _fill(90), source="culture")
    changed = _violations(healer, plan, other)
    assert changed and any("of" in c for c in changed)


def test_a_changed_hold_is_refused(healer):
    plan = _protocol({"action": "incubate", "labware": "plate", "duration_s": 60, "temperature_c": 37})
    shorter = _protocol({"action": "incubate", "labware": "plate", "duration_s": 30, "temperature_c": 37})
    assert _violations(healer, plan, shorter)


def test_a_protocol_that_does_not_pass_is_not_written(tmp_path):
    protocol = json.loads((TESTS / "fixtures" / "serial_piston_failing.json").read_text())
    deck = load_deck_config(str(TESTS / "fixtures" / "serial_deck.json"))
    healed = tmp_path / "healed"
    with pytest.raises(NotPassing) as refused:
        finish(protocol, deck, "not_ready", [], status="HEALED", healed=healed)
    assert refused.value.gate.detail["error_code"] == "PISTON_TRAVEL"
    assert not healed.exists() or not any(healed.iterdir())
