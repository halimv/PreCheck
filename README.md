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

## Repository Structure

```text
.
├── fsm/
│   ├── verifier.py              # Core precheck safety gate engine
│   ├── test_verifier.py         # Comprehensive test suite (11 test cases)
│   ├── labware_config.json      # Hardware specs (plates, tips, containers)
│   ├── protocol_config.json     # Serial dilution parameters & starting concentrations
│   └── protocol_plan.yaml       # Example reference protocol (YAML format)
├── files/
│   └── serial_dilution_pylabrobot_v2.py  # PyLabRobot reference implementation
├── main.py                      # CLI entry point for verification
└── README.md

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

## Testing

Run the comprehensive test suite:
```bash
pytest fsm/test_verifier.py -v
```

All 11 tests cover:
- Volume boundary conditions (dead volume min/max)
- Smart contamination prevention (same-source reuse allowed, different-source blocked)
- Tip tracking and depletion
- Reference serial dilution protocol validation

---

## Future Work (Phase 2)

- **Concentration Linearity Validation** — verify dilution factor math across transfers
- **Tip Property Tracking** — distinguish filter vs. standard vs. LPB (low protein binding) tips
- **Multi-Channel Alignment** — ensure all channels pick from same row
- **Mixing Validation** — check mix volume feasibility
- **Reservoir Capacity** — track diluent source depletion
- **Error Recovery** — state rollback and idempotency