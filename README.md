# Hamilton STARlet Pre-Execution Safety Gate

A deterministic pre-flight safety verifier and volumetric simulator for PyLabRobot (PLR) automated serial dilution protocols.

Designed for a Hamilton STARlet liquid handler controlled via a Windows host (VENUS runtime environment), this engine sits between an LLM Reasoning Agent and PyLabRobot. It evaluates non-deterministic LLM protocol parameters against physical hardware invariants before any channel moves or valves actuate.

---

## Target Hardware & Labware Config

* **Liquid Handler:** Hamilton STARlet
* **Software Framework:** PyLabRobot (`pylabrobot.liquid_handling.LiquidHandler` with `STAR` backend)
* **Plates:** Corning 96-Well Clear Flat Bottom Microplates
  * *Max Well Volume:* $360\,\mu\text{L}$
  * *Dead Volume:* $30\,\mu\text{L}$
* **Tips:** Hamilton Filtered Tips ($200\,\mu\text{L}$)

---

## Core Safety Invariants

1. **Volumetric Bounds:** Verifies total well volumes during dilution series never exceed $360\,\mu\text{L}$ or drop below $30\,\mu\text{L}$ dead volume limit.
2. **Pipetting Range:** Enforces single-step volume transfers within $1.0\,\mu\text{L} - 200.0\,\mu\text{L}$ (Hamilton $200\,\mu\text{L}$ filtered tip specs).
3. **Sequence Expansion & Tip State Tracking:** Translates high-level serial dilution parameters into explicit operational primitives (`pick_up_tip`, `aspirate`, `dispense`, `mix`, `drop_tip`) to audit tip presence, tip availability in racks, and cross-contamination rules.

---

## Repository Structure

```text
.
├── config/
│   └── deck_config.yaml         # Corning 96-well & Hamilton tip rack physical limits
├── schemas/
│   └── serial_dilution.json     # JSON Schema for LLM-generated protocol parameters
├── src/
│   ├── __init__.py
│   ├── verifier.py              # Main preflight verifier entrypoint
│   ├── volumetric.py            # Volumetric calculations for serial dilution steps
│   ├── sequence.py              # Parameter-to-sequence step translator
│   └── tips.py                  # Tip state and rack occupancy tracker
├── tests/
│   ├── test_volumetric.py       # Overfill/underfill test cases
│   └── test_tips.py             # Tip sequence validation tests
├── protocols/
│   ├── llm_input_valid.json     # Example valid LLM-generated parameter file
│   └── llm_input_invalid.json   # Example overfilling LLM parameter file
├── main.py                      # Preflight verification CLI
├── requirements.txt
└── README.md