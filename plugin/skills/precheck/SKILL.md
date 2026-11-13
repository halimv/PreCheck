---
name: precheck
description: Turn a liquid-handling protocol (a PDF, a text file, or a description in words) into a protocol that has been checked and repaired against the lab's Hamilton STARlet, then review it with the scientist and test it in AHC's simulator. Use when someone wants to draft, check, heal, simulate or revise a protocol for the STARlet, asks whether a protocol will run on the robot, or wants a protocol prepared before handing it to AHC.
---

# PreCheck

PreCheck takes a protocol and returns one that passes on a model of the lab's own instrument. It drafts the steps,
chooses real labware from the lab's VENUS library, places it on the deck that is on the STARlet, runs the result on
PyLabRobot's STAR model configured from the instrument's firmware file, and repairs what fails. Nothing is sent to a
robot. A protocol that does not pass is never written as ready.

The command is `precheck` (the launcher in this plugin's `bin/`; `precheck --root` prints the PreCheck folder that
every relative path in its output is inside).

## 0. Set up the folder (once per task folder)

If the task folder has no `healed/` folder yet, run this first:

```bash
precheck --setup
```

It checks what PreCheck needs (the VENUS labware library, the Claude CLI, uv, and that the folder is writable) and
creates the folders a run writes into. If an item is marked missing, tell the scientist what it says and stop.

## 1. Check the protocol

```bash
precheck "<path to a PDF or text file, or the protocol text itself>" --yes
```

- Takes several minutes (drafting, then up to 5 repair rounds with Claude Haiku, then Sonnet and Opus if Haiku runs
  out). Give the command a 20 minute timeout.
- Pass the scientist's text as they wrote it. Do not rewrite, summarise or add steps to it first: the drafter
  records every assumption it has to make, and the scientist reviews those.
- Ground truth defaults to the lab's files in `config/`. Only when the scientist names others:
  `--instrument <file>`, `--labware <VENUS Labware folder>`, `--deck <.lay>`.
- `--model <name>` runs one model only; `--healer ollama` uses a local model.

The output ends with the result. There are two outcomes:

- **PASSED: ready for AHC.** The last line names the report: `Report (review, suggestions, files): <path>_report.json`.
  Read that file; it holds everything in step 2.
- **NOT READY: did not pass the simulator.** Nothing was written to `healed/`. Show the scientist the summary
  (which models were tried, how many rounds, the final failure) and ask what to change. Never edit a protocol file
  by hand to make it pass, and never present a protocol that did not pass as ready.

## 2. Show the scientist what to review

From the report, briefly and in this order:

1. **Result**: passed, the repair rounds and models used, how many steps, and `simulated_on`.
2. **Assumptions** (`review.assumptions`): every one. These are choices the drafter made that the text did not settle
   (volumes, number of dilutions, which container).
3. **Design parameters**: a table from `review.wells` (plate, column, final volume, contents with each dilution) and
   one from `review.reagents` (load, drawn, left over, capacity). Mention any `flags`.
4. **Labware and deck** (`review.labware`): what was chosen and where it sits, and anything the operator has to place
   before the run.
5. **Suggestions** (`suggestions`): numbered, title then detail. They are improvements, not errors.
6. **AHC** (`ahc`): whether the whole deck is on the AHC layout (`not_on_layout` empty), and where AHC's labware model
   differs from VENUS (`differs_from_venus`).

To let them watch the assay in PyLabRobot's 3D viewer, run it in the background and give them the address it prints:

```bash
precheck --protocol <files.ir> --visualize
```

## 3. Test it in AHC's simulator

Before the scientist decides, run the accepted protocol on AHC in simulate mode, using the AHC `lab-hardware`
skill. Simulate mode only: never a real robot in this step.

1. Copy `<files.ahc_layout>` into the task folder's `.ahc/layouts/` (the PreCheck folder has its own `.ahc/`).
2. Set up a simulated STARlet (`configure_devices`, simulation), and have the scientist confirm the configuration.
3. Load the layout, run the deck check, then the protocol's steps from `<files.ir>` as AHC calls, one plate column at
   a time, verifying each stage the lab-hardware skill names.
4. Report what AHC accepted and what it refused, with AHC's own messages. A refusal is a finding: say so, and do not
   edit the protocol to get past it. Send the refusal back to the scientist as a change to make (step 4).

## 4. Ask for improvements, and revise

Ask whether they want anything changed. For a change in their words, or a suggestion they pick (use its `request`
text):

```bash
precheck --revise <files.ir> "<the change>" --yes
```

This saves the next version (`_r2`, `_r3`, ...) after the same check and repair, with its own report. Show what
changed, and repeat from step 2 (and step 3 when the change is to be tested) until the scientist accepts it.

## 5. Hand off

Tell the scientist the two ways to run the accepted protocol, and let them choose:

- **PreCheck alone**: `python <files.script> --backend chatterbox` rehearses it; `python demo/server.py` in the
  PreCheck folder, then the Execute page, walks through the deck checklist and runs it on the STARlet.
- **With AHC** (optional: a supervised run with error recovery and an on-site deck check): copy `<files.ahc_layout>`
  into the task folder's `.ahc/layouts/` and follow the AHC `lab-hardware` skill, using the steps in `<files.ir>` as
  the plan.

Do not start a run on a real instrument yourself. That is the scientist's decision, made on site.
