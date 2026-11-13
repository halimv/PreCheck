#!/usr/bin/env python3
"""
Precheck: from a protocol's text to a protocol checked against the real instrument.

  python pipeline.py protocol.pdf
  python pipeline.py "Serially dilute the culture 1:10 in 0.9% saline ..."

Inputs: the protocol (a PDF, a text file, or the text itself) and the lab's ground truth in config/: the
instrument file (firmware configuration, VENUS's deck template, the layout of the deck now) and VENUS's
labware library. Other ground truth: --instrument, --labware, --deck.

  1. Draft      Claude writes the protocol IR and names the labware it needs by role (drafts/).
  2. Deck       The needs become real labware from VENUS's library, placed on the deck that is on the
                instrument; what nothing fits goes back to Claude (decks/).
  3. Check      The IR is compiled to PyLabRobot and run on PyLabRobot's STAR model configured as this
                instrument, on that deck, with tip and volume tracking: nothing is sent, but what the real
                backend would refuse is refused here.
  4. Repair     On a failure the diagnostic goes to a model (Claude Haiku by default, --healer ollama for a
                local one), which edits the IR; at most 5 rounds (--max-rounds).
  5. Review     The design as numbers (labware chosen, reagent volumes, what every well ends up holding and
                at what dilution, dead-volume and fill limits) plus suggestions: improvements, not errors.
  6. Watch      The whole assay replayed in PyLabRobot's 3D viewer. Then: any improvements? A change in
                words, or a suggestion's number, goes back through 1-5 as the next version (_r2, _r3, ...).
  7. Hand-off   healed/<name>.json, its standalone PyLabRobot script, and the same deck as an AHC layout.
                Precheck alone can run it (demo/server.py -> Execute); AHC adds supervision on site: error
                recovery, and catching a deck or instrument that is not what the files say.

Other ways in:
  python pipeline.py --revise healed/serial_dilution.json "use 3 replicate rows instead of 8"
  python pipeline.py --protocol protocols/serial_dilution_v1.json --heal
  python pipeline.py protocol.pdf --yes        (no review prompt: scripts, the Claude skill)
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

import yaml

from pipeline import diagnostics, proposals
from pipeline.deck import DeckError, deck_config_for, load_deck_config
from pipeline.design_review import render
from pipeline import runs, summary
from pipeline.flow import NotPassing, finish, next_stem, result_summary
from pipeline.instrument import InstrumentError, load_instrument
from pipeline.instrument import use as use_ground_truth
from pipeline.self_heal import CLAUDE_LADDER, CLAUDE_MODEL, SelfHealer, heal_with_ladder, ir_diff
from pipeline.stage0_drafter import DraftError, draft, read_source, revise
from pipeline.stage4_visualizer import visualize_protocol

from pipeline import paths  # noqa: E402

ROOT = paths.PLUGIN  # the ground truth (config/) and the code
CONFIG_DIR = ROOT / "config"
WORK = paths.WORK  # where this run writes
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
    print(f"\n[deck] {paths.in_work(d.deck_path)}{rounds}; mapping: {paths.in_work(d.mapping_path)}")
    for name, m in mapping["labware"].items():
        carrier = m.get("carrier") or {}
        where = (f"{carrier['venus_type']} rail {carrier['rails']}, position {m['position']['hamilton']}"
                 if carrier else "the deck's tip waste")
        barcode = f", barcode {m['barcode']}" if m.get("barcode") else ""
        print(f"  {name:18s} {m.get('venus_type') or 'waste':22s} {where}{barcode} [{m['action'].replace('_', ' ')}]")
    for change in mapping["operator_changes"]:
        print(f"  operator: {change}")


def heal(protocol, protocol_file, deck_config, args):
    """Compile, simulate and repair `protocol` with a model ladder: Haiku first, then Sonnet and Opus, each given
    --max-rounds rounds from where the last one stopped (one model only, with --model or --healer ollama). Returns
    (result, tiers); the knowledge base hears about the run unless --no-record."""
    out_dir = Path(args.output) / protocol_file.stem
    models = [args.model] if args.model or args.healer != "claude" else list(CLAUDE_LADDER)
    on = ("PyLabRobot's STAR model, configured as this instrument" if deck_config.get("instrument")
          else "the generic ChatterBox (the deck names no instrument)")
    banner(f"Compile + simulate + self-healing with {' -> '.join(models)}")
    print(f"(simulating on {on}; feedback: {args.feedback}, up to {args.max_rounds} repair rounds per model)")

    def tier_done(tier):
        print(f"\n[{tier['model']}] {tier['status']} after {max(len(tier['rounds']) - 1, 0)} round(s)")

    result, tiers = heal_with_ladder(protocol, deck_config, str(out_dir), args.max_rounds, models=models,
                                     healer=args.healer, feedback_mode=args.feedback,
                                     escalate_after=args.escalate_after or None, on_tier=tier_done)
    rounds = [dict(r, model=tier["model"]) for tier in tiers for r in tier["rounds"]]
    (out_dir / "heal_log.json").write_text(json.dumps({"tiers": [{"model": x["model"], "status": x["status"]} for x in tiers],
                                                       "rounds": rounds}, indent=2))
    last = tiers[-1]["model"]
    learned = [] if args.no_record else diagnostics.record_run(rounds, protocol_file.name, last)
    if learned:
        print(f"Recorded in {diagnostics.KNOWLEDGE_BASE.name}: {', '.join(sorted(set(learned)))}")
    for p in [] if args.no_record else proposals.submit(result.proposals, protocol_file.name, last):
        print(f"\nKnowledge-base proposal waiting for review:\n{proposals.describe(p)}\n"
              f"  approve: python -m pipeline.proposals approve {p['id']}   (or on the demo's Library page)")
    for c in result.proposals:
        if c["problems"]:
            print(f"\nProposal from round {c['evidence']['round']} not kept: {'; '.join(c['problems'])}")
    return result, tiers


async def watch_and_ask(protocol, deck_config, name, hints, visualize):
    """Replay the passing protocol in the 3D viewer, then ask the scientist for improvements while it stays open.
    Returns the change they ask for in words, or "" to accept the protocol as it is."""
    session = None
    if visualize:
        print("\n[Stage 4] Opening PyLabRobot's 3D viewer and replaying the protocol: watch the whole assay.")
        try:
            session = await visualize_protocol(protocol, deck_config, name=name)
            print(f"Replay finished. The viewer stays open at {session.url}")
        except Exception as e:  # the viewer is for watching; the protocol already passed without it
            print(f"The viewer could not be shown ({type(e).__name__}: {e}). The protocol passed the simulator regardless.")
    try:
        prompt = ("\nAny improvements? Type a change in your own words"
                  + (f", or a suggestion's number (1-{len(hints)})" if hints else "")
                  + ", or press Enter to accept the protocol as it is.\n> ")
        answer = (await asyncio.to_thread(input, prompt)).strip()
    except (EOFError, KeyboardInterrupt):
        answer = ""
    finally:
        if session is not None:
            await session.stop()
    numbers = [int(n) for n in answer.replace(",", " ").split()] if answer.replace(",", " ").replace(" ", "").isdigit() else []
    if numbers and all(1 <= n <= len(hints) for n in numbers):
        return " ".join(hints[n - 1]["request"] for n in numbers)
    return answer


def hand_off(report):
    """What comes after Precheck: the standalone script, and the same deck as an AHC layout."""
    stem, ahc = report["name"], report["ahc"]
    banner("Ready to run")
    print(f"Standalone (Precheck only):  python healed/{stem}_plr.py --backend chatterbox   (rehearsal)\n"
          f"                             python demo/server.py -> http://127.0.0.1:8000/execute   (deck checklist, then the STARlet)")
    print(f"With AHC (optional: supervised run, error recovery, deck check on site): layout written to "
          f"{report['files']['ahc_layout']}")
    for p in ahc["not_on_layout"]:
        print(f"  not on the AHC layout: {p}")
    for w in ahc["differs_from_venus"]:
        print(f"  AHC's model differs from VENUS: {w}")
    if ahc["not_on_layout"]:
        print("  AHC would not know about the items above; it will ask on site, or the deck needs labware AHC accepts.")
    print(f"Report (review, suggestions, files): {WORK / report['files']['report']}")


def _source(args, protocol_file):
    """What the person gave: the protocol text or file, a revision request, or the protocol file itself."""
    if args.input:
        return args.input
    if args.revise:
        return args.revise[1]
    return str(protocol_file) if protocol_file.exists() else None


def main():
    if "--setup" in sys.argv[1:]:  # the plugin's requirements and this folder's working folders; no protocol needed
        from pipeline import workfolder
        argv = sys.argv[1:]
        if "--labware" in argv and argv.index("--labware") + 1 < len(argv):  # given in chat or a script: save it, no prompt
            print(workfolder.set_labware(argv[argv.index("--labware") + 1]))
            results = workfolder.setup()
        elif sys.stdin.isatty():  # in a terminal: ask for what is missing
            results = workfolder.interactive_setup()
        else:
            results = workfolder.setup()
        print(workfolder.report(results))
        return
    parser = argparse.ArgumentParser(description="Precheck: protocol text -> a protocol checked against the real instrument")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("input", nargs="?", help="Protocol PDF, text file, or the protocol text itself")
    source.add_argument("--protocol", help="Existing protocol IR file (JSON or YAML): check it, repair it with --heal")
    source.add_argument("--revise", nargs=2, metavar=("HEALED_IR", "CHANGE"),
                        help="Change a healed IR as described (text, or a text file), then check and repair the "
                             "revision and save it to healed/ as the next version")
    truth = parser.add_argument_group("ground truth (defaults: this lab's STARlet, in config/)")
    truth.add_argument("--instrument", default=None,
                       help="The instrument file: it names the firmware configuration, VENUS's deck template and the "
                            "layout of the deck now (default config/instrument/starlet_F553.json)")
    truth.add_argument("--labware", default=None, help="VENUS's Labware folder (default config/Labware)")
    truth.add_argument("--deck", default=None,
                       help="Deck to draft on: a VENUS .lay or a deck config (default: the instrument's layout)")
    parser.add_argument("--claude-model", default=None, help="Model for the Claude CLI draft and revisions (default: the CLI's)")
    parser.add_argument("--draft-only", action="store_true", help="Stop after writing the draft IR to drafts/")
    parser.add_argument("--output", default=str(paths.BUILD), help="Directory for per-round work files (default: build/ in the working folder)")
    parser.add_argument("--heal", action="store_true", help="With --protocol: repair it if it fails")
    parser.add_argument("--healer", choices=["claude", "ollama"], default="claude",
                        help="Who repairs a failing protocol: Claude through its CLI (default) or a local Ollama model")
    parser.add_argument("--model", default=None,
                              help=f"One repair model only (default: {CLAUDE_MODEL}, then Sonnet, then Opus when the rounds run out)")
    parser.add_argument("--max-rounds", type=int, default=5, help="Maximum repair rounds per pass (default 5)")
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
    parser.add_argument("--yes", action="store_true",
                        help="Accept the passing protocol without the review prompt (also when not at a terminal)")
    parser.add_argument("--no-visualize", action="store_true", help="Do not open the 3D viewer at the review")
    parser.add_argument("--visualize", action="store_true",
                        help="With --yes or --protocol: replay the passing protocol in the 3D viewer and keep it open")
    args = parser.parse_args()

    try:
        use_ground_truth(args.instrument, args.labware)
        from pipeline import instrument as instrument_module
        deck_file = args.deck or load_instrument(instrument_module.DEFAULT_INSTRUMENT, ROOT)["deck_layout"]["file"]
    except (InstrumentError, OSError, KeyError, json.JSONDecodeError) as e:
        sys.exit(f"[ground truth] {e}")
    interactive = sys.stdin.isatty() and not args.yes

    previous = None  # the healed IR a revision starts from
    previous_name = None
    try:
        if args.input or args.revise:
            base_deck = load_deck_config(str(ROOT / deck_file))  # the deck on the STARlet: needs resolve against it
            print(f"Ground truth: instrument {instrument_module.DEFAULT_INSTRUMENT}, deck {deck_file}, "
                  f"labware library {args.labware or 'config/Labware'}")
            if args.revise:
                previous_file = Path(args.revise[0])
                previous, previous_name = json.loads(previous_file.read_text()), previous_file.name
                d = revise_draft(previous, previous_file.stem, read_source(args.revise[1])["text"], base_deck, deck_file, args)
            else:
                banner("Stage 0: drafting the IR with the Claude CLI, then building its deck from the labware library")
                d = draft(args.input, base_deck, deck_file=deck_file, model=args.claude_model)
                report_draft(d)
            protocol, protocol_file = d.protocol, d.path
            if args.draft_only:
                return
            args.heal = True
        else:
            protocol_file = Path(args.protocol)
            with open(protocol_file) as f:
                protocol = yaml.safe_load(f)
            base_deck = None
    except (DraftError, DeckError, OSError, json.JSONDecodeError) as e:
        sys.exit(f"\n[stage 0] {e}")

    while True:
        deck_config = deck_config_for(protocol, ROOT)  # the deck built for this protocol
        stem = protocol_file.stem
        print(f"\nProtocol: {protocol_file} ({len(protocol['steps'])} steps)")
        if not args.heal:
            gate = SelfHealer(deck_config=deck_config, work_dir=str(Path(args.output) / stem)).evaluate(protocol, 0)
            print(f"[{gate.stage}] {'PASSED' if gate.passed else 'FAILED'}: {gate.summary}")
            if not gate.passed:
                if gate.feedback != gate.summary:
                    print(gate.feedback)
                print("\nRe-run with --heal to repair it.")
                sys.exit(1)
            passing, rounds = protocol, []
        else:
            try:
                result, tiers = heal(protocol, protocol_file, deck_config, args)
            except RuntimeError as e:
                sys.exit(f"\n[self-healing] {e}")
            print("\n" + result_summary(result.status, tiers, args.max_rounds,
                                        Path(args.output) / stem / "heal_log.json", protocol_file.name))
            if result.status == "GAVE_UP":
                failed = Path(args.output) / stem / "summary.md"
                failed.parent.mkdir(parents=True, exist_ok=True)
                failed_text = summary.failure_markdown(protocol, tiers, args.max_rounds,
                                                       Path(args.output) / stem / "heal_log.json")
                failed.write_text(failed_text)
                run_dir = runs.record(stem, _source(args, protocol_file), protocol,
                                      [dict(r, model=tier["model"]) for tier in tiers for r in tier["rounds"]],
                                      tiers, False, failed_text, None)
                print(f"Summary of the failed run (nothing written to healed/): {paths.in_work(failed)}")
                print(f"Run record: {paths.in_work(run_dir)}")
                sys.exit(1)
            passing = result.protocol
            rounds = [dict(r, model=tier["model"]) for tier in tiers for r in tier["rounds"]]
            if result.status == "HEALED":
                print("\nRepairs made to the draft:")
                print(ir_diff(protocol, passing))
        if previous is not None:
            print(f"\nChanges from {previous_name} (your request, plus any repairs):")
            print(ir_diff(previous, passing) or "  (no step or volume changes)")
        try:
            report = finish(passing, deck_config, stem, rounds, status=result.status if args.heal else "PASSED",
                            tiers=tiers if args.heal else [])
        except NotPassing as e:  # the gate says no: nothing is written
            sys.exit(f"\n{e}")
        run_dir = runs.record(
            stem, _source(args, protocol_file), passing,
            [dict(r, model=tier["model"]) for tier in tiers for r in tier["rounds"]] if args.heal else [],
            tiers if args.heal else [], True,
            (WORK / report["files"]["summary"]).read_text(),
            report,
            script=(WORK / report["files"]["script"]).read_text(),
            layout=WORK / report["files"]["ahc_layout"])
        print(f"Run record: {paths.in_work(run_dir)}")
        hints = report["suggestions"]

        banner("For your review")
        print(render(report["review"], hints))
        print(f"\nPassing IR:          {report['files']['ir']}\nPLR Hamilton script: {report['files']['script']}")

        if not interactive:
            break
        change = asyncio.run(watch_and_ask(passing, deck_config, f"{stem} ({len(passing['steps'])} steps)", hints,
                                           visualize=not args.no_visualize))
        if not change:
            break
        try:
            if base_deck is None:
                base_deck = load_deck_config(str(ROOT / deck_file))
            previous, previous_name = passing, f"{stem}.json"
            d = revise_draft(passing, stem, change, base_deck, deck_file, args)
        except (DraftError, DeckError, OSError) as e:
            print(f"\n[stage 0] The change could not be made: {e}\nThe protocol above still stands.")
            break
        protocol, protocol_file, args.heal = d.protocol, d.path, True

    hand_off(report)
    if args.visualize and not interactive:
        print("\n[Stage 4] Opening PyLabRobot's 3D viewer and replaying the passing protocol...")
        try:
            asyncio.run(show_in_visualizer(passing, deck_config, name=f"{stem} ({len(passing['steps'])} steps)"))
        except KeyboardInterrupt:
            print("Viewer closed.")


def revise_draft(current, current_stem, note, base_deck, deck_file, args):
    """Have Claude change `current` as `note` asks; the revision is the next version (<name>_r2, _r3, ...)."""
    banner(f"Stage 0: revising {current_stem} with the Claude CLI")
    print(f"Change requested: {note}\n")
    stem = next_stem(current_stem)  # never overwrites an earlier version
    d = revise(current, note, base_deck, current_name=f"{current_stem}.json", deck_file=deck_file,
               model=args.claude_model, stem=stem)
    report_draft(d)
    return d


def report_draft(d):
    cost = f", ${d.cost_usd:.3f}" if d.cost_usd else ""
    print(f"\n[stage 0] Draft written to {paths.in_work(d.path)} "
          f"({len(d.protocol['steps'])} steps, {d.attempts} attempt(s){cost})")
    print_deck(d)


if __name__ == "__main__":
    main()
