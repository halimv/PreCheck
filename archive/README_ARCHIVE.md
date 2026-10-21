# Archive: Legacy & Reference Code

This directory contains code from earlier development phases that is **not part of the active 4-stage pipeline**. Files here are kept for reference and historical context but are not imported or executed by the main CLI (`cli.py`).

---

## Contents

### `files/` — Reference Implementations

Legacy reference implementations and configuration documents:

- **`serial_dilution_pylabrobot_v2.py`** — Standalone PyLabRobot implementation of serial dilution (not integrated with the verifier)
- **`config.json`, `config.yaml`** — Old configuration formats (replaced by `config/labware.json`, `config/hardware.json`, `config/protocol_defaults.json`)
- **`README_CONFIG_DRIVEN.md`, `CONFIG_GUIDE.md`, `IMPLEMENTATION_SUMMARY.md`** — Documentation from earlier phases
- **`Serial_Dilution_Experimental_Plan.txt`** — Experimental design notes

### `viz_backend/` — Visualization Server (Separate Concern)

A separate visualization tool (not part of the main pipeline):

- **`server.py`** — Flask/web server for protocol visualization
- **`requirements.txt`** — Viz-specific Python dependencies
- **`workspace/`** — Workspace for visualization state

The visualization system is decoupled from the main 4-stage pipeline. To run it:
```bash
cd archive/viz_backend
python server.py
```

### `simulator_old.py` — Broken PLR Simulator (Deferred)

Early attempt to integrate PyLabRobot's ChatterBox backend directly.

**Status:** ❌ **BROKEN** — ChatterBox does not maintain tip state across `drop_tips()` calls, breaking multi-step protocols.

**Decision:** Deferred to Phase 2. The verifier (`pipeline/stage1_verifier.py`) now tracks state independently.

### `json_parser_old.py` — Legacy JSON Parser

Earlier JSON parser (functionality now in `pipeline.stage2_compiler`).

**Status:** Superseded by `ProtocolCompiler` in `pipeline/stage2_compiler.py`.

### `main.py` — Old CLI

Previous entry point (replaced by `cli.py` at project root).

**Status:** Superseded by the new 4-stage orchestrator in `cli.py`.

### `start_visualizer.py` — Old Visualization Launcher

Previous script to launch the visualization server.

**Status:** Replaced by direct execution of `archive/viz_backend/server.py`.

---

## Why These Are Here

1. **Historical Context** — Shows the project's evolution from a standalone verifier → integrated 4-stage pipeline.
2. **Reference** — Useful patterns for hardware integration and PyLabRobot examples.
3. **Known Issues** — ChatterBox state bug is documented here; prevents naive PLR integration.
4. **Backup** — In case anything needs to be recovered or reimplemented.

---

## Migration Notes

### If You Need to Use Old Code

- **Visualization:** `python archive/viz_backend/server.py` (separate from main pipeline)
- **Reference PLR Script:** See `archive/files/serial_dilution_pylabrobot_v2.py` as an example
- **Old Configs:** See `archive/files/config.json` and `archive/files/config.yaml`

### If You Want to Integrate Something

- Move files back to the main project
- Update imports to use `pipeline.stage1_verifier`, `pipeline.stage2_compiler`, etc.
- Add tests to `precheck/test_verifier.py`

---

## Cleanup (Optional)

If you decide these files are no longer needed, you can safely delete the `archive/` directory. The main project (`cli.py`, `pipeline/`, `protocols/`, `config/`) is fully self-contained.

---

## See Also

- Main README: [`../README.md`](../README.md)
- Pipeline source: [`../pipeline/`](../pipeline/)
- Protocol specs: [`../protocols/`](../protocols/)
