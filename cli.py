#!/usr/bin/env python3
"""
LLNL Capstone Protocol Pipeline CLI.

Orchestrates the 4-stage pipeline:
  Stage 1: Verifier (declarative JSON → safety gate)
  Stage 2: Compiler (JSON → PyLabRobot code)
  Stage 3: Simulator (PLR code → ChatterBox dry run)
  Stage 4: Executor (hardware execution)

Usage:
  python cli.py --protocol protocols/serial_dilution_v1.json [--execute]
"""

import argparse
import os
import sys
from pathlib import Path

from pipeline.stage1_verifier import Verifier
from pipeline.stage2_compiler import ProtocolCompiler
from pipeline.stage3_simulator import PLRSimulator
from pipeline.stage4_executor import HardwareExecutor


def resolve_config_path(config_name: str) -> str:
    """Resolve config file path relative to config/ directory."""
    config_dir = Path(__file__).parent / "config"
    return str(config_dir / config_name)


def main():
    parser = argparse.ArgumentParser(
        description="LLNL Capstone Protocol Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cli.py --protocol protocols/serial_dilution_v1.json
  python cli.py --protocol protocols/serial_dilution_v1.json --execute --output /tmp/result.log
        """
    )
    parser.add_argument(
        "--protocol",
        required=True,
        help="Path to protocol JSON or YAML file (e.g., protocols/serial_dilution_v1.json)"
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Path to save compiled PLR code and logs (default: /tmp/protocol_output/)"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute on physical hardware (requires stage 1-3 to pass)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Run simulation only (default: True)"
    )

    args = parser.parse_args()

    # Setup output directory
    output_dir = Path(args.output) if args.output else Path("/tmp/protocol_output")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Resolve config paths
    labware_config = resolve_config_path("labware.json")
    hardware_config = resolve_config_path("hardware.json")
    protocol_defaults = resolve_config_path("protocol_defaults.json")

    print(f"\n{'='*70}")
    print(f"LLNL Capstone Protocol Pipeline")
    print(f"{'='*70}\n")

    # --- STAGE 1: VERIFIER ---
    print("[Stage 1] Verifying declarative protocol...")
    try:
        verifier = Verifier(labware_config, args.protocol, protocol_defaults)
        result = verifier.run_verification()

        if result["status"] == "PASSED":
            print(f"✓ PASSED: {result['message']}")
        else:
            print(f"✗ FAILED: {result['message']}")
            print(f"  Error Code: {result.get('error_code', 'UNKNOWN')}")
            sys.exit(1)
    except Exception as e:
        print(f"✗ ERROR: {e}")
        sys.exit(1)

    # --- STAGE 2: COMPILER ---
    print("\n[Stage 2] Compiling to PyLabRobot code...")
    try:
        compiler = ProtocolCompiler(labware_config, args.protocol)
        compiled_code = compiler.compile()

        compiled_path = output_dir / "compiled_protocol.py"
        with open(compiled_path, "w") as f:
            f.write(compiled_code)
        print(f"✓ Compiled: {compiled_path}")
    except Exception as e:
        print(f"✗ ERROR: {e}")
        sys.exit(1)

    # --- STAGE 3: SIMULATOR ---
    print("\n[Stage 3] Simulating with ChatterBox...")
    try:
        simulator = PLRSimulator(hardware_config, str(compiled_path))
        sim_result = simulator.run(compiled_code)

        if sim_result["status"] == "PASSED":
            print(f"✓ SIMULATION PASSED")
            sim_log = output_dir / "simulation.log"
            simulator.save_log(str(sim_log))
            print(f"  Log saved: {sim_log}")
        else:
            print(f"⚠ SIMULATION: {sim_result['message']}")
            if sim_result.get("errors"):
                print("  Errors:")
                for err in sim_result["errors"]:
                    print(f"    - {err}")
    except Exception as e:
        print(f"✗ ERROR: {e}")
        sys.exit(1)

    # --- STAGE 4: EXECUTOR (conditional) ---
    if args.execute:
        print("\n[Stage 4] Executing on hardware...")
        try:
            executor = HardwareExecutor(hardware_config)
            exec_result = executor.execute(compiled_code)

            if exec_result["status"] == "PASSED":
                print(f"✓ EXECUTION PASSED")
            else:
                print(f"⚠ EXECUTION: {exec_result['message']}")

            exec_log = output_dir / "execution.log"
            executor.save_log(str(exec_log))
            print(f"  Log saved: {exec_log}")
        except Exception as e:
            print(f"✗ ERROR: {e}")
            sys.exit(1)
    else:
        print("\n[Stage 4] SKIPPED (use --execute to run hardware)")

    print(f"\n{'='*70}")
    print(f"Pipeline complete. Output: {output_dir}")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
