"""The diagnostics knowledge base (knowledge/diagnostics.json): it loads, every entry can be
reached, a mistake in a hand edit is reported when the file is loaded, and self-healing runs
are recorded into it."""

import datetime
import json
from pathlib import Path

import pytest
from pylabrobot.resources.errors import NoTipError, TooLittleLiquidError

from pipeline import diagnostics
from pipeline.deck import DeviceError, load_deck_config
from pipeline.self_heal import SelfHealer

ROOT = Path(__file__).resolve().parent.parent

STATE = {"container_volumes_ul": {"tube_15ml": 40.0}, "unused_tip_columns": {"tips": [4, 5]}}
PROTOCOL = {"steps": [{"step": 9, "action": "aspirate", "labware": "tube_15ml", "volume_ul": 300, "channels": [0, 1]}],
            "initial_volumes_ul": {"tube_15ml": 550}}


def translate(exc, step):
    return diagnostics.translate(exc, step, PROTOCOL, {}, STATE)


def test_loads_and_ends_with_a_catch_all():
    entries = diagnostics.knowledge_base()
    assert entries[-1]["code"] == "UNRECOGNIZED"
    assert "when" not in entries[-1]


def test_every_entry_is_reachable():
    """An entry hidden behind an earlier, broader one would never be used."""
    entries = diagnostics.knowledge_base()
    for i, entry in enumerate(entries[:-1]):
        for later in _as_cases(entry):
            first = next(j for j, e in enumerate(entries) if any(_cond_implies(later, c) for c in _when(e)))
            assert first == i, f"{entry['code']} ({entry['title']}) is shadowed by {entries[first]['code']}"


def _when(entry):
    return diagnostics._as_list(entry.get("when", {}))


def _as_cases(entry):
    return _when(entry)


def _cond_implies(case, cond):
    """True if every failure matching `case` also matches `cond` (on the keys both use)."""
    for key, value in cond.items():
        if key not in case:
            return False
        want = diagnostics._as_list(value)
        if key == "error":
            if not any(issubclass(diagnostics.EXCEPTIONS[c], tuple(diagnostics.EXCEPTIONS[w] for w in want))
                       for c in diagnostics._as_list(case[key])):
                return False
        elif key == "message_contains":
            if value not in case[key]:
                return False
        elif not set(diagnostics._as_list(case[key])) <= set(want):
            return False
    return True


def test_loaded_reagent_shortage_offers_only_the_volume_fix():
    diag = translate(TooLittleLiquidError("need 300uL"), PROTOCOL["steps"][0])
    assert diag["error_code"] == "INSUFFICIENT_LIQUID"
    assert diag["suggested_fixes"] == [
        "Have the scientist load more reagent (needed 600 uL plus a 10% margin): "
        '{"op": "set_initial_volume", "labware": "tube_15ml", "volume_ul": 700}. '
        "This keeps every step unchanged. Do not lower volume_ul: that changes the experiment and is rejected."
    ]


def test_matching_uses_action_and_device_code():
    tips_on = {"step": 2, "action": "tips_on", "labware": "tips", "column": 1, "channels": [0]}
    assert translate(NoTipError("x"), tips_on)["error_code"] == "TIP_SPOT_EMPTY"
    assert translate(NoTipError("x"), {**tips_on, "action": "dispense"})["error_code"] == "NO_TIP_MOUNTED"
    assert "[4, 5]" in translate(NoTipError("x"), tips_on)["suggested_fixes"][0]
    shake = {"step": 7, "action": "shake", "labware": "plate", "speed_rpm": 3000}
    assert translate(DeviceError("x", "SHAKE_SPEED_OUT_OF_RANGE"), shake)["error_code"] == "SHAKE_SPEED_OUT_OF_RANGE"
    assert translate(RuntimeError("boom"), None)["error_code"] == "UNRECOGNIZED"


def test_notes_are_not_sent_to_the_model():
    diag = translate(TooLittleLiquidError("need 300uL"), PROTOCOL["steps"][0])
    assert "qwen" not in diag["explanation"] + " ".join(diag["suggested_fixes"])


@pytest.mark.parametrize("change, message", [
    (lambda e: e[0].update(cde="X"), "unknown field"),
    (lambda e: e[0]["when"][0].update(eror="ValueError"), "unknown condition"),
    (lambda e: e[0]["when"][0].update(error="ChannelDoesNotFit"), "unknown error class"),
    (lambda e: e[0].update(facts=["container_width"]), "unknown fact"),
    (lambda e: e[1].pop("when"), "only the last entry"),
    (lambda e: e[-1].update(when={"error": "ValueError"}), "every error is covered"),
    (lambda e: e[1].update(id=e[0]["id"]), "duplicate id"),
    (lambda e: e[0].update(fixes=[3]), "fixes must be"),
])
def test_mistakes_in_hand_edits_are_reported(tmp_path, change, message):
    kb = json.loads(diagnostics.KNOWLEDGE_BASE.read_text())
    change(kb["entries"])
    path = tmp_path / "diagnostics.json"
    path.write_text(json.dumps(kb))
    with pytest.raises(ValueError, match=message):
        diagnostics.knowledge_base(path)


# ---------- recording runs ----------

class Scripted:
    def __init__(self, *replies):
        self.replies = list(replies)

    def propose_edits(self, system, prompt):
        return self.replies.pop(0) if self.replies else {"reasoning": "", "edits": []}


def heal_demo(tmp_path, *replies, max_rounds=2):
    demo = json.loads((ROOT / "protocols" / "plate_wash_incubate_demo.json").read_text())
    config = ROOT / "config"
    healer = SelfHealer(load_deck_config(str(config / "reference" / "plr_deck_plate_assay.json")), Scripted(*replies), str(tmp_path / "work"))
    return healer.heal(demo, max_rounds=max_rounds)


@pytest.fixture
def kb_copy(tmp_path):
    """A copy of the knowledge base with nothing recorded yet."""
    kb = json.loads(diagnostics.KNOWLEDGE_BASE.read_text())
    for entry in kb["entries"]:
        entry.pop("observed", None)
    path = tmp_path / "diagnostics.json"
    path.write_text(json.dumps(kb))
    return path


def observed(path, entry_id):
    return next(e for e in json.loads(path.read_text())["entries"] if e["id"] == entry_id)["observed"]


LOAD_MORE = {"op": "set_initial_volume", "labware": "wash_buffer_trough", "volume_ul": 7050}
LOWER = {"op": "replace_step", "step": 28, "new_steps": [
    {"action": "aspirate", "labware": "wash_buffer_trough", "volume_ul": 100, "channels": list(range(8))}]}


def test_a_healing_run_is_recorded(tmp_path, kb_copy):
    result = heal_demo(tmp_path, {"reasoning": "", "edits": [LOAD_MORE]})
    assert result.status == "HEALED"
    assert diagnostics.record_run(result.rounds, "demo.json", "qwen", kb_copy, datetime.date(2026, 10, 30)) \
        == ["insufficient_liquid.loaded_reagent"]
    obs = observed(kb_copy, "insufficient_liquid.loaded_reagent")
    assert (obs["seen"], obs["repair_attempts"], obs["resolved"]) == (1, 1, 1)
    assert obs["resolved_by"] == {"set_initial_volume": 1}
    assert obs["examples"][0]["outcome"] == "resolved by set_initial_volume"
    assert obs["examples"][0]["step"] == 28 and "TooLittleLiquidError" in obs["examples"][0]["raw_error"]
    # The curated part is untouched and the file still loads.
    diagnostics.knowledge_base.cache_clear()
    assert diagnostics.knowledge_base(kb_copy)[1]["fixes"] == diagnostics.knowledge_base()[1]["fixes"]


def test_rejections_accumulate_across_runs(tmp_path, kb_copy):
    for _ in range(2):
        result = heal_demo(tmp_path, {"reasoning": "", "edits": [LOWER]}, max_rounds=1)
        assert result.status == "GAVE_UP"
        diagnostics.record_run(result.rounds, "demo.json", "qwen", kb_copy)
    obs = observed(kb_copy, "insufficient_liquid.loaded_reagent")
    # Each run: round 0 fails, its edit is rejected; round 1 fails again with no rounds left.
    assert (obs["seen"], obs["repair_attempts"], obs["resolved"]) == (4, 0, 0)
    assert obs["rejected"] == {"intent guard: moves a different volume": 2}
    assert [e["outcome"] for e in obs["examples"]] == ["all edits rejected", "no repair attempted (out of rounds)"] * 2
    assert obs["protocols"] == ["demo.json"]


def test_examples_are_capped(tmp_path, kb_copy):
    result = heal_demo(tmp_path, max_rounds=0)
    for _ in range(diagnostics.MAX_EXAMPLES + 3):
        diagnostics.record_run(result.rounds, "demo.json", "qwen", kb_copy)
    obs = observed(kb_copy, "insufficient_liquid.loaded_reagent")
    assert obs["seen"] == diagnostics.MAX_EXAMPLES + 3
    assert len(obs["examples"]) == diagnostics.MAX_EXAMPLES
