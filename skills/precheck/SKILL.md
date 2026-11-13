---
name: precheck
description: Turn a liquid-handling protocol (a PDF, a text file, or a description in words) into a protocol that has been checked and repaired against the lab's Hamilton STARlet, then review it with the scientist. Use when someone wants to draft, check, heal, simulate or revise a protocol for the STARlet, asks whether a protocol will run on the robot, or wants a protocol prepared before handing it to AHC.
---

# PreCheck

PreCheck takes a protocol and returns one that passes on a model of the lab's own instrument. It drafts the
steps, chooses real labware from the lab's VENUS library, places it on the deck that is on the STARlet, runs
the result on PyLabRobot's STAR model configured from the instrument's firmware file, and repairs what fails
(Claude Haiku by default, at most 5 rounds). Nothing is sent to a robot.

Run it with `precheck` (on PATH while this plugin is enabled; otherwise `${CLAUDE_PLUGIN_ROOT}/bin/precheck`).
`precheck --root` prints the PreCheck folder: every path PreCheck reports that is not absolute is inside it.

## 1. Check the protocol

```bash
precheck "<path to a PDF or text file, or the protocol text itself>" --yes
```

- Takes 1 to 5 minutes: give the command a 10 minute timeout.
- Pass the scientist's text as they wrote it. Do not rewrite, summarise or add steps to it first: the drafter
  records every assumption it has to make, and the scientist reviews those.
- Ground truth defaults to the lab's files in `config/`. Only when the scientist names others:
  `--instrument <file>`, `--labware <VENUS Labware folder>`, `--deck <.lay>`.
- A local repair model instead of Claude: `--healer ollama`. Another Claude model: `--model claude-sonnet-5-5`.

The last line of output names the report: `Report (review, suggestions, files): <path>_report.json`. Read that
file; it holds everything below.

If the command exits with `Not ready`, the protocol still fails after 5 repairs. Show the last failure from the
output, and ask the scientist what to change. Never edit the protocol JSON by hand to make it pass, and never
present a protocol that did not pass as ready.

## 2. Show the scientist what to review

From the report, briefly and in this order:

1. **Result**: passed, how many repairs, how many steps, what it was simulated on (`simulated_on`). If
   `reference_deck` is true, say it can be rehearsed but not run.
2. **Assumptions** (`review.assumptions`): every one. These are choices the drafter made that the text did not
   settle (volumes, number of dilutions, which container).
3. **Design parameters**: a table from `review.wells` (plate, column, final volume, contents with each
   dilution) and one from `review.reagents` (load, drawn, left over, capacity). Mention any `flags`.
4. **Labware and deck** (`review.labware`): what was chosen and where it sits, and anything the operator has to
   place before the run.
5. **Suggestions** (`suggestions`): numbered, title then detail. They are improvements, not errors.
6. **AHC** (`ahc`): whether the whole deck is on the AHC layout (`not_on_layout` empty), and where AHC's labware
   model differs from VENUS (`differs_from_venus`).

To let them watch the assay, start the 3D viewer in the background and give them the address it prints:

```bash
precheck --protocol <files.ir> --visualize
```

## 3. Ask for improvements, and revise

Ask whether they want anything changed. For a change in their words, or a suggestion they pick (use its
`request` text):

```bash
precheck --revise <files.ir> "<the change>" --yes
```

This saves the next version (`_r2`, `_r3`, ...) after the same check and repair, with its own report. Show what
changed and repeat from step 2 until they accept it.

## 4. Hand off

Tell the scientist the two ways to run the accepted protocol, and let them choose:

- **PreCheck alone**: `python <files.script> --backend chatterbox` rehearses it; `python demo/server.py` in the
  PreCheck folder, then the Execute page, walks through the deck checklist and runs it on the STARlet.
- **With AHC** (optional: a supervised run with error recovery and an on-site deck check): copy
  `<files.ahc_layout>` into the task folder's `.ahc/layouts/` and follow the AHC `lab-hardware` skill, using the
  steps in `<files.ir>` as the plan.

Do not start a run on a real instrument yourself. That is the scientist's decision, made on site.
