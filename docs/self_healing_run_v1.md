# Self-Healing Run Report: `serial_dilution_v1` with qwen2.5-coder:7b

**Date:** 2026-10-21
**Protocol:** `protocols/serial_dilution_v1.json` (68 steps, 2-fold serial dilution across 12 columns)
**Repair model:** `qwen2.5-coder:7b` via Ollama 0.33.1 (local, temperature 0, `num_ctx` 32768)
**Simulator:** PyLabRobot 0.2.2, `LiquidHandlerChatterboxBackend`, tip and volume tracking on
**Outcome:** Healed in 3 repair rounds (run 5); runs 1–4 gave up and led to harness fixes
**Run artifacts:** [`docs/runs/2026-10-21_v1_qwen2.5-coder-7b/`](runs/2026-10-21_v1_qwen2.5-coder-7b/) (`heal_log.json`, `serial_dilution_v1_healed.json`, and its compiled PLR code `serial_dilution_v1_healed_plr.py`)

---

## 1. Summary

The v1 protocol passes the Stage 1 safety verifier but has two physical problems that only show up when PyLabRobot simulates it. A local 7B model, given lab-concept diagnostics from the simulator, repaired both by editing the protocol IR. It never wrote Python. Getting there took four failed runs. Each failure exposed a gap in the harness, and eight of the ten fixes made were to the harness, not to the model.

Key result: **every run was safe.** Edits that changed the experiment, or protocols that failed simulation, were never accepted. Failed runs stopped at the round cap with `GAVE_UP`.

---

## 2. Pipeline under test

```
                  ┌──────────────────────────────────────────────────────────┐
                  │                    one repair round                      │
 protocol IR ───► │ Stage 1 verifier ─► Stage 2 compiler ─► Stage 3 ChatterBox│ ──► PASSED: healed IR
                  │ (safety rules)      (deterministic)     (PLR trackers)   │
                  └───────────────┬──────────────────────────────────────────┘
                                  │ first failure → diagnostic
                                  ▼
                  qwen2.5-coder:7b proposes IR edits (JSON)
                                  │
                                  ▼
                  harness checks the edits → applied or rejected (reason fed back)
```

| Component | File | Role |
|---|---|---|
| Stage 1 verifier | `pipeline/stage1_verifier.py` | Dead volume, overflow, tip inventory, cross-contamination rules on the IR |
| Stage 2 compiler | `pipeline/stage2_compiler.py` | Deterministic IR → PLR module, one statement per step with a `# step N` comment |
| Deck builder | `pipeline/deck.py` + `config/plr_deck.json` | Fixed STARlet layout; starting reagent volumes come from the IR's `initial_volumes_ul` |
| Stage 3 simulator | `pipeline/stage3_simulator.py` | Runs the module in ChatterBox, maps any exception back to its IR step, snapshots the deck |
| Diagnostic translator | `pipeline/diagnostics.py` | Turns PLR exceptions into lab-concept explanations and suggested IR edits |
| Self-healing loop | `pipeline/self_heal.py` | Ollama backend, edit application, guardrails, round history |
| CLI | `cli.py` | `python cli.py --protocol <IR> --heal` |

**What the model can do:** reply with JSON edits of two kinds:
- `replace_step`: replace step N with one or more steps (edit, split, or delete it)
- `set_initial_volume`: change how much reagent the scientist loads into a container

The harness then renumbers steps and re-runs all three stages.

---

## 3. The two problems in the v1 protocol

| # | Where | Problem | Why Stage 1 misses it |
|---|---|---|---|
| A | Step 2 | Aspirates stock with all 8 channels at once from `tube_15ml`. The PLR tube is 17 mm wide and Hamilton channels must be at least 9 mm apart, so only one channel fits. PLR raises `ValueError: Resource is too small to space channels.` | The verifier models volumes and tips, not container geometry |
| B | IR `initial_volumes_ul` | 600 µL of stock is loaded, but the plan aspirates 8 × 100 = 800 µL. PLR raises `TooLittleLiquidError` at the 7th aspirate. | The verifier doesn't track volumes in source containers (tubes, troughs) |

Problem B only becomes visible once problem A is fixed, because the simulation stops at the first failure.

---

## 4. Run-by-run account

### Run 1: GAVE UP after 5 rounds

| Round | Failure | What qwen did |
|---|---|---|
| 0 | Step 2 `CHANNEL_SPACING` | **Correct fix:** replaced step 2 with 8 single-channel aspirates of 100 µL (channels `[0]` … `[7]`) |
| 1 | Verifier: *"Step 2: aspirate action requires 'column' field."* | Tried to add tip-rack columns to the aspirates |
| 2–5 | Same verifier error | Rewrote unrelated steps 13 and 29, dropping the plate column on step 29; re-applied "replace step 2" to already-split steps; the IR grew to 103 steps |

**Root causes:**
- **A verifier regression (a bug of mine, not the model's).** When the verifier moved to `pipeline/stage1_verifier.py` during the repo reorganization, it began requiring `column` on every aspirate and dispense. Tubes, troughs and waste have no columns, so qwen's correct fix was rejected with a misleading message.
- **Nothing stopped the model from editing steps that were working.**
- **Renumbering confused the model.** After step 2 became 8 steps, every later step shifted, but the "earlier rounds" history still quoted the old step numbers.
- **Rejection reasons weren't fed back** to the next round.

**Fixes:**
1. **Verifier:** `column` is required only for `tips_on` and for plate aspirate/dispense. Single containers share column index 0, as in the original verifier.
2. **Step scope:** `replace_step` may only target the step that failed this round. `set_initial_volume` is always allowed.
3. **History in words:** earlier rounds are described as "CHANNEL_SPACING was fixed: replaced the failing step with 8 step(s)", marked "already applied, do not repeat", with no stale step numbers.
4. **Rejection feedback:** when an edit is rejected, the reasons go into the next round's prompt.

### Run 2: GAVE UP after 5 rounds

| Round | Failure | What qwen did |
|---|---|---|
| 0 | Step 2 `CHANNEL_SPACING` | Split step 2 (applied) |
| 1 | Step 8 `INSUFFICIENT_LIQUID`: the tube ran dry at the 7th aspirate | Its reasoning said *"increase the initial volume of the tube to at least 800 uL"*, but its edit rewrote step 8 with different volumes |
| 2–5 | Follow-on failures from that edit | One round aspirated 600 µL into a tip; the translator labeled the error as a well overflow |

**Root causes:**
- **Reasoning and action didn't match.** The model explained the right fix and returned a different one. This was the main small-model weakness seen.
- **Nothing checked that an edit preserved the experiment.**
- **A translator bug of mine:** a `TooLittleVolumeError` raised during an aspirate means the tip is full, but it was reported as `CONTAINER_OVERFLOW`.

**Fixes:**
5. **A first intent guard:** reject edits that change any plate well's final volume, per the verifier's volume model. This was replaced in run 4; see fix 9.
6. **Exact edits in suggested fixes:** the `INSUFFICIENT_LIQUID` diagnostic now includes the edit verbatim: `{"op": "set_initial_volume", "labware": "tube_15ml", "volume_ul": 900}` (800 µL needed plus a 10% margin, rounded up to 50 µL).
7. **Translator:** a `TooLittleVolumeError` during an aspirate is now `TIP_OVERFLOW`; during a dispense it stays `CONTAINER_OVERFLOW`.

### Run 3: GAVE UP after 5 rounds

| Round | Failure | What qwen did |
|---|---|---|
| 0 | Step 2 `CHANNEL_SPACING` | Split step 2, but **without `volume_ul`** on any of the 8 new steps. The edit was accepted. |
| 1–5 | Compiler: *"Step 2: aspirate needs 'volume_ul'."* | Rewrote the step repeatedly, still omitting volumes |

**Root causes:**
- **The reply schema didn't require `volume_ul`**, so Ollama's constrained decoding let the model omit it.
- **The plate-volume guard missed it.** The verifier treats a missing volume as 0 µL, and a 0 µL aspirate from the tube doesn't change any plate well.
- **Malformed steps entered the IR** and were only caught one round later by the compiler.

**Fix:**
8. **Validate at apply time:** each proposed step goes through the Stage 2 translator before it enters the IR. A missing `volume_ul`, unknown labware, or a missing plate column rejects the edit immediately, with the reason fed back.

### Run 4: GAVE UP after 5 rounds

| Round | Failure | What qwen did |
|---|---|---|
| 0 | Step 2 `CHANNEL_SPACING` | Split without volumes → **rejected at apply time** (fix 8 working) |
| 1 | Same | Re-sent the split with volumes (applied) |
| 2 | Step 8 `INSUFFICIENT_LIQUID` | Cut the aspirate to **60 µL**. The plate-volume guard accepted it. |
| 3–5 | Follow-on failures | Kept rewriting step 8, omitting volumes again |

**Root cause:**
- **The plate-volume guard measured the wrong thing.** The verifier doesn't track what's in a tip, so after the 60 µL aspirate it still counted the full 100 µL dispense into the plate. The experiment changed, but the guard couldn't see it.

**Fixes:**
9. **Transfer-totals intent guard,** replacing fix 5. For every channel, the harness sums the volume aspirated and dispensed at each location (labware, plus column for plates) and compares it with the original plan. Any change rejects the edit, with a message listing the changed totals and "load more reagent instead of moving less".
   - Splitting one 8-channel step into eight 1-channel steps keeps every total the same → **allowed**
   - `set_initial_volume` changes no transfers → **allowed**
   - Cutting 100 µL to 60 µL changes a channel's total at `tube_15ml` → **rejected**
10. **`volume_ul` is required in the reply schema,** with the instruction "always include it; 0 for tips_on and tips_off".

### Run 5: HEALED in 3 rounds (wall time about 50 s)

| Round | Stages | Failure | qwen's edit | Harness decision |
|---|---|---|---|---|
| 0 | verify ✓, compile ✓, simulate ✗ | Step 2 `CHANNEL_SPACING` | Replace step 2 with 8 single-channel 100 µL aspirates | **Applied:** totals unchanged |
| 1 | simulate ✗ | Step 8 `INSUFFICIENT_LIQUID` (600 µL loaded, 800 µL needed) | Replace step 8 (channel 6's 100 µL aspirate) with **one 8-channel aspirate of 60 µL** | **Rejected by the intent guard:** *"channel 0 aspirate at tube_15ml: 100 -> 160 uL; channel 1 …"* |
| 2 | simulate ✗ | Same failure, plus the rejection reason | `set_initial_volume tube_15ml → 900 µL` | **Applied** |
| 3 | verify ✓, compile ✓, simulate ✓ | None: all 75 steps ran in ChatterBox | n/a | **HEALED** |

The rejected round-1 edit was wrong in two ways. It moved less stock in total, and it went back to an 8-channel aspirate from the tube, which would have hit the channel-spacing failure again. The intent guard caught it before it reached the simulator. The guard's message showed channels 0–5 and 7 going from 100 µL to 160 µL, and channel 6 from 100 µL to 60 µL.

---

## 5. The repair, as the scientist would review it

Output of `ir_diff` (original v1 vs healed). Unchanged steps are hidden, and step numbers are left out so renumbering doesn't show up as changes:

```diff
--- original
+++ healed
@@ -1,4 +1,11 @@
-initial_volumes_ul: {"tube_15ml": 600, "reservoir_50ml": 5500}
+initial_volumes_ul: {"tube_15ml": 900, "reservoir_50ml": 5500}
 {"action": "tips_on", "labware": "hamilton_tiprack_96", "column": 1, "channels": [0, 1, 2, 3, 4, 5, 6, 7]}
-{"action": "aspirate", "labware": "tube_15ml", "column": 1, "volume_ul": 100.0, "channels": [0, 1, 2, 3, 4, 5, 6, 7]}
+{"action": "aspirate", "labware": "tube_15ml", "volume_ul": 100.0, "channels": [0]}
+{"action": "aspirate", "labware": "tube_15ml", "volume_ul": 100.0, "channels": [1]}
+{"action": "aspirate", "labware": "tube_15ml", "volume_ul": 100.0, "channels": [2]}
+{"action": "aspirate", "labware": "tube_15ml", "volume_ul": 100.0, "channels": [3]}
+{"action": "aspirate", "labware": "tube_15ml", "volume_ul": 100.0, "channels": [4]}
+{"action": "aspirate", "labware": "tube_15ml", "volume_ul": 100.0, "channels": [5]}
+{"action": "aspirate", "labware": "tube_15ml", "volume_ul": 100.0, "channels": [6]}
+{"action": "aspirate", "labware": "tube_15ml", "volume_ul": 100.0, "channels": [7]}
 {"action": "dispense", "labware": "corning_3595", "column": 1, "volume_ul": 100.0, "channels": [0, 1, 2, 3, 4, 5, 6, 7]}
```

In lab terms: **load 900 µL of stock instead of 600 µL, and draw it with one channel at a time instead of all eight together.** Every well still receives the same volumes as the original plan.

**Independent re-check:** the healed IR was run through the pipeline again with no model involved (`python cli.py --protocol <healed IR>`):

```
[simulate] PASSED: All 75 steps ran in ChatterBox with tip and volume tracking.
```

The verifier test suite (`precheck/test_verifier.py`) still passes 11/11 after the verifier fix.

### About "the code is written but not shown"

When I reported run 5 earlier, the CLI's diff was hard to read. The original `ir_diff` compared lines that included step numbers. After step 2 was split into 8 steps, every later step's number shifted by 7, so the diff showed all ~70 steps as changed even though only two things actually changed.

I rewrote `ir_diff` in `pipeline/self_heal.py` to leave step numbers out of the compared lines and to show only one line of context. The edit was saved, but the command that would have run the new version and printed its output was rejected before it ran, so at that point the new code existed but had never been executed or shown to you. It has since been run, and its output is the diff above, which now shows only the two real changes.

---

## 6. What the runs showed

1. **The harness did most of the work.** Of the ten fixes, eight constrain or check the model: step scope, apply-time validation, the intent guard, the required-field schema, history wording, rejection feedback, and exact suggested edits. Two fixed bugs of mine (the verifier regression and the tip-overflow label). The model's job shrank to choosing a sensible local edit.
2. **The 7B model's main weakness was acting on its own reasoning.** It usually diagnosed the problem correctly in its `reasoning` text, then returned a different edit. A specific rejection reason followed by a retry was what got it through.
3. **Each failure also improved the diagnostics.** The diagnostics that worked best spelled out the exact edit (`set_initial_volume … 900`). This supports the project's claim that lab-concept diagnostics, not raw tracebacks, are what make self-healing work. That hasn't been measured yet; see section 7.
4. **Safety held regardless of model quality.** A weak model can make the loop give up, but can't get an unsafe or intent-changing protocol accepted. The only output path is a protocol that passed all three stages and the intent guard, and it still goes to a scientist for review.

---

## 7. Limitations and next steps

- **One successful run, at temperature 0.** The prompts changed between runs as fixes were added, so this shows the loop *can* heal v1, not how *reliably* it does. Next: repeat run 5 N times (with temperature > 0 or varied seeds) and report the success rate and average rounds.
- **Raw vs translated feedback is not yet measured.** `--feedback raw` sends only the PLR exception text. Running both modes on the same model is the experiment that tests the translator's value directly.
- **The intent guard forbids changing labware.** Moving the stock into a trough, for example, would be rejected. That keeps the experiment fixed, but it also blocks some legitimate repairs. Labware changes could be allowed behind explicit scientist approval.
- **Translator coverage is partial.** It covers channel spacing, insufficient liquid, tip and container overflow, tip mounted/missing/used, and cross-contamination. Anything else is reported as `UNRECOGNIZED` with the raw error.
- **The healed IR changes the scientist's prep** (900 µL of stock). It is saved as `*_healed.json` and labeled as needing review. It does not replace the original.
- **Not committed.** None of the Stage 2/3/self-healing work in this report is committed yet.

---

## 8. Reproducing

```bash
ollama pull qwen2.5-coder:7b

# One pass through stages 1-3 (no model): shows the step 2 CHANNEL_SPACING diagnostic
python cli.py --protocol protocols/serial_dilution_v1.json

# Self-healing loop
python cli.py --protocol protocols/serial_dilution_v1.json --heal

# Same, but the model sees only raw PLR exceptions
python cli.py --protocol protocols/serial_dilution_v1.json --heal --feedback raw
```

Outputs go to `build/serial_dilution_v1/`: every round's IR (`round_N.json`) and compiled module (`round_N_plr.py`), `heal_log.json`, and on success `serial_dilution_v1_healed.json` plus the diff on screen.
