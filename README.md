# LLNL Capstone: Self-Healing Control Plane for a Hamilton STARlet

A safety-gated pipeline that takes a liquid-handling protocol, written as human-readable JSON, and makes sure it
runs cleanly in PyLabRobot's simulator before it could ever reach the robot. When the simulation fails, the
failure is translated into lab terms and a **local** language model repairs the protocol, under checks that stop
it from changing the experiment.

**Start here:** [`notebooks/pipeline_walkthrough.ipynb`](notebooks/pipeline_walkthrough.ipynb) runs every stage
on the serial dilution protocol and shows what each module takes in and hands on, ending with the repaired
protocol replayed in PyLabRobot's browser visualizer.
[`docs/self_healing_run_v1.md`](docs/self_healing_run_v1.md) is the write-up of the first successful repair run.

---

## How it works

```
                 ┌─────────────────────── one round ───────────────────────┐
 protocol IR ──► │ Stage 1 verifier ─► Stage 2 compiler ─► Stage 3 ChatterBox │ ──► PASSED ──► Stage 4 visualizer ──► Stage 5 hardware
 (JSON)          │  safety rules       deterministic       PLR trackers       │                (watch the replay)       (stub)
                 └──────────────────────────────┬────────────────────────────┘
                                                │ first failure
                                                ▼
                               diagnostic in lab terms (step, cause, numbers, fixes)
                                                │
                                                ▼
                    local model (Ollama) proposes IR edits ──► harness checks ──► next round
```

| Stage | Module | What it does |
|---|---|---|
| IR | `protocols/*.json` | The plan a scientist reviews: steps plus the reagent volumes loaded before the run |
| 1. Verifier | `pipeline/stage1_verifier.py` | Checks the IR against safety rules (below) with its own plate and tip model |
| 2. Compiler | `pipeline/stage2_compiler.py` | Deterministic IR → PyLabRobot code; one statement per step with a `# step N` comment |
| Deck | `pipeline/deck.py`, `config/plr_deck.json` | Fixed STARlet layout; maps each IR labware ID to a PLR resource |
| 3. Simulator | `pipeline/stage3_simulator.py` | Runs the code on PLR's `LiquidHandlerChatterboxBackend` with tip and volume tracking, maps any exception back to its IR step |
| Diagnostics | `pipeline/diagnostics.py` | Turns PLR exceptions into lab-concept explanations with suggested IR edits |
| Self-healing | `pipeline/self_heal.py` | Sends diagnostics to a local model, checks its edits, and re-runs Stages 1–3 |
| 4. Visualizer | `pipeline/stage4_visualizer.py` | Replays the passing protocol in PyLabRobot's browser visualizer, step by step |
| 5. Executor | `pipeline/stage5_executor.py` | Hardware execution (**stub**) |

### Design choices

- **The model never writes Python.** The IR → PyLabRobot translation is fixed code, so the same IR always
  compiles to the same program. The model only edits the IR, which keeps the human-readable plan the source
  of truth.
- **The deck is config, not model output.** Labware and positions come from `config/plr_deck.json`.
- **Runs locally.** The repair model is a local Ollama model (default `qwen2.5-coder:7b`); no API key needed.
- **Repairs go to a person.** A repaired protocol is saved as `*_healed.json` with a diff for review. It never
  replaces the original automatically.

### What each layer catches

| Layer | Catches | Examples |
|---|---|---|
| Stage 1 verifier | Rule violations in the plan | Dead volume, well overflow, tip reuse, missing tips, cross-contamination |
| Stage 3 simulator | Physical problems the rules don't model | 8 channels into a 17 mm tube; a source tube running dry |
| Harness checks | Model edits that would change the experiment or break the IR | See below |

---

## Stage 1 safety rules

Volume limits come from `config/labware.json` (Corning 3595 plate: 30 µL dead volume, 330 µL usable maximum).

| Error code | Cause | Fix |
|---|---|---|
| `DRY_ASPIRATE` | An aspirate would leave a plate well below 30 µL | Aspirate less, or start the well with more liquid |
| `VOLUMETRIC_OVERFLOW` | A dispense would take a plate well above 330 µL | Dispense less, or use another well |
| `CONTAMINATED_TIP` | A channel aspirates from a different source without `tips_off` | Same source may be reused; otherwise `tips_off` + `tips_on` |
| `TIP_DEPLETED` | Tips picked from a rack column that was already used (tracked per rack) | Use an unused column or another rack |
| `MISSING_TIP` | Aspirate or dispense on a channel with no tip mounted | `tips_on` first |
| `VALIDATION_ERROR` | A required field is missing (column for `tips_on` or plate steps, `duration_s`, `speed_rpm`) | Add the field |
| `TIPS_DURING_HOLD` | `incubate` or `shake` while tips are still mounted | `tips_off` first |

The verifier models plate wells and tips only. It does not model source containers (tubes, troughs), container
geometry, or tip capacity. Those are caught in Stage 3.

## Stage 3 diagnostics

The explanations and suggested fixes are not written in code. They live in
[`knowledge/diagnostics.json`](knowledge/diagnostics.json), a knowledge base about failures in the same way that
`config/labware.json` is an inventory of the labware. Each entry has a part people write and a part the pipeline
writes:

- **Curated:**
  - `when`: which failures the entry covers (PLR exception, message text, device code, the step's action, and
    whether the scientist loads the labware).
  - `explanation` and `fixes`: what the model is told, and which IR edits are suggested.
  - `notes`: why the wording is what it is. Never sent to the model. For example, "lower `volume_ul`" was removed
    from `INSUFFICIENT_LIQUID` because the intent guard always rejects it, and qwen kept proposing it.
- **Observed** (updated after every `cli.py --heal` and demo run):
  - how often the entry came up;
  - how often the model's repair made the failure go away, and with which edit ops;
  - why the model's edits were rejected;
  - which protocols and models hit it;
  - the last few raw errors.

  It is never sent to the model, so the model sees the same prompts however much has been recorded. Benchmark
  runs don't record, so repeated synthetic scenes don't swamp the counts.

Entries are checked top to bottom and the first match wins. Numbers that come from the deck or the whole protocol
(container width, total volume the plan aspirates, unused tip columns) are small named "facts" in
`pipeline/diagnostics.py`. The file is checked when it loads, so a typo in a hand edit fails right away instead of
mid-run.

To cover a new error, add an entry above `UNRECOGNIZED`. That entry's `observed.examples` lists the errors still
waiting for one.

| Code | PLR error | Meaning in the lab |
|---|---|---|
| `CHANNEL_SPACING` | `Resource is too small to space channels` | More channels than fit in the container at once (channels need 9 mm spacing) |
| `INSUFFICIENT_LIQUID` | `TooLittleLiquidError` | The source runs dry; reports how much the plan needs vs how much is loaded |
| `TIP_OVERFLOW` | `TooLittleVolumeError` on aspirate | More liquid than the mounted tips can hold |
| `CONTAINER_OVERFLOW` | `TooLittleVolumeError` on dispense | More liquid than the destination can hold |
| `TIP_ALREADY_MOUNTED` / `NO_TIP_MOUNTED` / `TIP_SPOT_EMPTY` | `HasTipError` / `NoTipError` | Tip pickup or use out of order, or tips already used |
| `CROSS_CONTAMINATION` | `CrossContaminationError` | A tip would touch a different liquid |
| `NOT_ON_HEATER_SHAKER` | plate's parent is not a `HeaterShaker` | `incubate` or `shake` on a plate the deck doesn't put on a heater-shaker |
| `SHAKE_SPEED_OUT_OF_RANGE` / `TEMPERATURE_OUT_OF_RANGE` | the simulated Hamilton heater-shaker's limits (20–2000 rpm, up to 105 °C, the same ones PLR's real backend asserts) | The device can't do it; changing it needs the scientist's approval |
| `HEATER_CANNOT_COOL` | PLR: `Backend does not support active cooling` | A step asks for a lower temperature than an earlier step heated to |
| `UNRECOGNIZED` | anything else | The raw error is passed through |

### Device and waste steps

Besides `tips_on`, `tips_off`, `aspirate` and `dispense`, the IR has three actions for plate assays:

| Action | Fields | What it does |
|---|---|---|
| `empty` | plate, `column`, `channels`, optional `waste` | Aspirates everything in the column (whatever it holds at that point) into the waste. No dead-volume rule; the tips count as having touched that column |
| `incubate` | plate, `duration_s`, optional `temperature_c` | Holds the plate on its heater-shaker; without `temperature_c` the heater switches off (room temperature) |
| `shake` | plate, `duration_s`, `speed_rpm`, optional `temperature_c` | Shakes the plate on its heater-shaker |

Device steps need a deck with a heater-shaker: `config/plr_deck_plate_assay.json` puts the Corning plate on a
Hamilton heater-shaker (rails 26) and adds a wash-buffer trough. A protocol picks its deck with a top-level
`"deck_config"` field; without one it uses `config/plr_deck.json`. Hold times are not waited out in simulation.
The model's prompt only describes these actions when the protocol uses them, so prompts for transfer-only
protocols are unchanged.

## Self-healing checks

The model can reply with two edit types: `replace_step` (replace the failing step with one or more steps) and
`set_initial_volume` (change how much reagent is loaded). Each edit must pass all three checks before it is applied:

| Check | Rejects |
|---|---|
| Step scope | Edits to any step other than the one that failed this round |
| Compiles | New steps the Stage 2 compiler can't translate (missing volume, unknown labware, ...) |
| Intent guard | Any change to the total volume each channel aspirates or dispenses at each location, to how often each column is emptied, or to the total time of each heated incubate or shake (by plate, temperature and speed). Room-temperature holds may be added or lengthened, e.g. to let the plate cool, but not shortened |

Edits are checked one at a time: those that pass are applied even if another edit in the same reply is
rejected (on an intent-guard violation, the reply's `replace_step` is dropped and its `set_initial_volume`
edits are kept). A rejected edit's reason is sent back to the model for the next round. The loop stops at a clean pass
(`HEALED`) or after `--max-rounds` (`GAVE_UP`). Giving up is safe: nothing that failed a check gets through.

---

## Setup

```bash
pip install -r requirements.txt
```

For self-healing, install [Ollama](https://ollama.com) and pull the default model:

```bash
ollama pull qwen2.5-coder:7b
```

## Live demo

A local web page that runs the self-healing loop and shows each round as it happens: which stage failed, the
lab-concept diagnostic, the model's reasoning and proposed edits, and whether the harness accepted them. When the
protocol passes, **Watch in PyLabRobot's visualizer** opens PLR's own visualizer in a new tab and replays it (Stage 4).

```bash
python demo/server.py            # then open http://127.0.0.1:8000  (--port to change)
```

Needs Ollama running with a model pulled. Runs are saved to `build/demo/<run id>/`, one run at a time.

The **Benchmark results** page (`/benchmark`) shows any run of `python -m benchmark.run` saved in
`build/benchmark/`: healed counts and mean scores per condition, a healed-by-retry-budget table, a scene ×
condition score grid, and every round of any run (click a cell). See
[docs/serial_dilution_benchmark_spec.md](docs/serial_dilution_benchmark_spec.md) for how runs are scored.

The **Library** page (`/library`) shows the static data the pipeline relies on. It is read-only: edit the files
and reload.

- **Labware tab:**
  - every item in `config/labware.json`, with its key specifications and which deck layouts place it;
  - every `config/plr_deck*.json` layout: labware positions, PyLabRobot resources, machines and carriers, and
    which protocols use it;
  - deck labware missing from the inventory, and inventory items no deck uses.
- **Knowledge base tab:** every entry of `knowledge/diagnostics.json` in matching order, showing:
  - when it applies, in plain words;
  - the explanation and fixes sent to the model, with placeholders highlighted;
  - the notes for people;
  - what recorded runs observed.

  A filter and an "only entries seen in a recorded run" toggle narrow it down.

## Usage

Run Stages 1–3 once and print the diagnostic on failure:

```bash
python cli.py --protocol protocols/serial_dilution_v1.json
```

Repair a failing protocol with the local model:

```bash
python cli.py --protocol protocols/serial_dilution_v1.json --heal
```

Watch the passing (or repaired) protocol in PyLabRobot's visualizer (Stage 4). This opens a browser tab at
`http://127.0.0.1:1337`, replays every step, and keeps the page open until you press Ctrl+C:

```bash
python cli.py --protocol protocols/serial_dilution_v1.json --heal --visualize
```

Options: `--model` (any Ollama model, default `qwen2.5-coder:7b`), `--max-rounds` (default 5),
`--feedback raw` (send the model only the raw PLR exception instead of the lab-concept diagnostic, for comparison),
`--output` (default `build/`, git-ignored), `--execute` (Stage 5, a stub for now).

Each run writes to `build/<protocol>/`: every round's IR (`round_N.json`) and compiled code (`round_N_plr.py`),
`heal_log.json`, and on success `<protocol>_healed.json` plus its compiled PyLabRobot code, `<protocol>_healed_plr.py`.

## Tests

```bash
python -m pytest precheck/ tests/ -q
```

- `precheck/test_verifier.py` (11 tests): the Stage 1 rules (volume boundaries, contamination tracking,
  per-rack tip depletion, and the v0 reference protocol).
- `tests/test_reproducible_v1.py` (4 tests): keeps `protocols/serial_dilution_v1.json` as a fixed, known-bad
  reference. It must pass Stage 1, fail Stage 3 at step 2 with `CHANNEL_SPACING`, and pass after the reference
  repair (split step 2, load 900 µL of stock), without the original file or input being modified.
- `tests/test_device_steps.py` (9 tests): `empty`, `incubate` and `shake` on `protocols/plate_wash_incubate_demo.json`.
  The demo is an uncorrected zero-shot Claude draft and stays known-bad (Stage 3 fails at step 28: 4000 µL of
  wash buffer loaded, 6400 µL needed). The tests check that, the reference repair, each device failure code,
  and that the intent guard protects holds and empties.
- `tests/test_partial_edits.py` (4 tests): edits that pass their checks are applied even when another edit in the
  same reply is rejected, and the rejected part is reported back to the model.
- `tests/test_diagnostics_kb.py` (16 tests): the diagnostics knowledge base loads, no entry is hidden behind an
  earlier one, typos in a hand edit (unknown field, condition, exception or fact; duplicate id) are reported when it
  loads, and self-healing runs are recorded into `observed` (on a copy, never the real file).

The live model loop has no unit tests; the notebook runs it end to end.

**Reproducibility rule:** `serial_dilution_v1.json` is the reference input for repair runs and stays in its
original, failing form. Repairs are written to `build/<protocol>/<protocol>_healed.json`, or to `docs/runs/`
for documented runs, and never over the original.

---

## Repository layout

```text
.
├── cli.py                        # Entry point: stages 1-3, --heal for the repair loop
├── requirements.txt
├── pipeline/
│   ├── stage1_verifier.py        # Safety rules on the IR
│   ├── stage2_compiler.py        # IR -> PyLabRobot code (deterministic)
│   ├── deck.py                   # Builds the PLR deck from config/plr_deck.json
│   ├── stage3_simulator.py       # ChatterBox dry run + error interceptor
│   ├── diagnostics.py            # PLR exception -> lab-concept diagnostic (looked up in knowledge/)
│   ├── self_heal.py              # Repair loop, Ollama backend, edit checks, ir_diff
│   ├── stage4_visualizer.py      # Replay in PyLabRobot's browser visualizer
│   └── stage5_executor.py        # Hardware execution (stub)
├── config/
│   ├── plr_deck.json             # PLR deck layout used by stages 2-5
│   ├── plr_deck_plate_assay.json # Same deck plus a heater-shaker holding the plate and a wash-buffer trough
│   ├── labware.json              # Labware specs used by the verifier (volume limits)
│   ├── protocol_defaults.json    # Initial hardware state and experiment parameters
│   └── hardware.json             # Earlier deck description (not used by the pipeline)
├── knowledge/
│   └── diagnostics.json          # Diagnostics knowledge base: what each simulator error means, how to fix it,
│                                 #   and what past self-healing runs learned about it
├── protocols/
│   ├── serial_dilution_v1.json   # Full 68-step serial dilution; fixed known-bad reference (don't overwrite)
│   ├── plate_wash_incubate_demo.json # Zero-shot Claude draft: coat, incubate, wash; known-bad (don't overwrite)
│   ├── serial_dilution_v0.yaml   # Earlier 12-step version (used by the verifier tests)
│   └── serial_dilution_simple.yaml
├── demo/
│   ├── server.py                 # Live self-healing demo (Flask + Server-Sent Events)
│   └── static/                   # Pages: live run (index/app.js), benchmark, library; shared common.js, style.css
├── notebooks/
│   └── pipeline_walkthrough.ipynb
├── tests/
│   ├── test_reproducible_v1.py   # Keeps serial_dilution_v1.json fixed as the known-bad reference
│   ├── test_device_steps.py      # empty / incubate / shake on the plate-assay demo
│   ├── test_partial_edits.py     # Partial acceptance of a model reply
│   └── test_diagnostics_kb.py    # The error knowledge base
├── docs/
│   ├── self_healing_run_v1.md    # Report on the first successful repair run
│   └── runs/                     # Logs and healed IRs from documented runs
├── precheck/                     # Verifier tests (+ older copies of the verifier and configs)
└── archive/                      # Earlier code kept for reference; not used by the pipeline
```

## Target hardware

- **Liquid handler:** Hamilton STARlet, 8-channel head
- **Software:** PyLabRobot 0.2.2 (`LiquidHandlerChatterboxBackend` for simulation)
- **Plate:** Corning 3595, 96-well flat bottom (PLR `cor_96_wellplate_360uL_Fb`)
- **Tips:** Hamilton 200 µL filtered tips in the spec; simulated with PLR's closest rack,
  `hamilton_96_tiprack_300uL_filter`

---

## Status and known gaps

**Working:** Stages 1–3, lab-concept diagnostics, and the self-healing loop with a local 7B model. One documented
successful repair of `serial_dilution_v1` in 3 rounds ([report](docs/self_healing_run_v1.md)).

**Not yet:**
- Natural language → IR generation. Protocols are written by hand.
- Stage 5 hardware execution.
- Repair reliability numbers. One successful run is shown; repeated runs and a raw vs translated feedback
  comparison (`--feedback raw`) are next.
- Unit tests for the live model loop (Stages 1–3 and the edit checks are covered on v1 by `tests/`).
- Labware changes in repairs. The intent guard rejects them (e.g. moving a reagent to a trough), even when they
  would be a valid fix.
- A `mix` action in the IR.
- Moving plates (gripper) and returning tips to the rack for reuse. Without tip return, washing with the
  8-channel head needs a fresh tip column per column per wash, so wash-heavy assays run out of tips quickly.
- Spill risk from shaking full wells, and plate reading. Neither is checked.
- `serial_dilution_v0.yaml` and `serial_dilution_simple.yaml` have no `initial_volumes_ul`, so their sources start
  empty in Stage 3.
- `serial_dilution_v1.json` metadata says `final_volume_per_well_ul: 100`, but its steps leave every well at
  50 µL. The pipeline only reads the steps; the metadata or the volumes should be corrected.
- `precheck/` still holds older copies of the verifier and configs. The tests use `pipeline/stage1_verifier.py`
  and `config/`.
