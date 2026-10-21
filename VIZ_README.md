# Precheck Gate - Web Visualizer

A web-based protocol visualizer for loading and validating Hamilton liquid handler protocols.

## Quick Start

```bash
python start_visualizer.py
```

Then open **http://localhost:8000** in your browser.

## Features

Opentrons-style run view:
- **Protocol steps** (left) — Steps in plain language ("Aspirate 100 µL from Reservoir · slot 3 · column 1"), grouped into transfers. Click a step to jump to it.
- **Deck map** (center) — OT-2 12-slot deck with labware placed from `hardware_config.json`. Tip racks show used/remaining tips, plates fill wells by volume, the 8-channel head moves to each step's target column, and dispense steps draw an arc from the aspirate source.
- **Playback** — Play/pause, step forward/back, scrubber and speed. Keyboard: ←/→ to step, Space to play, Home/End.
- **Inspector** (right) — Current step details, per-channel tip/volume state, labware status, and verification results. A failed verification jumps to and highlights the failing step.

## Loading a protocol

Click **Load protocol**. The dialog opens on startup too. Pick a bundled sample set, or drop in your own files. Each file is matched to its slot by extension/contents. You can also drop a file on a specific slot. Every slot has a **Sample ↓** link to download the bundled example of that file.

| File | Required | Scope | What it contains |
|---|---|---|---|
| `protocol_plan.yaml` | Yes | Per run | `protocol_name`, `version`, and a `steps` list. Each step has `action` (`tips_on`, `aspirate`, `dispense`, `tips_off`), `labware` (an id from the labware library, or `waste`), a 1-based `column`, `channels` (0–7), and `volume_ul` for liquid steps. |
| `hardware_config.json` | Yes | Per run | `hardware_configurations` list. The `opentrons_ot2_v1` entry maps `tip_rack` / `plate` / `reservoir` to deck slots. |
| `protocol_config.json` | No | Per run | `initial_state` (plate, tip rack, mounted tips). Defaults: empty plate, full tip rack, no tips mounted. |
| `labware_config.json` | Yes | Library | Static labware library (`plates`, `tip_racks`, `reagent_containers`). The built-in `precheck/labware_config.json` is used by default. An uploaded replacement is saved in the browser and kept between runs until you click **Reset to built-in**. The repo file is never modified. |

The server validates every file before anything loads: it parses each one, checks the required keys, and confirms that each labware a step uses exists in the library. **Load protocol** stays disabled until every required file is present and valid. **Run verification** runs against the files you loaded.

## Files

```
viz_backend/
  ├── server.py          # Flask API server
  └── requirements.txt   # Python dependencies

viz_frontend/
  └── index.html         # Single-page web app

start_visualizer.py      # Python launcher
```

## API Endpoints

- `GET /` — Serve the web UI
- `GET /api/protocol` — Load protocol_plan.yaml
- `GET /api/deck` — Load hardware_config.json
- `GET /api/files` — Input file descriptions and sample sets
- `GET /api/samples/<name>` — Download a bundled sample file
- `GET|POST /api/session` — Validate files and return protocol + resolved deck (POST body: file texts; GET uses built-in samples)
- `POST /api/verify` — Run verification on posted file texts (or the built-in files if the body is empty)

## Requirements

- Python 3.x
- Flask, Flask-CORS, PyYAML

Dependencies are installed automatically by `start_visualizer.sh`.

## Workflow

1. **Start the visualizer** — `bash start_visualizer.sh`
2. **Open in browser** — http://localhost:8000
3. **Click "Load Protocol"** — Loads `precheck/protocol_plan.yaml` and hardware config
4. **View protocol steps** — Left panel shows protocol actions
5. **See deck layout** — Center panel visualizes deck resources
6. **Run verification** — Click "Run Verification" to validate the protocol
7. **Check results** — Right panel shows validation results and execution log

## Next Steps

- Create/update `precheck/protocol_plan.yaml` with your protocol
- The visualizer will automatically display it when you click "Load Protocol"
