#!/usr/bin/env python3
"""
LLNL Capstone Protocol Pipeline CLI.

  Stage 1: Verifier   (protocol IR -> safety gate)
  Stage 2: Compiler   (IR -> PyLabRobot module, deterministic)
  Stage 3: Simulator  (module -> ChatterBox dry run + lab-concept diagnostic)
  Stage 4: Executor   (hardware, stub)

With --heal, a failing protocol goes through the self-healing loop: a local Ollama model
edits the IR until stages 1-3 pass, and the repaired IR is written out for review.

Usage:
  python cli.py --protocol protocols/serial_dilution_v1.json
  python cli.py --protocol protocols/serial_dilution_v1.json --heal
"""

import argparse
import json
import sys
from pathlib import Path

import yaml

from pipeline.deck import load_deck_config
from pipeline.self_heal import OllamaBackend, SelfHealer, ir_diff
from pipeline.stage4_executor import HardwareExecutor

CONFIG_DIR = Path(__file__).parent / "config"


def main():
    parser = argparse.ArgumentParser(description="LLNL Capstone Protocol Pipeline")
    parser.add_argument("--protocol", required=True, help="Protocol IR file (JSON or YAML)")
    parser.add_argument("--output", default="build", help="Output directory (default: build/)")
    parser.add_argument("--heal", action="store_true", help="Repair a failing protocol with a local model")
    parser.add_argument("--model", default="qwen2.5-coder:7b", help="Ollama model for --heal")
    parser.add_argument("--max-rounds", type=int, default=5, help="Maximum repair rounds for --heal")
    parser.add_argument(
        "--feedback", choices=["translated", "raw"], default="translated",
        help="What the model sees on a simulation failure: lab-concept diagnostic or raw exception",
    )
    parser.add_argument("--execute", action="store_true", help="Run on hardware after a clean pass (stub)")
    args = parser.parse_args()

    with open(args.protocol) as f:
        protocol = yaml.safe_load(f)
    stem = Path(args.protocol).stem
    out_dir = Path(args.output) / stem
    deck_config = load_deck_config(str(CONFIG_DIR / "plr_deck.json"))

    healer = SelfHealer(
        deck_config=deck_config,
        labware_path=str(CONFIG_DIR / "labware.json"),
        protocol_defaults_path=str(CONFIG_DIR / "protocol_defaults.json"),
        backend=OllamaBackend(model=args.model),
        work_dir=str(out_dir),
        feedback_mode=args.feedback,
    )

    print(f"\nProtocol: {args.protocol} ({len(protocol['steps'])} steps)")
    if not args.heal:
        gate = healer.evaluate(protocol, 0)
        print(f"[{gate.stage}] {'PASSED' if gate.passed else 'FAILED'}: {gate.summary}")
        if not gate.passed:
            if gate.feedback != gate.summary:
                print(gate.feedback)
            print("\nRe-run with --heal to repair it with a local model.")
            sys.exit(1)
    else:
        print(f"Self-healing with {args.model} (feedback: {args.feedback}, max {args.max_rounds} rounds)")
        result = healer.heal(protocol, max_rounds=args.max_rounds)
        (out_dir / "heal_log.json").write_text(json.dumps(result.rounds, indent=2))
        print(f"\nResult: {result.status} after {len(result.rounds) - 1} repair round(s). Log: {out_dir / 'heal_log.json'}")
        if result.status == "HEALED":
            healed_path = out_dir / f"{stem}_healed.json"
            healed_path.write_text(json.dumps(result.protocol, indent=2))
            print(f"Healed IR (needs scientist review before use): {healed_path}\n")
            print(ir_diff(protocol, result.protocol))
        if result.status == "GAVE_UP":
            sys.exit(1)

    if args.execute:
        print("\n[Stage 4] " + HardwareExecutor(str(CONFIG_DIR / "hardware.json")).execute("")["message"])


if __name__ == "__main__":
    main()
