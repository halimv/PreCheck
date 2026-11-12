#!/usr/bin/env python3
"""
LLNL Capstone Protocol Pipeline CLI.

  Stage 0: Drafter    (protocol PDF/text -> protocol IR with labware needs, by the Claude CLI)
  Stage 0b: Deck      (needs -> real labware from VENUS's library and the deck on the STARlet; what nothing
                       fits goes back to Claude, then the deck config and mapping are written to decks/)
  Stage 2: Compiler   (IR -> PyLabRobot module, deterministic)
  Stage 3: Simulator  (module -> ChatterBox dry run + lab-concept diagnostic)
  Stage 4: Visualizer (replay in PyLabRobot's browser visualizer, --visualize)
  Stage 5: Executor   (the STARlet; set up and run from the demo's Execute page)

Given a protocol file or text, the whole pipeline runs: Claude drafts the IR from the protocol text (saved in
drafts/), its deck is built (decks/), the self-healing loop repairs it with a local Ollama model until
the compiler and simulator pass (the stage 1 verifier is out of the loop for now), and
the passing IR and its PLR script are written to healed/.

With --revise, a healed IR is changed as the scientist asks: Claude revises it, the revision goes
through the same loop, and it is written to healed/ as the next version (<name>_r2, _r3, ...); the
earlier version is kept.

With --heal on an existing IR (--protocol), a failing protocol goes through the same loop.

Usage:
  python pipeline.py protocol.pdf
  python pipeline.py "Serially dilute the culture 1:10 in 0.9% saline ..."
  python pipeline.py --revise healed/serial_dilution.json "use 3 replicate rows instead of 8"
  python pipeline.py --protocol protocols/serial_dilution_v1.json --heal
  python pipeline.py --protocol protocols/serial_dilution_v1.json --heal --visualize
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

import yaml

from pipeline import diagnostics, proposals
from pipeline.deck import DEFAULT_DECK, INSTRUMENT_DECK, deck_config_for, load_deck_config
from pipeline.self_heal import OllamaBackend, SelfHealer, ir_diff
from pipeline.stage0_drafter import DraftError, draft, read_source, revise, revision_stem
from pipeline.stage2_compiler import compile_standalone
from pipeline.stage4_visualizer import visualize_protocol

ROOT = Path(__file__).parent
CONFIG_DIR = ROOT / "config"
HEALED = ROOT / "healed"
BOLD, RESET = "\033[1m", "\033[0m"


def banner(text):
    print(f"\n{BOLD}== {text} =={RESET}", flush=True)


async def show_in_visualizer(protocol, deck_config, name):
    session = await visualize_protocol(protocol, deck_config, name=name)
    print(f"Replay finished. Visualizer still open at {session.url}; press Ctrl+C to close it.")
    try:
        while True:
            await asyncio.sleep(1)
    finally:
        await session.stop()


def print_deck(d):
    """The deck stage 0 built: where each IR name's labware is, and what the operator has to add."""
    mapping = json.loads(d.mapping_path.read_text())
    rounds = f" after {d.deck_rounds} round(s) of changing needs nothing in the library fit" if d.deck_rounds else ""
    print(f"\n[deck] {d.deck_path.relative_to(ROOT)}{rounds}; mapping: {d.mapping_path.relative_to(ROOT)}")
    for name, m in mapping["labware"].items():
        carrier = m.get("carrier") or {}
        where = (f"{carrier['venus_type']} rail {carrier['rails']}, position {m['position']['hamilton']}"
                 if carrier else "the deck's tip waste")
        barcode = f", barcode {m['barcode']}" if m.get("barcode") else ""
        print(f"  {name:18s} {m.get('venus_type') or 'waste':22s} {where}{barcode} [{m['action'].replace('_', ' ')}]")
    for change in mapping["operator_changes"]:
        print(f"  operator: {change}")


def write_healed(protocol, deck_config, stem, rounds):
    """The passing IR, its standalone PLR script and the heal log, in healed/."""
    HEALED.mkdir(exist_ok=True)
    ir_path = HEALED / f"{stem}.json"
    ir_path.write_text(json.dumps(protocol, indent=2))
    plr_path = HEALED / f"{stem}_plr.py"
    deck_file = protocol.get("deck_config", DEFAULT_DECK)
    plr_path.write_text(compile_standalone(protocol, deck_config, deck_file, f"healed/{plr_path.name}"))
    (HEALED / f"{stem}_heal_log.json").write_text(json.dumps(rounds, indent=2))
    return ir_path, plr_path


def main():
    parser = argparse.ArgumentParser(description="LLNL Capstone Protocol Pipeline")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("input", nargs="?", help="Protocol PDF, text file, or the protocol text itself: drafts the IR "
                                                 "with Claude, then self-heals it (implies --heal)")
    source.add_argument("--protocol", help="Existing protocol IR file (JSON or YAML)")
    source.add_argument("--revise", nargs=2, metavar=("HEALED_IR", "CHANGE"),
                        help="Have Claude change a healed IR as described (text, or a text file), then self-heal "
                             "the revision and save it to healed/ as the next version")
    parser.add_argument("--deck", default=INSTRUMENT_DECK,
                        help=f"Deck for drafting: a VENUS .lay or a deck config (default {INSTRUMENT_DECK}, the deck on the STARlet)")
    parser.add_argument("--claude-model", default=None, help="Model for the Claude CLI draft (default: the CLI's)")
    parser.add_argument("--draft-only", action="store_true", help="Stop after writing the draft IR to drafts/")
    parser.add_argument("--output", default="build", help="Directory for per-round work files (default: build/)")
    parser.add_argument("--heal", action="store_true", help="Repair a failing protocol with a local model")
    parser.add_argument("--model", default="qwen2.5-coder:7b", help="Ollama model for the self-healing loop")
    parser.add_argument("--max-rounds", type=int, default=8, help="Maximum repair rounds (default 8)")
    parser.add_argument(
        "--feedback", choices=["translated", "raw"], default="translated",
        help="What the model sees on a simulation failure: lab-concept diagnostic or raw exception",
    )
    parser.add_argument(
        "--escalate-after", type=int, default=1, metavar="N",
        help="When the same simulator failure comes back N times in a row, ask the model to reason past the "
             "knowledge base and propose an addition to it (default 1; 0 turns this off)",
    )
    parser.add_argument("--no-record", action="store_true",
                        help="Do not record this run in the knowledge base (rehearsals and tests)")
    parser.add_argument(
        "--visualize", action="store_true",
        help="After a clean pass, replay the passing protocol in PyLabRobot's browser visualizer (stage 4)",
    )
    args = parser.parse_args()

    previous = None  # the healed IR a --revise starts from
    if args.input or args.revise:
        try:
            base_deck = load_deck_config(str(ROOT / args.deck))  # the deck on the STARlet: needs resolve against it
            if args.revise:
                previous_file = Path(args.revise[0])
                previous = json.loads(previous_file.read_text())
                note = read_source(args.revise[1])["text"]
                banner(f"Stage 0: revising {previous_file.name} with the Claude CLI")
                print(f"Change requested: {note}\n")
                stem = revision_stem(previous_file.stem)
                while (HEALED / f"{stem}.json").exists():  # never overwrite an earlier version
                    stem = revision_stem(stem)
                d = revise(previous, note, base_deck, current_name=previous_file.name, deck_file=args.deck,
                           model=args.claude_model, stem=stem)
            else:
                banner("Stage 0: drafting the IR with the Claude CLI, then building its deck from the labware library")
                d = draft(args.input, base_deck, deck_file=args.deck, model=args.claude_model)
        except (DraftError, OSError, json.JSONDecodeError) as e:
            sys.exit(f"\n[stage 0] {e}")
        protocol, protocol_file = d.protocol, d.path
        deck_config = deck_config_for(protocol, ROOT)  # the deck built for this protocol
        cost = f", ${d.cost_usd:.3f}" if d.cost_usd else ""
        print(f"\n[stage 0] Draft written to {d.path.relative_to(ROOT)} "
              f"({len(protocol['steps'])} steps, {d.attempts} attempt(s){cost})")
        for a in protocol.get("assumptions", []):
            print(f"  assumption: {a}")
        print_deck(d)
        if args.draft_only:
            return
        args.heal = True
    else:
        protocol_file = Path(args.protocol)
        with open(protocol_file) as f:
            protocol = yaml.safe_load(f)
        deck_config = deck_config_for(protocol, ROOT)
    stem = protocol_file.stem
    out_dir = Path(args.output) / stem

    healer = SelfHealer(
        deck_config=deck_config,
        backend=OllamaBackend(model=args.model),
        work_dir=str(out_dir),
        feedback_mode=args.feedback,
    )

    print(f"\nProtocol: {protocol_file} ({len(protocol['steps'])} steps)")
    passing = protocol  # the protocol that passed compile and simulate; replaced by the repaired IR after --heal
    if not args.heal:
        gate = healer.evaluate(protocol, 0)
        print(f"[{gate.stage}] {'PASSED' if gate.passed else 'FAILED'}: {gate.summary}")
        if not gate.passed:
            if gate.feedback != gate.summary:
                print(gate.feedback)
            print("\nRe-run with --heal to repair it with a local model.")
            sys.exit(1)
    else:
        banner(f"Compile + simulate + self-healing with {args.model}")
        print(f"(feedback: {args.feedback}, max {args.max_rounds} rounds)")
        result = healer.heal(protocol, max_rounds=args.max_rounds, escalate_after=args.escalate_after or None)
        (out_dir / "heal_log.json").write_text(json.dumps(result.rounds, indent=2))
        learned = [] if args.no_record else diagnostics.record_run(result.rounds, protocol_file.name, args.model)
        if learned:
            print(f"Recorded in {diagnostics.KNOWLEDGE_BASE.name}: {', '.join(sorted(set(learned)))}")
        for p in [] if args.no_record else proposals.submit(result.proposals, protocol_file.name, args.model):
            print(f"\nKnowledge-base proposal waiting for review:\n{proposals.describe(p)}\n"
                  f"  approve: python -m pipeline.proposals approve {p['id']}   (or on the demo's Library page)")
        for c in result.proposals:
            if c["problems"]:
                print(f"\nProposal from round {c['evidence']['round']} not kept: {'; '.join(c['problems'])}")
        print(f"\nResult: {result.status} after {len(result.rounds) - 1} repair round(s). Log: {out_dir / 'heal_log.json'}")
        if result.status == "GAVE_UP":
            sys.exit(1)
        ir_path, plr_path = write_healed(result.protocol, deck_config, stem, result.rounds)
        banner("Safety-checked output")
        print(f"Passing IR (scientist review before use): {ir_path.relative_to(ROOT)}")
        print(f"PLR Hamilton script:                      {plr_path.relative_to(ROOT)}")
        if result.status == "HEALED":
            print("\nRepairs made to the draft:")
            print(ir_diff(protocol, result.protocol))
        if previous is not None:
            print(f"\nChanges from {Path(args.revise[0]).name} (your request, plus any repairs):")
            print(ir_diff(previous, result.protocol) or "  (no step or volume changes)")
        print("\nNext: python demo/server.py, open http://127.0.0.1:8000/execute, pick this protocol and follow the "
              f"deck setup checklist.\n  Rehearse without the robot: python {plr_path.relative_to(ROOT)} --backend chatterbox")
        passing = result.protocol

    if args.visualize:
        print("\n[Stage 4] Opening PyLabRobot's visualizer and replaying the passing protocol...")
        try:
            asyncio.run(show_in_visualizer(passing, deck_config, name=f"{stem} ({len(passing['steps'])} steps)"))
        except KeyboardInterrupt:
            print("Visualizer closed.")


if __name__ == "__main__":
    main()
