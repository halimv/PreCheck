# Serial Dilution Benchmark: Spec (draft)

**Status:** Draft for review. Items marked **OPEN** need a decision before the main run.
**Scope:** Benchmark the self-healing loop on one protocol, `protocols/serial_dilution_v1.json`. No other protocols, no hardware.

---

## 0. Scope for this update (implemented in `benchmark/`)

The full spec below is the target. This update runs a reduced version that fits in one evening:

| Piece | This update | Deferred |
|---|---|---|
| Faults | S1 (v1 natural), S2 × 5 stock loads, S3 × 5 diluent loads: 11 scenes | Family P, labware-with-approval |
| Conditions | B0, B1, LLM translated, LLM raw | Zero-shot PLR, larger model |
| Temperature | 0, one run per scene | 0.7 repeats, if time allows (`--temperature 0.7 --repeats N`) |
| Retry sweep | Budgets 1, 2, 3, 5, 10, read from one 10-round run per scene | n/a |
| C2, C3 | Keyword and value checks on the model's reasoning and edits | Structured diagnosis output (§5.3) |

**Why the retry sweep is free:** the repair prompt never mentions the round limit, and at temperature 0 the model and ChatterBox are deterministic. A run capped at k rounds is the first k rounds of a 10-round run, so one run per scene is scored at every budget.

**Run it:**

```bash
python -m benchmark.run                      # all 11 scenes x 4 conditions
python -m benchmark.run --conditions B0,B1   # baselines only, seconds
```

Results go to `build/benchmark/<timestamp>/`: `runs.jsonl` (one record per run, with every round), `summary.md`, and each run's per-round IR and console log.

---

## 1. Protocol under test

- **File:** `protocols/serial_dilution_v1.json`, 68 steps, 8 channels, 12 columns.
- **Dilution:** 1000 µM stock, 2-fold, column 1 down to column 12 (1000 µM to 0.488 µM). Every column gets 50 µL diluent, then 50 µL is transferred down the series. Column 12 discards 50 µL excess.
- **Expected concentrations:** the `dilution.columns` table in the IR. These are the ground truth for C5.
- **Expected volumes per step:** total stock aspirated is 8 × 100 µL = 800 µL. Total diluent aspirated is 8 × (200 + 200 + 150) µL = 4400 µL.

### 1.1 The unmodified v1 does not pass the simulator

Running `python cli.py --protocol protocols/serial_dilution_v1.json` fails at step 2 with `CHANNEL_SPACING`. The 17 mm tube cannot take 8 channels at once. The reference for healing is therefore the healed IR in [self_healing_run_v1.md](self_healing_run_v1.md), not v1 as written.

The healed IR (75 steps) splits step 2 into 8 single-channel aspirates and sets `tube_15ml` to 900 µL. Its ground-truth fix is the one the benchmark scores against.

### 1.2 Known inconsistencies to fix before the run

- `metadata.final_volume_per_well_ul` says 100, but the steps leave every well at 50 µL. The scorer's expected values must come from the steps, not the metadata.
- `config/protocol_defaults.json` describes a different protocol: `hamilton_robotip_200` tips, which the PLR deck doesn't have, and a different quality-control section. Don't use it as a source for the spec until it is reconciled.

---

## 2. Layers and what catches each fault

| Layer | Checks | Does not check |
|---|---|---|
| Stage 1 verifier (`pipeline/stage1_verifier.py`) | Plate well dead volume and overflow, tip inventory, missing tips, contamination | Source container volume, tube geometry, channel spacing |
| Stage 2 compiler | IR to PLR code, deterministic | Physical validity |
| Stage 3 simulator (ChatterBox, tip and volume tracking on) | Channel spacing, source volume, tip and container overflow, tip state, contamination | Arm kinematics, clogs, aspiration physics |

Tip state is tracked by PLR in the current version (checked directly with a PLR script; see §8).

**Consequence:** a plan-level fault (Family P below) is usually rejected by Stage 1 before the simulator runs. The loop then only sees a verifier message. A simulator-level fault (Family S) reaches Stage 3. The benchmark's main claim is about Family S, because that is where the loop must reason about physical reality.

---

## 3. Fault taxonomy

Each scene has **exactly one fault**, injected into the IR before the run. The agent never sees which fault was injected.

### Family S: simulator-level (primary)

| ID | Fault | Injection | Caught by | Ground truth for a correct repair | Valid edits |
|---|---|---|---|---|---|
| S1 | Channel spacing on tube | v1 as written (step 2 uses 8 channels into `tube_15ml`) | Stage 3 `CHANNEL_SPACING` | Split step 2 into single-channel aspirates of 100 µL | `replace_step` on step 2 |
| S2 | Stock under-loaded | `tube_15ml` loaded at `L` µL, with `L` drawn from a range below 800 | Stage 3 `INSUFFICIENT_LIQUID` | `set_initial_volume` for `tube_15ml` at ≥ 800 µL | `set_initial_volume` only |
| S3 | Diluent under-loaded | `reservoir_50ml` loaded at `L` µL, with `L` below 4400 | Stage 3 `INSUFFICIENT_LIQUID` | `set_initial_volume` for `reservoir_50ml` at ≥ 4400 µL | `set_initial_volume` only |

**Note on S2 and S3:** the intent guard rejects any edit that changes the total volume each channel aspirates. So lowering a step's volume is not a valid repair. The only valid repair is loading more reagent. The `INSUFFICIENT_LIQUID` diagnostic's "lower volume" suggestion is one the guard will reject.

Compare the healed IR, which loads 900 µL, with the 800 µL minimum. The benchmark accepts any load at or above the minimum.

**S1 combined with S2 (the v1 natural case):** the loop must fix S1 first, then S2 (the order in §1.1). The scorer must accept either order.

### Family P: plan-level (secondary, verifier-caught)

These faults are in the IR, so Stage 1 catches them first. They test the loop's response to rule violations, not to physical faults.

| ID | Fault | Injection | Caught by | Ground truth |
|---|---|---|---|---|
| P1 | Dry aspirate | Step 22 volume raised so the source well goes below 30 µL | Stage 1 `DRY_ASPIRATE` | Lower the volume (note: the intent guard may block this; see §6 OPEN) |
| P2 | Overflow | Step 7 volume raised so a well exceeds 330 µL | Stage 1 `VOLUMETRIC_OVERFLOW` | Lower the volume or use another well |
| P3 | Missing tip | Delete step 5 (`tips_on` before diluent) | Stage 1 `MISSING_TIP` | Restore `tips_on` |
| P4 | Tip reuse | Change step 21 to `hamilton_tiprack_96` column 1, which step 1 already used | Stage 1 `TIP_DEPLETED` | Use an unused column |
| P5 | Contamination | Delete step 4 (`tips_off` after stock) | Stage 1 `CONTAMINATED_TIP` | Restore `tips_off` |

Family P is **not** in the main score. It appears only in the sensitivity runs, to show what the loop does with a rule violation.

### Natural and synthetic faults

- **Natural faults** are the v1 problems (S1, and S2 at the 600 µL load). They happen without injection.
- **Synthetic faults** are all others. Injection must be a single, documented IR edit so anyone can reproduce it.

---

## 4. Scenes

- **Scene** = fault × injection site × magnitude × repeat index.
- **Variation source:** ChatterBox is deterministic. The same IR always produces the same result, so a seed does not add physical noise. Scenes differ by injection site and magnitude instead. For example, S2 uses several loaded volumes below 800 µL.
- **Variance across repeats** comes only from the LLM. Repeats of the same scene use temperature 0.7 (§6.3).
- **Scene count (first pass):** S1 × 1, S2 × 5 volumes, S3 × 5 volumes, each × 10 repeats. That is 110 runs per condition, before sensitivity sweeps. Family P is excluded from this count.

---

## 5. Scoring

### 5.1 Checkpoints

| Checkpoint | Points | Condition |
|---|---|---|
| C1 Started | +1 | The run gets past the first step with no error |
| C2 Mistake identified | +1 | At least one attempt's structured diagnosis names the injected fault (fault type and step or labware) |
| C3 Correct result identified | +1 | The structured diagnosis gives the correct corrected value or action (table in §3) |
| C4 Correct execution | +1 | A corrected attempt applies the ground-truth fix, as checked against the IR |
| C5 Final result within tolerance | +1 | Final concentrations match the expected table within **1% relative** |
| Budget exhausted without C5 | −1 | The run hits `--max-rounds` without passing all stages |

Range: −1 to 5.

### 5.2 Diagnosis and execution sub-scores

- **Diagnosis** = C2 + C3 (0 to 2).
- **Execution** = C4 + C5 (0 to 2).

Report both. A run with diagnosis 2 and execution 0 is the "knew it, did it wrong" case.

### 5.3 Structured diagnosis

C2 and C3 are checked against a structured output, not against free text judged by another model. The loop must emit, per round:

```json
{"fault_type": "INSUFFICIENT_LIQUID", "labware": "tube_15ml", "required_ul": 800}
```

The scorer compares those fields to the injected fault. Free-text reasoning is logged but not scored.

**Implementation note:** the current loop does not emit this structure. Adding it is a prerequisite for C2 and C3.

### 5.4 Failure labels

Every failed run also gets one label, so the score and the failure mode are reported separately:

- `GAVE_UP`: budget exhausted
- `WRONG_TARGET`: the edit changed a step or labware outside the failing step's scope
- `REJECTED_ALL`: every edit was rejected by a harness check
- `CRASH`: the loop raised an exception
- `STALLED`: the same edit repeated across rounds
- `CONTEXT_LIMIT`: the prompt exceeded the model's context window (`num_ctx`)

---

## 6. Conditions and sensitivity

### 6.1 Conditions

| Condition | Description |
|---|---|
| B0 fail-on-error | No repair. Baseline floor. |
| B1 rule-based | Applies the translator's suggested fix directly. Tests the translator, not the LLM. |
| L-translated | LLM loop, lab-concept diagnostics (current default) |
| L-raw | LLM loop, raw PLR exception text only |

**B1 caveat:** B1 uses the translator's own suggestion. If the translator is right, B1 scores high by construction. Report it as a ceiling for the translator, not as a competitor to the LLM.

### 6.2 Sensitivity sweeps

Each sweep varies one factor, holding the others at their defaults.

| Factor | Values | Measured |
|---|---|---|
| Retry budget (`--max-rounds`) | 1, 2, 3, 5, 10 | Score, success rate, and tokens against rounds |
| Representation | **Zero-shot PLR** (model writes PLR Python directly) vs **IR edits** (current: model edits the IR JSON) | Score, success rate, and tokens |

I'm assuming "intermediate representation" means the IR JSON. Tell me if you meant something else.

Run the retry × representation factorial on a subset of scenes to keep cost down.

### 6.3 Decisions

Settled:

1. **Penalty:** the −1 stacks on top of checkpoint points, so the range is −1 to 5. Report the floor explicitly.
2. **Model:** `qwen2.5-coder:7b` for the main run. Larger models appear only as a sensitivity condition.
3. **Temperature:** temperature 0 for the baseline. Temperature 0.7 for the 10 repeats per scene. Report this setting with the results.
4. **C5 tolerance:** 1% relative.
5. **Labware changes:** allowed, but only behind a scientist-approval flag. This is a new condition: the loop may propose moving reagent to another container, and the run is scored only if the approval flag is set. Scoring for these runs is separate from the fixed-labware runs.
6. **P1 scoring:** if the intent guard rejects the correct repair, the run counts as a fail (no C4 or C5, label `REJECTED_ALL`).
7. **Scene count:** 5 loaded volumes each for S2 and S3, 10 repeats per scene, about 110 runs per condition.

Dropped:

- **Token budget:** no sweep. The model runs locally, so tokens have no cost. Tokens and wall-clock time per run are reported as metrics (§7). If a run hits the context limit (`num_ctx`), that is recorded as a failure label.

---

## 7. Logging

One JSON record per run, in `build/benchmark/<run id>/runs.jsonl`:

- Scene: fault ID, injection site, magnitude, repeat index
- Condition and config: model, temperature, max rounds, feedback mode, representation, `num_ctx`
- Per round: stage that failed, diagnostic, model response, structured diagnosis, edits proposed, harness decisions, tokens used
- Outcome: final status (`HEALED`, `GAVE_UP`, `REJECTED_ALL`, and so on), failure label, C1–C5, diagnosis and execution sub-scores, total score, total tokens, wall-clock time
- Final state: concentrations per well and volumes per source, for C5

---

## 8. Checks already done

- **Tip state** is tracked by PLR 0.2.2 with tip and volume tracking on. Three clean pick-up, aspirate, dispense, and discard cycles pass. Four bad sequences raise the expected errors: aspirate with no tip, double pickup, rack position reuse, and overdraw from a 50 µL trough. The check script is `chatterbox_state_check.py` in the session scratchpad.
- **v1 as written** fails at step 2 with `CHANNEL_SPACING`, as expected.
- **The healed IR** from the 2026-10-21 run passed all three stages. Its repair (8 single-channel aspirates, 900 µL load) matches the ground truth in §3.

---

## 9. Not yet done

**Found in the smoke test:** the `INSUFFICIENT_LIQUID` diagnostic always lists "Lower volume_ul in step N" as a suggested fix, but the intent guard rejects every such edit. In the S2_stock_790 smoke run, the translated-feedback model followed that suggestion in all 10 rounds and gave up, while the raw-feedback model loaded more stock and healed in 2 rounds. Removing the suggestion would change the condition under test, so it was left as is for the first full run and reported as a finding. **Fixed afterwards:** the diagnostic now offers only `set_initial_volume` when the source is a loaded container, and says lowering `volume_ul` is rejected. The translated condition was rerun on the fixed diagnostic; compare the two runs on the Benchmark page.

- Structured diagnosis output (§5.3). Required for C2 and C3.
- Ground-truth fix checker (C4) that compares the edited IR against the expected step set.
- Scene generator and runner. Nothing in the repo runs a batch yet.
- Hand-labeled validation set for the scorer: about 20 transcripts, to measure agreement with the automatic scorer.
- Reconciling `protocols/serial_dilution_v1.json` metadata and `config/protocol_defaults.json`.
- Updating the stale ChatterBox note in `archive/README_ARCHIVE.md`.
