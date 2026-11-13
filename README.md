# PreCheck

PreCheck turns a liquid-handling protocol (a PDF, a text file, or a description in words) into a protocol that has
been drafted, checked and repaired against the lab's own Hamilton STARlet: its deck, its labware from the VENUS library,
and its firmware configuration. Nothing is sent to a robot. The output is a protocol a scientist reviews, a standalone
PyLabRobot script, an AHC layout, and a summary that lists what needs a person's review.

PreCheck ships as a Claude Code plugin. It also runs from the command line.

## Contents

- [Quick start](#quick-start)
- [How a run works](#how-a-run-works)
- [What a run produces](#what-a-run-produces)
- [The check: simulator and repair](#the-check-simulator-and-repair)
- [Ground truth](#ground-truth)
- [The plugin](#the-plugin)
- [Command line](#command-line)
- [Demo pages](#demo-pages)
- [Hand-off to AHC and the robot](#hand-off-to-ahc-and-the-robot)
- [Tests](#tests)
- [Repository layout](#repository-layout)
- [Status and known gaps](#status-and-known-gaps)

## Quick start

PreCheck needs three things on the machine: [uv](https://docs.astral.sh/uv/) (it installs PreCheck's Python packages
from `plugin/pyproject.toml`), the Claude Code CLI (`npm install -g @anthropic-ai/claude-code`, then `claude` once to
log in, for drafting and repairs), and the VENUS labware library copied into `plugin/config/Labware/` (it is Hamilton's
software content, so it is not in the repository). Then, in the folder where you want the results:

```bash
precheck --setup                       # checks the requirements and makes this folder's working folders
precheck "protocol.txt" --yes          # or a PDF, or the protocol text in quotes
```

`precheck` is the launcher in `plugin/bin/precheck`. From Claude Code, the plugin's skill runs the same commands.

## How a run works

1. **Draft.** Claude (through the Claude CLI) writes the protocol as a structured plan: the steps, the volumes, the
   starting liquids, and the labware it needs by role ("diluent", "culture", "tips"). Every assumption it makes is
   recorded.
2. **Deck.** Each labware need is matched to a real item in the VENUS library and placed on the deck that is on the
   STARlet, on a free site. What nothing fits goes back to Claude. The placement is written as a deck config and a
   mapping, and any carrier the operator must add is listed.
3. **Check.** The plan is compiled to PyLabRobot code, and run on a simulated STARlet configured from the instrument's
   firmware report (`plugin/config/instrument/starlet_F553_configuration.json`): its channels, 96 head, iSWAP, deck and
   tip waste. Tips, volumes, piston travel, channel spacing and containers are checked by the device model, so what the
   real instrument would refuse is refused here.
4. **Repair.** A failing plan goes to a model with the diagnostic: Claude Haiku first, then Sonnet and then Opus when
   the rounds run out. Each model gets up to five rounds, starting from where the last one stopped. A repair may
   restructure the steps, but every plate well must end with the same volume and reagents as the plan (see
   [the repair guard](#the-repair-guard)).
5. **Review.** A protocol that passes gets its design as numbers (labware chosen, what each well holds and at what
   dilution, dead-volume and fill limits, the tips used) and a list of suggestions. Suggestions are improvements, not
   errors.
6. **Hand-off.** A passing protocol is written out with its standalone script and an AHC layout. A protocol that does
   not pass writes nothing to `healed/`.

## What a run produces

Everything a run writes goes into the **working folder**: the folder you run `precheck` from (or `PRECHECK_WORKDIR`).
`precheck --workdir` prints it.

| Where | What |
|---|---|
| `healed/<name>.json` | The passing protocol (the IR) |
| `healed/<name>_plr.py` | The same protocol as a standalone PyLabRobot script |
| `healed/<name>.ahc_layout.yaml` | The deck as an AHC layout |
| `healed/<name>_summary.md` | **Summary**: the result, the models and rounds, the wells, the reagents, and the list of things that need a person's review |
| `healed/<name>_report.json` | Everything above as data, including `needs_review` |
| `healed/<name>_heal_log.json` | Every round: the failure, the model's edits, and the verdict |
| `drafts/`, `decks/` | What the drafter and the deck builder produced, with Claude's replies |
| `build/<name>/summary.md` | **Summary of a protocol that did not pass**. Nothing is written to `healed/` |
| `knowledge/diagnostics.json` | The diagnostics knowledge base, copied from the plugin on first use and added to by runs |

The review list has two severities:

- **must**: the protocol cannot run as it stands. An operator carrier to place, an item AHC cannot load, liquid too
  shallow to draw from reliably, or a protocol that did not pass.
- **check**: a choice made for the scientist to confirm. A drafting assumption, a repair that changed the steps, labware
  AHC substitutes for VENUS's, or a well flagged against its limits.

## The check: simulator and repair

**The simulator** is PyLabRobot's STAR device (`pylabrobot.hamilton.star`) configured from the instrument's firmware
report. It is the same model AHC runs. Two rules are set by hand, from measurements on the instrument:

- **Channel planning.** Channels are planned at the instrument's minimum pitch (9 mm), not the 18 mm body width the
  firmware reports, since 9 mm plate columns work on this instrument. AHC does the same.
- **Air in the tip.** A dispense also pushes out the transport air drawn with it. The device's default for this tip
  is 5 µL. This is PyLabRobot's model, not yet measured on this instrument.

**Diagnostics.** A failure is explained in lab terms from the knowledge base (`knowledge/diagnostics.json`): what went
wrong, and which fixes a repair may try. Entries are matched top to bottom. Each entry is written so a scientist can
read and change it.

**The repair guard.** A repair is accepted only if it leaves the experiment the same. The guard compares what ends up
in each plate well (its volume and each reagent's volume, traced through every transfer) and each heated or shaken
hold's time. Splitting, merging or reordering transfers is allowed, and so is air drawn with the liquid, because air
never reaches a well. A change to a well, such as a dilution cut from 90 to 80 µL, is refused. The trace follows
liquid in proportion as it moves, so the numbers are an approximation of mixing.

**Escalation.** `--max-rounds` (default 5) is per model. Repairs made by one model are kept when the next takes over.

## Ground truth

The files in `plugin/config/` are the lab's ground truth. Read them, don't edit them in a run.

| File | What it is |
|---|---|
| `config/Labware/` | VENUS's labware library: carriers (`.tml`), racks and plates (`.rck`), well shapes (`.ctr`). Not in the repository |
| `config/venus_labware.json` | Per VENUS type: the PyLabRobot factory, the VENUS file, and whether PyLabRobot's or VENUS's geometry is used |
| `config/instrument/ahc_deck.lay` | The deck on the STARlet now (a VENUS layout). Export a new one when the deck changes |
| `config/instrument/starlet_F553.json` | The instrument's facts, checked against its firmware report and VENUS's deck template |
| `config/instrument/starlet_F553_configuration.json` | The firmware report the simulator answers as this instrument |
| `config/ML_Starlet.tpl` | VENUS's deck template: the fixed parts (waste block, tip waste, 96 head slide waste) |
| `config/precheck_policy.json` | The dead volume and fill limit for plates. These are choices the lab sets |
| `config/ahc_starlet.json` | The carriers and labware AHC accepts |
| `config/remote.json` | The Raspberry Pi the STARlet is plugged into, for remote runs |

Other ground truth can be used with `--instrument`, `--labware` and `--deck`.

## The plugin

The plugin is the `plugin/` folder. Its manifest is `plugin/.claude-plugin/plugin.json`, and the marketplace at the
repository root points at it.

```bash
claude plugin marketplace add /path/to/PreCheck
claude plugin install precheck@precheck
```

The plugin contains the skill (`plugin/skills/precheck/SKILL.md`), which Claude follows to set up a folder, check a
protocol, summarise it, test it on AHC's simulator, revise it and hand it off. It runs from the plugin folder and
writes into the folder Claude Code was opened in. Installing the plugin does not create a working folder, since a
working folder is a task folder; `precheck --setup` (the skill runs it first) does.

## Command line

Run from the working folder:

```bash
precheck --setup                                   # requirements and this folder's working folders
precheck protocol.txt --yes                        # draft, check and repair a protocol, without asking
precheck protocol.txt                              # the same, then review and watch in the 3D viewer
precheck --protocol healed/name.json --heal        # repair an existing protocol
precheck --protocol healed/name.json --visualize   # watch the passing protocol in PyLabRobot's 3D viewer
precheck --revise healed/name.json "use 3 rows"    # a change in words, checked and saved as name_r2
```

Useful options: `--model <name>` runs one model only (the default is the Haiku, Sonnet, Opus ladder); `--healer
ollama` uses a local model; `--max-rounds N`; `--instrument`, `--labware` and `--deck` for other ground truth;
`--no-record` keeps a run out of the knowledge base; `--draft-only` stops after the draft.

Full options: `precheck --help`.

## Demo pages

```bash
python demo/server.py          # then open http://127.0.0.1:8000
```

- **Check** (`/`): start a run from text, a file or a saved protocol. It streams the repair rounds, the review and the
  summary, and it can replay the passing protocol in the 3D viewer.
- **Library** (`/library`): VENUS's labware library and the deck on the STARlet, and the protocols drafted for it.
- **Execute** (`/execute`): sets up a passing protocol on the STARlet. It shows the deck checklist and the layout
  comparison, has a *Replay in 3D* button, and runs the protocol on ChatterBox or the STARlet, once every setup item is
  ticked.

The demo is a development tool. It reads the code from `plugin/` and writes to the folder it is started in.

## Hand-off to AHC and the robot

- **AHC (optional):** the AHC layout is copied into the task folder's `.ahc/layouts/`. AHC's simulator then checks the
  deck and runs the plan. The skill does this in simulate mode. A real robot is run only on site, under AHC's own
  checks.
- **PreCheck alone:** `python healed/<name>_plr.py --backend chatterbox` rehearses a protocol, and the Execute page
  runs it on the STARlet. The script for the STARlet (`--backend star`) asks you to type `run` first.
- **Remote:** `config/remote.json` names a Raspberry Pi the STARlet's USB cable is plugged into. The Execute page can
  run there, and a lock file keeps two runs from driving the instrument at once.

## Tests

```bash
uv run --project plugin --group dev pytest tests -q
```

The tests run from the repository: `tests/conftest.py` puts `plugin/` on the path, and the working folder is the
repository. They use the fixtures in `tests/fixtures/` and the VENUS library in `plugin/config/Labware/`, so the
library must be present for the labware tests.

## Repository layout

```
PreCheck/
├── plugin/                        # the plugin: what a user installs
│   ├── .claude-plugin/plugin.json # manifest
│   ├── bin/precheck               # launcher: runs pipeline.py through uv, in the working folder
│   ├── skills/precheck/SKILL.md   # the skill Claude follows
│   ├── pipeline.py                # command line entry point
│   ├── pipeline/                  # the code (see below)
│   ├── config/                    # ground truth (see Ground truth)
│   ├── knowledge/                 # diagnostics knowledge base (seed) and decisions log
│   ├── pyproject.toml, uv.lock    # pinned dependencies (PyLabRobot at the commit AHC uses)
│   └── requirements.txt           # the same list for pip
├── .claude-plugin/marketplace.json  # marketplace: points at plugin/
├── demo/                          # development demo: server.py and its pages
├── tests/                         # pytest suite; fixtures in tests/fixtures/
├── docs/                          # design notes and the first run report
├── notebooks/                     # walkthrough notebook
└── files/input.txt                # an example protocol text
```

Code in `plugin/pipeline/`:

| Module | Role |
|---|---|
| `paths.py` | The plugin folder (read) and the working folder (write) |
| `stage0_drafter.py`, `deck_builder.py`, `deck.py` | Draft, placement, the deck |
| `stage2_compiler.py` | Plan to PyLabRobot code, and the standalone script |
| `stage3_simulator.py`, `pipetting.py`, `instrument.py` | The simulator on the STAR device |
| `stage4_visualizer.py` | The 3D replay |
| `self_heal.py`, `diagnostics.py`, `proposals.py` | Repair, diagnostics, knowledge |
| `design_review.py`, `summary.py`, `flow.py` | Review, summaries, writing a passing protocol |
| `workfolder.py` | `--setup` |
| `ahc_export.py`, `venus_layout.py`, `venus_labware.py`, `library_view.py` | AHC layout, VENUS import, the library |
| `stage5_executor.py`, `remote.py`, `setup_guide.py` | Execution on the STARlet and the Pi |

## Status and known gaps

**Working:** the draft, the deck placement, the STAR-model simulator and 3D replay, the repair loop with the model
ladder and the repair guard, the review and summaries, the plugin install and `--setup`, and the AHC simulator run of a
passing protocol.

**Not yet:**
- The model ladder has not been run end to end. The mechanics (hand-off between models, nothing written on failure) are
  tested with zero rounds only.
- Only the simulator is on the new STAR device. The robot path (`--backend star`, the Execute page on the robot and
  the Pi) still uses PyLabRobot's legacy driver and has not been run on the instrument since the move.
- The 5 µL transport air is PyLabRobot's default, not measured on this instrument.
- The trace behind the repair guard approximates mixing in proportion.
- Heater-shaker steps (`incubate`, `shake`) are simulated but there is no heater-shaker on the deck.
- Mixing is written as aspirate and dispense pairs.
- The VENUS library's licence needs checking before the plugin is shared.
- Claude's draft is checked by the simulator, but a draft that passes is not thereby right: the scientist reviews the
  assumptions and the list of things to check.
