"""The run summary and the review list: what must be done before a run, and what a person should check."""

from pipeline.summary import failure_markdown, review_items


def test_operator_changes_and_unloadable_items_must_be_done_before_a_run(tmp_path):
    deck = tmp_path / "d.json"
    deck.write_text("{}")
    (tmp_path / "d.mapping.json").write_text('{"operator_changes": ["diluent: add carrier RGT_CONT_50ml_A00"]}')
    items = review_items({"steps": []}, [], {"assumptions": [], "wells": []}, [],
                         {"not_on_layout": ["dilution_plate is not labware AHC accepts"], "differs_from_venus": []},
                         deck_path=deck, passed=True)
    musts = [i["item"] for i in items if i["severity"] == "must"]
    assert "Place on the deck before the run" in musts and "AHC cannot load this item" in musts


def test_assumptions_and_repairs_are_checks_not_blockers():
    rounds = [{"round": 1, "model": "claude-sonnet-5-5", "result": "PISTON_TRAVEL", "edits_applied": [{"op": "replace_step"}]}]
    items = review_items({"steps": []}, rounds, {"assumptions": ["Six dilutions chosen."], "wells": []}, [],
                         {"not_on_layout": [], "differs_from_venus": []}, passed=True)
    assert [i["severity"] for i in items] == ["check", "check"]
    assert any("Repair in round 1" in i["item"] for i in items)


def test_a_shallow_liquid_suggestion_is_a_must():
    suggestions = [{"id": "liquid_too_shallow", "title": "'culture' starts 0.2 mm deep", "detail": "Load more."}]
    items = review_items({"steps": []}, [], {"assumptions": [], "wells": []}, suggestions,
                         {"not_on_layout": [], "differs_from_venus": []}, passed=True)
    assert items == [{"severity": "must", "area": "liquid", "item": "'culture' starts 0.2 mm deep", "detail": "Load more."}]


def test_a_failed_run_says_it_is_not_ready_and_points_to_the_heal_log(tmp_path):
    log = tmp_path / "heal_log.json"
    tiers = [{"model": "claude-haiku-5-5", "status": "GAVE_UP", "rounds": [{"round": 0, "result": "PISTON_TRAVEL"}]}]
    text = failure_markdown({"protocol_name": "X", "steps": []}, tiers, 1, log)
    assert "NOT READY" in text and "claude-haiku-5-5: 0 round(s), GAVE_UP" in text and str(log) in text
