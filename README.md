# LLNL Capstone: Hamilton STARlet Automated Protocol Control Plane

A self-healing, safety-gated control plane for automating serial dilution protocols on a Hamilton STARlet liquid handler via PyLabRobot.

**4-Stage Pipeline:** Declarative JSON IR → Safety Verification → Code Compilation → Simulation → Hardware Execution

This engine sits between an LLM Reasoning Agent (Step 1→2) and PyLabRobot (Step 2→4). It validates non-deterministic LLM protocol parameters against physical hardware invariants, compiles to executable code, dry-runs in ChatterBox, and self-heals on simulation errors before any motor moves.

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

**Phase 1 MVP (Current Implementation):**

1. **Dead Volume Enforcement (30-330µL):** 
   - Enforces 30µL minimum (dead volume, inaccessible residual)
   - Enforces 330µL maximum (360µL capacity - 30µL dead volume)
   - Prevents aspirate that would leave <30µL or dispense exceeding 330µL

2. **Tip Management & Cross-Contamination Prevention:**
   - Smart contamination tracking: tips can be reused for same source well (serial dilution pattern)
   - Blocks aspirates from different source wells without `tips_off` (prevents cross-talk)
   - 96-tip rack position-based inventory (tracks which positions depleted)
   - 8-channel head per-channel contamination state (independent tracking per channel)

3. **Pipetting Range:** Enforces single-step volume transfers within $1.0\,\mu\text{L} - 200.0\,\mu\text{L}$ (Hamilton $200\,\mu\text{L}$ filtered tip specs).

---

## 4-Stage Pipeline Architecture

```
[ User Intent / Natural Language ]
         ↓
[Stage 1: Verifier]
  - Input: Declarative JSON/YAML protocol
  - Validates: Volume limits, tip management, contamination prevention
  - Output: PASS/FAIL with structured error codes
         ↓ (if PASS)
[Stage 2: Compiler]
  - Input: Verified JSON protocol
  - Maps: Declarative steps to PyLabRobot API calls
  - Output: Executable Python code (PLR script)
         ↓
[Stage 3: Simulator]
  - Input: Compiled PLR code
  - Executes: In ChatterBox backend (mock hardware)
  - Captures: State transitions, errors, warnings
  - Output: Dry-run diagnostics
         ↓ (if PASS)
[Stage 4: Executor]
  - Input: Verified & simulated PLR code
  - Executes: On physical Hamilton STARlet
  - Monitors: Hardware state, safety interlocks
  - Output: Execution logs, final state

[ SELF-HEALING LOOP (Future) ]
  If Simulator detects error:
    → Translate error to lab-concept diagnostics
    → Send to LLM for auto-refactor
    → Re-enter Stage 2 with corrected protocol
```

**Key Design Principle:** No script touches hardware until it has:
1. Passed declarative safety verification (Stage 1)
2. Been compiled to executable code (Stage 2)
3. Successfully run through simulation (Stage 3)

---

## Repository Structure (Reorganized)

```text
.
├── cli.py                             # Entry point: orchestrates 4-stage pipeline
├── README.md                          # This file
│
├── config/                            # Hardware specifications
│   ├── labware.json                   # Plate, tip, container specs
│   ├── hardware.json                  # Deck layout, connection parameters
│   └── protocol_defaults.json         # Initial state and experiment parameters
│
├── pipeline/                          # The 4-stage execution pipeline
│   ├── stage1_verifier.py             # Declarative JSON → Safety gate
│   ├── stage2_compiler.py             # JSON → PLR Python code (stub)
│   ├── stage3_simulator.py            # PLR code → ChatterBox dry run (stub)
│   └── stage4_executor.py             # Hardware execution (stub)
│
├── protocols/                         # Protocol specifications (human-readable JSON/YAML)
│   ├── serial_dilution_v1.json        # Full 68-step, 12-column protocol (CURRENT)
│   ├── serial_dilution_v0.yaml        # Previous 12-step version
│   └── serial_dilution_simple.yaml    # Demo/test version (4 steps)
│
├── precheck/                          # Legacy verifier & test suite
│   ├── test_verifier.py               # Comprehensive tests (11 tests, all passing)
│   └── *.json, *.yaml                 # Config files (duplicates in config/)
│
├── tests/                             # Test suite (mirrors precheck/)
│   └── fixtures/                      # Test data
│
└── archive/                           # Legacy & reference code (NOT in active pipeline)
    ├── files/                         # Old reference implementations
    ├── viz_backend/                   # Visualization server (separate)
    ├── simulator_old.py               # Broken PLR simulator (ChatterBox state bug)
    ├── json_parser_old.py             # Legacy JSON parser
    ├── main.py                        # Old CLI
    └── start_visualizer.py            # Old visualization launcher

---

## Error Codes

| Error Code | Cause | Solution |
|-----------|-------|----------|
| `DRY_ASPIRATE` | Aspirate would leave <30µL dead volume (inaccessible residual) | Reduce aspirate volume or use well with more initial liquid |
| `VOLUMETRIC_OVERFLOW` | Dispense would exceed 330µL maximum (usable capacity) | Reduce dispense volume or use new well |
| `CONTAMINATED_TIP` | Attempted aspirate from different source well without `tips_off` | Either reuse tips on same source well (serial dilution), or execute `tips_off` + `tips_on` to switch sources |
| `TIP_DEPLETED` | Requested tip position in 96-tip rack already used (no tip available) | Use different column in tip rack |
| `MISSING_TIP` | Channel attempted aspirate/dispense without mounted tip | Execute `tips_on` before aspirate/dispense operations |

---

## Quick Start

### Run the Full Pipeline

```bash
# Verify + compile + simulate
python cli.py --protocol protocols/serial_dilution_v1.json --output /tmp/protocol_run
```

Expected output:
- ✓ Stage 1: Protocol passes safety gate
- ✓ Stage 2: Python code compiled to `/tmp/protocol_run/compiled_protocol.py`
- ⚠ Stage 3: Simulator (ChatterBox integration pending)
- ⊘ Stage 4: Hardware execution skipped (use `--execute` to run)

### Run Tests

```bash
# All verifier tests (11 tests, all passing)
pytest precheck/test_verifier.py -v

# Quick test
pytest precheck/test_verifier.py -q
```

All 11 tests cover:
- Volume boundary conditions (dead volume min/max)
- Smart contamination prevention (same-source reuse allowed, different-source blocked)
- Tip tracking and depletion per rack (supports multiple racks)
- Reference serial dilution protocol validation

---

## Future Work (Phase 2)

- **Concentration Linearity Validation** — verify dilution factor math across transfers
- **Tip Property Tracking** — distinguish filter vs. standard vs. LPB (low protein binding) tips
- **Multi-Channel Alignment** — ensure all channels pick from same row
- **Mixing Validation** — check mix volume feasibility
- **Reservoir Capacity** — track diluent source depletion
- **Error Recovery** — state rollback and idempotency