import sys
import json
import os
import argparse
from precheck.verifier import Verifier
from precheck.simulator import HamiltonSimulator

def main():
    parser = argparse.ArgumentParser(description="Precheck gate: verify + simulate protocols")
    parser.add_argument("--simulate", action="store_true", help="Run protocol in Hamilton simulator after precheck")
    parser.add_argument("--verbose", action="store_true", help="Show execution log")
    args = parser.parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    precheck_dir = os.path.join(script_dir, "precheck")
    labware_config = os.path.join(precheck_dir, "labware_config.json")
    protocol_plan = os.path.join(precheck_dir, "protocol_plan.yaml")
    protocol_config = os.path.join(precheck_dir, "protocol_config.json")

    # Stage 1: Precheck verification
    print("=" * 60)
    print("STAGE 1: PRECHECK GATE (Deterministic Verification)")
    print("=" * 60)
    verifier = Verifier(labware_config, protocol_plan, protocol_config)
    result = verifier.run_verification()
    print(json.dumps(result, indent=2))

    if result["status"] == "FAILED":
        sys.exit(1)

    # Stage 2: Optional simulator execution
    if args.simulate:
        print("\n" + "=" * 60)
        print("STAGE 2: HAMILTON SIMULATOR (Runtime Validation)")
        print("=" * 60)
        sim = HamiltonSimulator(labware_config, protocol_plan)
        sim_result = sim.run_simulation()
        print(json.dumps(sim_result, indent=2))

        if sim_result["status"] == "FAILED":
            sys.exit(1)

    print("\n✓ Protocol passed all safety checks")

if __name__ == "__main__":
    main()