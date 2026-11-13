# PreCheck: modular design plan

Notes for designing the PreCheck Claude plugin/skill. Status as of this write-up: the PyLabRobot upgrade is done locally; the modular refactor has not started.

## Current state

- **PyLabRobot.** PreCheck now pins PyLabRobot 1.0.0b1 at commit `6262d633394cecb76673f31c79f10cb0ab2fa001`, the build AHC pins. All 120 tests pass on it. Not yet committed.
- **Raspberry Pi has two environments, and they disagree.**
  - `~/ahc/.venv`: PyLabRobot 1.0.0b1 (the AHC bridge; this is what ran the recent AHC test).
  - `~/llnl_capstone/.venv`: PyLabRobot 0.2.2 (what PreCheck's `pi:star` path uses via `pipeline/remote.py`). It must be upgraded to the same commit before any PreCheck run through the Pi.
- **Tip rack height is not verified.** In PyLabRobot 1.0.0b1 a 300 uL filter rack seats at Z 108.95 inside a carrier site whose surface is at Z 114.95, and its A1 well sits at 116.45. VENUS's carrier file (`config/Labware/ML_STAR/TIP_CAR_480_A00.tml`) gives the site at 114.95, and the test compares only site positions. Nothing in the config files states how VENUS seats the rack or where it picks up tips, so the 6 mm seating offset has not been checked against VENUS.

## Goal

PreCheck should be modular, and both simulation and real execution should take their geometry from the ground-truth files in `config/`: the VENUS labware library in `config/Labware` and the system deck in `config/instrument`. Nothing about the deck should be typed by hand for a real run.

## Proposed structure

1. **Ground-truth loader** (one module). Reads the VENUS labware library and the system deck (the `.lay` and the STARlet configuration). Produces a single deck model: carriers, sites, labware with absolute positions, and tip and well geometry.
2. **Backend adapters.** A simulation adapter (PyLabRobot chatterbox or STAR chatterbox) and a real-execution adapter (STARBackend, or the Pi bridge) both consume the same deck model, so simulated and real decks cannot drift apart.
3. **Check stages as separate modules.** Verifier, preflight (the AHC-equivalent refusals), simulator, 3D visualizer and executor each take the deck model and the IR, and each can be run and tested alone.
4. **Reference decks** (`config/reference/*.json`) stay only for the benchmark, clearly labelled, and never used on the real path.

## Open questions

- **VENUS seating rule.** How VENUS seats a tip rack in a carrier site and where it picks up tips. Needed to confirm or correct the 6 mm offset before the tip-height check is trusted.
- **Order of work.** Refactor first, or pin down the seating rule first?
- **Commit scope.** Commit the PyLabRobot upgrade alone now, or wait until the refactor is done?
- **Test file.** `tests/test_venus_layout.py` changed on disk outside this session (now uses `tests/fixtures/venus/ahc_deck.lay` and a third argument to `deck_config_from_lay`). Rerun the suite before committing.

## Implications for the plugin

- The plugin's skill should call the same deck model and check modules as the CLI, not its own copy of the deck.
- Each check stage should be invokable alone so the skill can report which stage failed.
- Before a real run the skill must confirm the Pi's PyLabRobot version matches the one tested.
