"""Checks for the text -> IR -> healed -> execution path: the drafter's parsing of Claude's reply,
the deck setup checklist, and the stage-5 executor on ChatterBox (healed v1 run as the protocol)."""

import io
import sys
import json
from pathlib import Path

from pipeline.deck import INSTRUMENT_DECK, load_deck_config
from pipeline.setup_guide import setup_checklist
from pipeline.stage0_drafter import _ReplyPrinter, extract_plan, read_source, structural_errors
from pipeline.stage5_executor import HardwareExecutor, tip_check_steps

ROOT = Path(__file__).resolve().parent.parent
HEALED_V1 = ROOT / "docs" / "runs" / "2026-10-21_v1_qwen2.5-coder-7b" / "serial_dilution_v1_healed.json"


def deck():
    return load_deck_config(str(ROOT / "config" / "reference" / "plr_deck.json"))


def instrument_deck():
    return load_deck_config(str(ROOT / INSTRUMENT_DECK))


# The v1 protocol's labware, written as the needs a draft names (its IDs as IR names).
V1_NEEDS = {
    "hamilton_tiprack_96": {"kind": "tip_rack", "tip_volume_ul": 300, "filter": True},
    "hamilton_tiprack_96_b": {"kind": "tip_rack", "tip_volume_ul": 300, "filter": True},
    "corning_3595": {"kind": "plate", "wells": 96, "min_capacity_ul": 200},
    "reservoir_50ml": {"kind": "reservoir", "min_capacity_ul": 5000},
    "tube_15ml": {"kind": "tube", "min_capacity_ul": 900},
    "waste": {"kind": "waste"},
}


def healed():
    return json.loads(HEALED_V1.read_text())


def test_read_source_treats_a_long_paragraph_as_text():
    text = "Serially dilute the culture 1:10 in 0.9% saline. " * 40
    assert read_source(text) == {"text": text.strip(), "name": "pasted_text", "pdf": None}


def test_extract_plan_takes_the_last_json_block():
    reply = 'First try:\n```json\n{"steps": []}\n```\nFixed:\n```json\n{"steps": [{"action": "tips_off"}]}\n```'
    assert extract_plan(reply) == {"steps": [{"action": "tips_off"}]}


def test_structural_errors_name_undeclared_labware_and_unknown_actions():
    plan = {"labware": {"plate": {"kind": "plate", "wells": 96}, "waste": {"kind": "waste"}},
            "steps": [{"action": "aspirate", "labware": "beaker", "volume_ul": 10, "channels": [0]},
                      {"action": "pour", "labware": "plate"}],
            "initial_volumes_ul": {"plate": 100}}
    errors = " ".join(structural_errors(plan))
    assert "'beaker', which is not in 'labware'" in errors
    assert "unknown action 'pour'" in errors
    assert "not a reservoir or tube" in errors


def test_structural_errors_need_a_labware_section_with_kinds():
    steps = [{"action": "tips_off", "labware": "waste", "volume_ul": 0, "channels": [0]}]
    assert "'labware' must be an object" in structural_errors({"steps": steps})[0]
    assert "needs a kind" in structural_errors({"steps": steps, "labware": {"waste": {"kind": "bin"}}})[0]


def test_reply_printer_hides_the_json_plan():
    out = io.StringIO()
    printer = _ReplyPrinter(out)
    for chunk in ["Reasoning here.\n``", '`json\n{"steps": [{"action": "a"}, ', '{"action": "b"}]}\n```\nDone.']:
        printer.feed(chunk)
    printer.close()
    shown = out.getvalue()
    assert "Reasoning here." in shown and "Done." in shown
    assert '"action"' not in shown and "2 steps" in shown


def test_checklist_covers_every_used_labware_and_reagent_volume():
    setup = setup_checklist(healed(), deck())
    ids = {i["id"] for i in setup["items"]}
    for lid in ("hamilton_tiprack_96", "hamilton_tiprack_96_b", "corning_3595", "reservoir_50ml", "tube_15ml"):
        assert f"labware:{lid}" in ids
    volumes = {i["labware"]: i.get("volume_ul") for i in setup["items"] if i.get("labware")}
    assert volumes["reservoir_50ml"] == healed()["initial_volumes_ul"]["reservoir_50ml"]
    tips = next(i for i in setup["items"] if i["id"] == "labware:hamilton_tiprack_96")
    assert "300 uL" in tips["detail"] and "PLR site 0, the front-most" in tips["detail"]


def test_executor_runs_the_healed_protocol_on_chatterbox():
    events = []
    result = HardwareExecutor(deck(), "chatterbox", on_event=lambda k, d: events.append(k)).run(healed())
    assert result == {"status": "DONE", "steps_done": len(healed()["steps"])}
    assert events.count("step_done") == len(healed()["steps"])


def test_tip_check_picks_up_and_returns_one_column_per_rack():
    steps = tip_check_steps(healed(), deck())
    assert [s["action"] for s in steps] == ["tips_on", "return_tips", "tips_on", "return_tips"]
    result = HardwareExecutor(deck(), "chatterbox", on_event=lambda k, d: None).run(healed(), mode="tip_check")
    assert result["status"] == "DONE"


def test_revision_stems_count_up():
    from pipeline.stage0_drafter import revision_stem
    assert revision_stem("serial_dilution") == "serial_dilution_r2"
    assert revision_stem("serial_dilution_r2") == "serial_dilution_r3"


def test_revise_sends_the_request_and_records_it(tmp_path, monkeypatch):
    """A stand-in CLI returns the current plan unchanged; the revision keeps the request and source, and the
    CLI runs without the CLAUDE* variables of a surrounding Claude session."""
    import pipeline.stage0_drafter as drafter

    fake = tmp_path / "claude"
    fake.write_text(f"""#!{sys.executable}
import json, os, re, sys
prompt = sys.stdin.read()
open({str(tmp_path / 'seen.json')!r}, "w").write(json.dumps({{
    "prompt": prompt, "env": sorted(k for k in os.environ if k.startswith("CLAUDE"))}}))
plan = re.search(r"# Current plan.*?```json\\n(.*?)\\n```", prompt, re.S).group(1)
text = "Done.\\n```json\\n" + plan + "\\n```"
print(json.dumps({{"type": "result", "is_error": False, "result": text, "session_id": "s"}}))
""")
    fake.chmod(0o755)
    monkeypatch.setattr(drafter, "CLAUDE_BIN", str(fake))
    monkeypatch.setenv("CLAUDECODE", "1")

    current = {**healed(), "labware": V1_NEEDS, "source": {"name": "dilution", "text": "Serially dilute 1:10."}}
    d = drafter.revise(current, "mix 5 times", instrument_deck(), "dilution.json", out=io.StringIO(),
                       drafts_dir=tmp_path / "drafts", decks_dir=tmp_path / "decks", stem="dilution_r2")
    seen = json.loads((tmp_path / "seen.json").read_text())
    assert "mix 5 times" in seen["prompt"] and "Serially dilute 1:10." in seen["prompt"]
    assert seen["env"] == []
    assert d.path == tmp_path / "drafts" / "dilution_r2.json"
    assert d.protocol["revisions"] == [{"note": "mix 5 times", "from": "dilution.json"}]
    assert d.protocol["source"]["text"] == "Serially dilute 1:10."
    assert len(d.protocol["steps"]) == len(healed()["steps"])
    assert d.deck_path == tmp_path / "decks" / "dilution_r2.json" and d.mapping_path.is_file()
