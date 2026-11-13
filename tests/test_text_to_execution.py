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

ROOT = Path(__file__).resolve().parent.parent / "plugin"  # the plugin: code and ground truth
TESTS = Path(__file__).resolve().parent


# The v1 protocol's labware, written as the needs a draft names (its IDs as IR names).


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


def test_revision_stems_count_up():
    from pipeline.stage0_drafter import revision_stem
    assert revision_stem("serial_dilution") == "serial_dilution_r2"
    assert revision_stem("serial_dilution_r2") == "serial_dilution_r3"


