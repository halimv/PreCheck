# LLNL Capstone: Self-Healing Control Plane for a Hamilton STARlet

A safety-gated pipeline that turns a written liquid-handling protocol (a PDF, a text file, or a paragraph) into a
PyLabRobot script for a Hamilton STARlet, and makes sure that script runs cleanly in PyLabRobot's simulator before
it can reach the robot.

1. **Claude drafts the plan.** The Claude CLI turns the protocol text into the IR: human-readable JSON steps, the
   reagent volumes to load, and the labware the protocol needs, named by role ("culture: a tube of at least 5 mL").
2. **The deck is built from the lab's labware.** Each need is matched to real labware: what is on the STARlet now
   first, then VENUS's labware library. What nothing fits goes back to Claude. The deck and a mapping (IR name →
   labware, barcode, carrier, position) are saved in `decks/`.
3. **It is checked on a model of this instrument, and repaired.** The IR is compiled and run on PyLabRobot's STAR
   model, configured from the STARlet's own firmware file, on that deck. When something fails, the failure is
   explained in lab terms and a model edits the IR, under checks that stop it from changing the experiment. Claude
   Haiku is the default repair model (`--healer ollama` for a local one); at most 5 rounds.
4. **The scientist reviews it.** What every well ends up holding and at what dilution, reagent volumes, limits,
   and suggestions that are improvements, not errors. The assay is replayed in PyLabRobot's 3D viewer. A change
   asked for in words goes back through steps 1-3 as the next version.
5. **A person runs it.** The passing IR, its PLR script, a report and the same deck as an AHC layout are saved in
   `healed/`. The demo's Execute page walks you through setting up the deck, then runs the script on the STARlet.
   [AHC](https://github.com/xthomaswang/ahc) is optional: a supervised run with error recovery and an on-site
   check that the deck is what the files say.

```bash
python pipeline.py input.txt
```

**Start here:** [`notebooks/pipeline_walkthrough.ipynb`](notebooks/pipeline_walkthrough.ipynb) runs every stage
on the serial dilution protocol and shows what each module takes in and hands on, ending with the repaired
protocol replayed in PyLabRobot's browser visualizer.
[`docs/self_healing_run_v1.md`](docs/self_healing_run_v1.md) is the write-up of the first successful repair run.

---

## How it works

```
 protocol PDF / text
        │
        ▼
 Stage 0 Claude CLI ──► draft IR with labware needs ──► Stage 0b deck builder ──► deck + mapping (decks/)
        ▲                                                │ needs nothing fits:
        └──────────── closest options from the library ──┘ back to Claude
                                │
                 ┌──────────────▼────────── one round ──────────────┐
 protocol IR ──► │ Stage 2 compiler ─► Stage 3 ChatterBox            │ ──► PASSED ──► healed/ ──► Stage 5 STARlet
 (JSON)          │  deterministic       PLR trackers                 │                IR + PLR    (Execute page:
                 └──────────────────────────────┬───────────────────┘                script      deck checklist, run)
                                                │ first failure                     Stage 4 visualizer: optional replay
                                                ▼
                               diagnostic in lab terms (step, cause, numbers, fixes)
                                                │
                                                ▼
                    local model (Ollama) proposes IR edits ──► harness checks ──► next round
```

| Stage | Module | What it does |
|---|---|---|
| Entry point | `pipeline.py` | Runs the stages below from one command, live in the terminal |
| 0. Drafter | `pipeline/stage0_drafter.py` | Protocol PDF/text → IR with the Claude CLI (`claude -p`), given the IR rules and the labware there is; saved in `drafts/` |
| 0b. Deck builder | `pipeline/deck_builder.py` | Each labware need → real labware (the deck on the STARlet, then VENUS's library); unresolved needs back to Claude; deck config and mapping in `decks/` |
| IR | `drafts/`, `healed/` | The plan a scientist reviews: labware needs, steps, and the reagent volumes loaded before the run |
| 1. Verifier | `pipeline/stage1_verifier.py` | **Out of the self-healing loop for now.** Safety rules (below) with its own plate and tip model; the simulator's failures drive the repairs |
| 2. Compiler | `pipeline/stage2_compiler.py` | Deterministic IR → PyLabRobot code; one statement per step with a `# step N` comment |
| Deck | `pipeline/deck.py`, `config/instrument/ahc_deck.lay` | The deck on the STARlet, read from VENUS's layout and labware library; maps each IR labware ID to a PLR resource |
| 3. Simulator | `pipeline/stage3_simulator.py` | Runs the code on PLR's `LiquidHandlerChatterboxBackend` with tip and volume tracking, maps any exception back to its IR step |
| Diagnostics | `pipeline/diagnostics.py` | Turns PLR exceptions into lab-concept explanations with suggested IR edits |
| Self-healing | `pipeline/self_heal.py` | Sends diagnostics to a local model, checks its edits, and re-runs Stages 2–3 |
| 4. Visualizer | `pipeline/stage4_visualizer.py` | Replays the passing protocol in PyLabRobot's browser visualizer, step by step |
| Setup guide | `pipeline/setup_guide.py` | The deck setup checklist for a passing IR: carriers, rails, positions, tip columns, reagent volumes |
| 5. Executor | `pipeline/stage5_executor.py` | Runs a passing IR step by step on the STARlet (`STARBackend`) or ChatterBox, with abort and a tip-check mode |

### Design choices

- **No model writes Python.** The IR → PyLabRobot translation is fixed code, so the same IR always
  compiles to the same program. Claude writes the IR and the repair model only edits it, which keeps the
  human-readable plan the source of truth.
- **The deck is ground truth, not model output.** Labware and positions come from VENUS: the `.lay` of the deck on
  the STARlet, built from VENUS's labware library (see [The static library](#the-static-library-the-real-system)).
  Claude says what labware the protocol needs, never where it goes: the deck builder picks real labware and
  positions, and only labware in the library can be chosen.
- **Repairs run locally.** The repair model is a local Ollama model (default `qwen2.5-coder:7b`). Only the first
  draft calls Claude.
- **Repairs go to a person.** A repaired protocol is saved in `healed/` (and the round files in `build/`) with a
  diff for review. It never replaces the original.
- **Only what passed can run.** The Execute page re-runs the compiler and simulator on a healed file before it runs, and its deck
  checklist uses the volumes the simulation checked.

### What each layer catches

| Layer | Catches | Examples |
|---|---|---|
| Stage 0b deck builder | Labware the lab does not have | A 500 mL tube; tips smaller than an aspiration |
| Stage 3 simulator | Physical problems: what the repairs are built on | 8 channels into a 17 mm tube; a source tube running dry; a tip or well overflowing; a used tip spot |
| Harness checks | Model edits that would change the experiment or break the IR | See below |

---

## Stage 1 safety rules (out of the loop for now)

The verifier is not run by the self-healing loop or the Execute page: the ChatterBox simulator gives the
diagnostics the repairs are built on. What it caught that the simulator does not: a well drawn below its dead
volume, and `incubate`/`shake` with tips still mounted. The module and its tests are kept.

Plate volume limits come from the deck (`pipeline/labware_limits.py`): a well's capacity from its geometry (VENUS's
volume equations), the dead volume and how full a well may get from `config/precheck_policy.json` (defaults 30 µL and
90%; the Cos_96_PCR plates on the real deck: 30-260.7 µL of 289.7). Each plate is tracked on its own.

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
`config/Labware` is the library of the labware. Each entry has a part people write and a part the pipeline
writes:

- **Curated:**
  - `when`: which failures the entry covers (PLR exception, message text, device code, the step's action, and
    whether the scientist loads the labware).
  - `explanation` and `fixes`: what the model is told, and which IR edits are suggested.
  - `notes`: why the wording is what it is. Never sent to the model. For example, "lower `volume_ul`" was removed
    from `INSUFFICIENT_LIQUID` because the intent guard always rejects it, and qwen kept proposing it.
- **Observed** (updated after every `pipeline.py --heal` and demo run):
  - how often the entry came up;
  - how often the model's repair made the failure go away, and with which edit ops;
  - why the model's edits were rejected;
  - which protocols and models hit it;
  - the last few raw errors.

  It is never sent to the model, so the model sees the same prompts however much has been recorded.

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

Device steps need a heater-shaker, which the deck on the STARlet does not have yet, so a protocol that uses them cannot
be checked against this instrument. A protocol picks its deck with a top-level `"deck_config"` field; drafts name
`config/instrument/ahc_deck.lay`, which is also the default. Hold times are not waited out in simulation.
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

### When a failure repeats: escalation and knowledge proposals

If the same simulator failure comes back (same knowledge-base entry at the same step, `--escalate-after N`
times in a row, default 1), the next round is **escalated**:

1. **The prompt changes.** The model is told what was already tried for this failure and why it was rejected,
   is given the raw PyLabRobot error, and is asked to reason past the suggested fixes. The harness checks
   above still apply.
2. **The model proposes a knowledge-base change.** Its reply also carries a `knowledge_proposal`:
   - `add_fix` (a new fix for the entry);
   - `replace_fixes` (the current fixes are wrong);
   - `new_entry` (only for `UNRECOGNIZED` errors). The harness, not the model, writes the entry's `when`
     from the actual exception and step action; the model may add a `match_text` that must appear in the
     error message.

   The fix text is turned into a template: this run's labware ID and step number become `{labware}` and `{n}`,
   and braces that aren't known placeholders are kept as literal text.
3. **Only proposals whose fix worked are kept.** That means the escalated round's edits resolved the failure
   and the protocol then passed every stage. Those are stored under `proposals` in `knowledge/diagnostics.json`
   with status `pending`. Nothing reaches the entries the model sees until a person approves it.
4. **A person reviews it.** Use the run's result card, the Library page, or the command line:

   ```bash
   python -m pipeline.proposals list
   python -m pipeline.proposals approve <id>
   ```

   Approving merges the proposal into the entries: a new entry goes just above `UNRECOGNIZED`, and replaced
   fixes are kept in `notes`. The whole knowledge base is checked first, and a proposal that would break it is
   refused. Rejected proposals stay on record.

The CLI and the demo escalate by default (`--escalate-after 0` or the demo's checkbox turns it off). The


**Decision log.** Every repair decision in a recorded run is appended to `knowledge/decisions.jsonl`. Each line
holds:

- **Features**, known before the decision: entry, error class, step action, repeats so far, the entry's history,
  and earlier rejection kinds.
- **The action:** follow the knowledge base, or escalate.
- **The outcome:** resolved, by which edit ops, rejection kinds, run status, and whether a proposal was made.

This is the dataset for a future policy that decides when to trust the knowledge base.

---

## Setup

```bash
pip install -r requirements.txt
```

Drafting and repair use the Claude CLI. Install it, then run `claude` once to log in (the pipeline calls it
without a window, so it needs a saved login):

```bash
npm install -g @anthropic-ai/claude-code
claude
```

Set `CLAUDE_BIN` if the `claude` command is not on your PATH.

To repair with a local model instead (`--healer ollama`), install [Ollama](https://ollama.com) and pull one:

```bash
ollama pull qwen2.5-coder:7b
```

## Claude plugin

This repository is also a Claude Code plugin. Its `precheck` skill takes a protocol PDF or a description in a
conversation, runs the pipeline, shows the review, and revises on request.

```
/plugin install precheck --marketplace halimv/LLNL_Capstone
```

From a local checkout: `/plugin marketplace add /path/to/LLNL_Capstone`, then `/plugin install precheck`. The
skill runs `bin/precheck`, which is `pipeline.py` with this repository's Python (`PRECHECK_PYTHON`, else `.venv`,
else the conda env `PRECHECK_CONDA_ENV`, default `bioinfo`).

## Live demo

A local web page that runs the same flow as `pipeline.py` and shows it as it happens. Describe a protocol (or
attach its PDF, or pick a saved IR) and press **Check protocol**: the draft and its labware, each repair round
(the diagnostic, the model's reasoning and edits, whether the harness accepted them), then the design review.
From there, **Watch in 3D** replays the assay in PyLabRobot's 3D viewer (Stage 4), **Revise** sends a ticked
suggestion or a change in your own words back through the loop, and **Set up and run** opens the Execute page.
Explanations sit behind the small "i" buttons.

```bash
python demo/server.py            # then open http://127.0.0.1:8000  (--port to change)
```

Needs the Claude CLI (or Ollama with a model pulled, for repairs only). Passing protocols are saved to `healed/`,
per-round work files to `build/demo/<run id>/`; one run at a time.

The **Library** page (`/library`) shows the static data the pipeline relies on. It is read-only: edit the files
and reload.

- **Labware tab:** VENUS's labware library (the plates, tip racks and reagent containers Precheck can place) and
  the deck on the STARlet now (`config/instrument/ahc_deck.lay`), with the protocols drafted for it. Nothing hand-written.
- **Knowledge base tab:** every entry of `knowledge/diagnostics.json` in matching order, showing:
  - when it applies, in plain words;
  - the explanation and fixes sent to the model, with placeholders highlighted;
  - the notes for people;
  - what recorded runs observed.

  A filter and an "only entries seen in a recorded run" toggle narrow it down.

The **Execute** page (`/execute`) sets up and runs a protocol from `healed/` on the robot. See
[Running it on the STARlet](#running-it-on-the-starlet-execute-page).

## From a written protocol to the robot

One command takes a protocol PDF, a text file, or a pasted paragraph through the whole pipeline, live in the terminal:

```bash
python pipeline.py input.txt
python pipeline.py protocol.pdf
python pipeline.py "Serially dilute the culture 1:10 in sterile 0.9% saline ..."
```

To check the Claude step on its own first (nothing is healed or recorded):

```bash
python pipeline.py input.txt --draft-only --no-record
```

1. **Stage 0 (Claude CLI):** `claude -p` drafts the IR from the text, given the IR rules and the labware there is
   (what is on the deck now, and the sizes the library has). Its reasoning streams to the terminal; the plan shows
   as a running step count. Bench volumes (mL) are scaled to the plate with the ratios kept, and every such choice is
   listed under `assumptions`. Claude names labware by role, not by deck position:

   ```json
   "labware": {
     "tips": {"kind": "tip_rack", "tip_volume_ul": 300, "filter": true},
     "dilution_plate": {"kind": "plate", "wells": 96, "min_capacity_ul": 200},
     "saline": {"kind": "reservoir", "min_capacity_ul": 8000},
     "culture": {"kind": "tube", "min_capacity_ul": 5000},
     "waste": {"kind": "waste"}
   }
   ```

   The steps use these names. A reply that is not valid JSON, or whose steps use undeclared labware, goes back to
   Claude.
2. **Stage 0b (deck builder):** each need is matched to real labware, in order: labware on the STARlet's deck now
   (`config/instrument/ahc_deck.lay`); a free site on a carrier that is there; a carrier from the library on free
   rails. Labware checked against PyLabRobot comes first, then the smallest that is big enough. A need nothing fits
   goes back to Claude with the closest options ("no tube in the library fits at least 500000 uL. Closest: ..."),
   in the same CLI session, up to 4 replies in all. The draft is saved as `drafts/<name>_<time>.json` (Claude's full
   replies in `.claude.md`), and its deck in `decks/`:
   - `decks/<name>_<time>.json`: the deck config the rest of the pipeline uses (the draft's `deck_config`). Labware
     IDs are the IR names; labware on the deck the protocol does not use keeps its VENUS ID.
   - `decks/<name>_<time>.mapping.json`: per IR name, the VENUS type and file, the **barcode** mask VENUS expects on
     the labware and on its carrier (VENUS's `Barcode.Value`, `*` for any character: `235903************` on 300 uL
     filter tip racks, `SR11****` on the DWP plate carrier), the part number, the carrier, rails and position, and
     what the operator does (`on_deck`, `add_labware`, `add_carrier`). `operator_changes` lists the additions.
3. **Compile + simulate + self-healing (local Ollama model):** the same loop as `--heal`.
4. **Output in `healed/`:** the passing IR (`<name>.json`), the PLR Hamilton script (`<name>_plr.py`), and the
   heal log. The script runs on its own: `python healed/<name>_plr.py --backend chatterbox` (or `--backend star`,
   which asks for confirmation).

Needs the Claude CLI (see [Setup](#setup)). `--claude-model` picks Claude's model, `--deck` the deck the needs are
resolved against (default: the instrument's `.lay`), `--draft-only` stops after the draft, and `--no-record` keeps a rehearsal out of the knowledge
base. The self-healing options below (`--model`, `--max-rounds`, ...) apply here too.

### Reviewing and revising a healed protocol

Read the healed IR (its steps and Claude's `assumptions`), then describe what to change:

```bash
python pipeline.py --revise healed/<name>.json "use 3 replicate rows instead of 8, and mix with 60 uL"
```

The change can also be given as a text file. Claude gets the protocol text, the current healed plan and your request,
and is told to keep everything else as it is, including earlier repairs. Its revision then goes through the same
self-healing loop and checks as a first draft, and is saved as the next version: `healed/<name>_r2.json` (then `_r3`,
...). The earlier version is never overwritten. The terminal ends with a diff against the version you revised, and
every request is kept in the IR's `revisions` list, which the Execute page shows. Each revision starts a new Claude
conversation, so it works on any healed file.

The pipeline starts `claude` without the `CLAUDE*` environment variables a surrounding Claude session sets, so
running `pipeline.py` from inside Claude Code behaves the same as from a plain terminal.

### Running it on the STARlet (Execute page)

The deck is the one in the instrument library's VENUS layout (`config/instrument/ahc_deck.lay`). A protocol drafted
on it is compared with that layout. The **Execute** page (`python demo/server.py`, then `/execute`) walks through the setup:

- Pick a protocol from `healed/`. The server re-runs the compiler and simulator on the file; one that no longer passes cannot run.
- **Deck setup checklist**, built from the deck config and the passing IR: each carrier and its rails, each labware
  and its carrier position (Hamilton counts positions from the back, PLR sites from the front; both are given),
  full tip racks and which columns the run uses, the exact reagent volumes the simulation checked, an empty plate.
  The deck drawing is the deck on the STARlet now (`config/instrument/ahc_deck.lay`), not the protocol's deck
  config: labware the protocol uses is marked (under its IR name), what its deck adds (labware, carriers) is drawn
  dashed as still to place, and the current setup item is highlighted. **Open the deck on the STARlet in
  PyLabRobot's visualizer** shows the same real deck, nothing run.
- **Run:** ChatterBox rehearsal or the STARlet over USB (`STARBackend`), as a **tip check** (pick up and return one
  column per rack, no liquid) or the full protocol. The STARlet only starts once every checklist item is confirmed.
  Progress streams per IR step; **Abort** stops before the next step (tips stay mounted and are reported).

For a first hardware run: tip check, then the full protocol with water, then samples.

**Venus deck layout (.lay).** The page checks the protocol against the `.lay` in the instrument library
(`config/instrument/`, see [The static library](#the-static-library-the-real-system)); loading another `.lay` in the
sidebar checks against that one instead. `pipeline/venus_layout.py` reads Venus's binary layout and:

- turns it into a deck config, building each Venus type as `config/venus_labware.json` says: from PyLabRobot's factory,
  or from Venus's own definition in `config/Labware`. A type with neither is reported, never guessed;
- compares PyLabRobot's position of every carrier origin, rack and plate A1 with the `.lay`'s (0.5 mm tolerance).
  This catches a definition with other geometry, but not a tip rack of another size with the same footprint: the
  type map has to be right;
- checks that every labware the protocol uses sits on the `.lay` deck where the protocol's deck config puts it
  (carrier type and rails, position, labware type). While a loaded layout does not match, the STARlet run is refused.

A `.lay` is a deck by itself: to draft on another layout, put it in `config/instrument/` and pass it with `--deck`
(`python pipeline.py input.txt --deck config/instrument/<name>.lay`). Its plate limits follow from VENUS's geometry and
`config/precheck_policy.json`; nothing has to be typed in.

### Running through the Raspberry Pi

macOS never enumerates the STAR, so its USB cable goes to a Raspberry Pi. The page stays on your Mac and runs
stage 5 on the Pi over SSH: pick **ChatterBox rehearsal on the Pi** (checks the Pi's setup without the robot) or
**Hamilton STARlet via the Pi**. `config/remote.json` names the Pi (an `~/.ssh/config` alias such as `raspi-as`),
its folder and its Python.

- **On the Pi:** `~/llnl_capstone/.venv` has `pylabrobot[usb]==0.2.2`, the version this pipeline uses. AHC's
  own venv in `~/ahc` (PyLabRobot 1.0) is separate. The STAR needs no `sudo`: the Pi has a udev rule for it.
- **Sync code to the Pi** copies `pipeline/`, `config/` and `healed/`. A run is refused until the Pi's code
  matches this machine's.
- **One controller at a time.** A STARlet run holds an exclusive lock on `~/ahc/.star-bridge/lock`, the file
  the AHC bridge locks. The page shows who holds it and refuses the run while the bridge (or anything else)
  does. A ChatterBox rehearsal on the Pi does not need it.
- **Stopping.** Abort, a closed connection (the Mac sleeps, Wi-Fi drops) or a SIGHUP/SIGTERM on the Pi all
  stop the run before its next step; the step in progress finishes. Tips may stay mounted: check the instrument.

The Pi side is `python -m pipeline.stage5_executor serve` (JSON lines on stdin and stdout) and
`python -m pipeline.stage5_executor status` (lists USB devices, opens none); the SSH side is `pipeline/remote.py`.

The scripts in `healed/` also run without the page (`python healed/<name>_plr.py --backend star` asks you to type
`run` first), but then there is no checklist.

## The static library: the real system

Precheck reads static config files that describe the system as it really is. Each file has one job, and the
files that hold measured or exported facts are checked against each other when they load, so a stale file fails
at once instead of on the robot.

| File | What it is | Source | Used by |
|---|---|---|---|
| `config/precheck_policy.json` | Choices, not measurements: dead volume and how full a well may get | The lab (defaults carried over from the old stand-in) | `pipeline/labware_limits.py`, stage 1 |
| `config/Labware/` | Venus's labware library: carriers (`.tml`), racks and plates (`.rck`), well shapes (`.ctr`) | Copied from the lab's Venus PC | `pipeline/venus_labware.py` |
| `config/venus_labware.json` | Per Venus type: the PyLabRobot factory, the Venus file, and which geometry decks use (`build`) | Written; checked against `config/Labware` | `.lay` import, deck building |
| `config/ML_Starlet.tpl` | Venus's deck template: the deck's fixed parts (waste block, tip waste, 96 head slide waste) | Copied from Venus | `pipeline/instrument.py` |
| `config/instrument/starlet_F553.json` | The instrument: serial, channels, 96 head and where it ejects, tip waste | Written; checked against the three files below | `pipeline/instrument.py`, deck building |
| `config/instrument/starlet_F553_configuration.json` | What the firmware reports (read with reads only) | AHC's `star_readonly_probe.py` | Instrument check |
| `config/instrument/ahc_deck.lay` | What is on the deck now: **the deck** protocols are drafted, checked and run on | Exported from Venus | `pipeline/deck.py` (stages 0-5), instrument check, Execute page, AHC export |
| `config/ahc_starlet.json` | The carriers and labware AHC accepts | Copied from AHC's `starlet.md` | `pipeline/ahc_export.py` |

**Geometry: Venus is the reference.** Venus's definitions are what the lab's runs on this STARlet use. PyLabRobot
ships its own, written by hand. `pipeline/venus_labware.check_map` compares them whenever `venus_labware.json`
loads: a type stays `"build": "plr"` only while PyLabRobot matches Venus within 0.15 mm. Today:

- `TIP_CAR_480_A00`, `PLT_CAR_L5AC_A00` and the 300 uL filter tip rack (`STF_L`) match, so decks use PyLabRobot's;
- `PLT_CAR_L5_DWP`'s sites are 0.8-0.9 mm further front and 0.33 mm higher in PyLabRobot, so decks build it from Venus;
- `Cos_96_PCR` has no PyLabRobot definition, so it is built from Venus's `.rck` and `.ctr` (127 x 86 x 22.5 mm,
  20.5 mm wells, 289.7 uL by Venus's volume equations).

Tip racks always stay PyLabRobot's: a `.rck` describes the rack, not the tip PyLabRobot needs to pipette. Built
this way, the deck in `ahc_deck.lay` matches the file to 0.0 mm at every carrier, rack and plate.

**The instrument.** A deck config's `"instrument"` field makes `build_deck` apply the instrument's facts where
PyLabRobot's defaults differ. Today that is the 96 head's initialization: PyLabRobot 0.2.2 already sends it to Venus's
x and y over the slide waste, but lowers it to 216.4 mm; Venus stops at 229.0. The deck's 96 waste is raised, so
PyLabRobot's own setup sends Venus's command (`C0EI xs00420 xd1 yh1203`, at 229.0 mm).

**Keeping it current.** When the deck changes, export a new `.lay` from Venus into `config/instrument/`. When labware
is added, copy its Venus files into `config/Labware` and add the type to `config/venus_labware.json`; the check says
whether PyLabRobot's factory can be used. The Pi gets the library with **Sync code to the Pi**, without its images and
3D models (about 140 MB that runs do not need).

**Handing the deck to AHC.** `python -m pipeline.ahc_export` writes a deck as an AHC layout
(`<task>/.ahc/layouts/<name>.yaml`): `--protocol healed/<name>.json` (the deck Precheck simulated, with its starting
volumes) or `--instrument` (the deck the `.lay` says is there). It leaves out what AHC does not accept, never renaming
it to a near match, and warns where AHC will build an item from PyLabRobot's geometry while Precheck uses Venus's.

## Working with an existing IR

Pass a protocol IR file with `--protocol` instead of protocol text. Stage 0 is skipped.

Compile and simulate once and print the diagnostic on failure:

```bash
python pipeline.py --protocol healed/serial_1_10_dilution_of_culture_in_0_9_saline_20261112-172546.json
```

Repair a failing protocol with the local model:

```bash
python pipeline.py --protocol healed/serial_1_10_dilution_of_culture_in_0_9_saline_20261112-172546.json --heal
```

Watch the passing (or repaired) protocol in PyLabRobot's visualizer (Stage 4). This opens a browser tab at
`http://127.0.0.1:1337`, replays every step, and keeps the page open until you press Ctrl+C:

```bash
python pipeline.py --protocol healed/serial_1_10_dilution_of_culture_in_0_9_saline_20261112-172546.json --heal --visualize
```

Options: `--model` (any Ollama model, default `qwen2.5-coder:7b`), `--max-rounds` (default 8),
`--feedback raw` (send the model only the raw PLR exception instead of the lab-concept diagnostic, for comparison),
`--output` (default `build/`, git-ignored), `--escalate-after` (see above), `--no-record`.

Each healing run writes every round's IR (`round_N.json`) and compiled code (`round_N_plr.py`) and `heal_log.json`
to `build/<protocol>/`, and on success the passing IR, its standalone PyLabRobot script and the heal log to
`healed/`.

## Tests

```bash
python -m pytest tests/ -q
```

- `tests/test_precheck_flow.py` (20 tests): the protocol flow from text to a checked protocol.
- `tests/test_deck_builder.py` (13 tests): the catalog read from VENUS's library, a serial dilution's needs resolved on
  the STARlet's deck (with barcodes), unresolved needs with the closest options, the built deck through compile and
  simulate, the drafter's loop back to Claude, the Execute page's real-deck drawing, and decks serializing for PyLabRobot.
- `tests/test_venus_layout.py` (11 tests): reads a real Venus 6.4 `.lay` (`tests/fixtures/venus/ahc_deck.lay`), places
  its carriers and labware, checks positions and heights against the file, and compares it with a protocol's deck.
- `tests/test_static_library.py` (19 tests): VENUS's labware library, the instrument's facts against their sources, the
  96 head initialized with VENUS's exact command, the layout handed to AHC, and the real deck as ground truth.
- `tests/test_diagnostics_kb.py` (13 tests): the diagnostics knowledge base loads, no entry is hidden behind an earlier
  one, and typos in a hand edit are reported when it loads.
- `tests/test_proposals.py` (3 tests) and `tests/test_partial_edits.py` (1 test): the knowledge-base proposal rules and
  partial acceptance of a model reply. Most of their coverage was on the removed stand-in decks and is not rebuilt yet.
- `tests/test_remote.py` (4 tests): the Pi runner, the exclusive STARlet lock and what blocks a run on the Pi.
- `tests/test_text_to_execution.py` (6 tests): reading protocol text, pulling the IR out of Claude's reply, catching
  unknown labware in a draft, and revisions.
- `tests/test_ground_truth_ui.py` (4 tests): the Library, deck and API serve only VENUS ground truth.

The live model loop, the real Claude CLI call and the STARlet itself have no unit tests; the notebook runs the
model loop end to end.

---

## Repository layout

```text
.
├── pipeline.py                   # Entry point: protocol text/PDF → healed/, or --protocol for an existing IR
├── requirements.txt
├── drafts/                       # Claude's draft IRs and full replies (created by the first run)
├── healed/                       # Passing IRs, their PLR scripts and heal logs (created by the first healed run)
├── pipeline/
│   ├── stage0_drafter.py         # Protocol PDF/text -> IR with the Claude CLI
│   ├── stage1_verifier.py        # Safety rules on the IR
│   ├── stage2_compiler.py        # IR -> PyLabRobot code (deterministic)
│   ├── deck.py                   # Builds the PLR deck from a VENUS .lay
│   ├── deck_builder.py           # Stage 0b: labware needs -> real labware and positions; deck + mapping
│   ├── labware_limits.py         # Plate volume limits: VENUS geometry + config/precheck_policy.json
│   ├── instrument.py             # The instrument's facts (config/instrument/), checked against their sources
│   ├── venus_layout.py           # Reads VENUS .lay/.tpl files; compares a layout with a deck
│   ├── venus_labware.py          # Reads VENUS's labware library; builds carriers and plates from it
│   ├── ahc_export.py             # Writes a deck as an AHC layout
│   ├── remote.py                 # Runs stage 5 on the Pi over SSH
│   ├── stage3_simulator.py       # ChatterBox dry run + error interceptor
│   ├── diagnostics.py            # PLR exception -> lab-concept diagnostic (looked up in knowledge/)
│   ├── proposals.py              # Knowledge-base proposals from escalated rounds; approve / reject
│   ├── self_heal.py              # Repair loop, Ollama backend, edit checks, ir_diff
│   ├── stage4_visualizer.py      # Replay in PyLabRobot's browser visualizer
│   ├── setup_guide.py            # Deck setup checklist for a passing IR
│   └── stage5_executor.py        # Runs a passing IR on the STARlet or ChatterBox
├── config/
│   ├── instrument/               # The STARlet: facts (starlet_F553.json), firmware report, the .lay of its deck now
│   ├── Labware/                  # VENUS's labware library (carriers, racks, plates, well shapes)
│   ├── ML_Starlet.tpl            # VENUS's deck template: the deck's fixed parts
│   ├── venus_labware.json        # VENUS type -> PyLabRobot factory, and which geometry decks use
│   ├── precheck_policy.json      # Dead volume and fill fraction (choices, not measurements)
│   ├── ahc_starlet.json          # The carriers and labware AHC accepts
│   ├── remote.json               # The Pi the STARlet is plugged into
├── knowledge/
│   ├── diagnostics.json          # Diagnostics knowledge base: what each simulator error means, how to fix it,
│                                 #   what past self-healing runs learned about it, and proposals awaiting review
│   └── decisions.jsonl           # One line per repair decision (created by the first recorded run)
├── demo/
│   ├── server.py                 # Live self-healing demo (Flask + Server-Sent Events)
│   └── static/                   # Pages: check (index/app.js), library, execute; shared common.js, style.css
├── notebooks/
│   └── pipeline_walkthrough.ipynb
├── tests/                       # See the list above (python -m pytest tests -q)
├── docs/
│   └── self_healing_run_v1.md    # Report on the first successful repair run
└── archive/                      # Earlier code kept for reference; not used by the pipeline
```

## Target hardware

- **Liquid handler:** Hamilton STARlet, 8-channel head
- **Software:** PyLabRobot 0.2.2 (`LiquidHandlerChatterboxBackend` for simulation, `STARBackend` over USB for
  the robot)
- **Plate:** Corning 3595, 96-well flat bottom (PLR `cor_96_wellplate_360uL_Fb`)
- **Tips:** Hamilton 200 µL filtered tips in the spec; simulated with PLR's closest rack,
  `hamilton_96_tiprack_300uL_filter`

---

## Status and known gaps

**Working:** the deck builder, compiler and simulator, lab-concept diagnostics, and the self-healing loop with a local 7B model. One documented
successful repair of `serial_dilution_v1` in 3 rounds ([report](docs/self_healing_run_v1.md)). The text → IR →
`healed/` pipeline, the deck checklist and Stage 5 run end to end on ChatterBox.

**Not yet:**
- **Not yet tested for real:** Stage 5 on the STARlet, and `--revise` with the real Claude CLI (tested with a
  stand-in).
- **No liquid source on today's real deck.** `ahc_deck.lay` holds two tip racks and two PCR plates, no trough or tube,
  and the IR can declare starting liquid only in containers, not in plate wells. Until one changes, a protocol on the
  real deck has nothing to aspirate from.
- **Device steps on the robot:** `incubate` and `shake` are refused on the STARlet. The heater-shaker is not wired
  up yet.
- Repair reliability numbers. One successful run is shown; repeated runs and a raw vs translated feedback
  comparison (`--feedback raw`) are next.
- Unit tests for the live model loop (Stages 1–3 and the edit checks are covered on v1 by `tests/`).
- Labware changes in repairs. The intent guard rejects them (e.g. moving a reagent to a trough), even when they
  would be a valid fix.
- A `mix` action in the IR. Mixing is written as aspirate/dispense pairs, and the verifier needs a well mixed
  before it is aspirated from, not after a dispense into it with the same tips.
- Moving plates (gripper) and returning tips to the rack for reuse. Without tip return, washing with the
  8-channel head needs a fresh tip column per column per wash, so wash-heavy assays run out of tips quickly.
- Spill risk from shaking full wells, and plate reading. Neither is checked.
