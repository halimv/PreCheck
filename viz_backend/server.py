#!/usr/bin/env python3
"""Precheck Protocol Visualizer - Web Backend"""
from flask import Flask, jsonify, request, Response
from flask_cors import CORS
import json
import re
import tempfile
import yaml
import sys
from pathlib import Path

app = Flask(__name__)
CORS(app)

PROJECT_ROOT = Path(__file__).parent.parent
PRECHECK_DIR = PROJECT_ROOT / "precheck"
FRONTEND_FILE = PROJECT_ROOT / "viz_frontend" / "index.html"
EDITOR_FILE = PROJECT_ROOT / "viz_frontend" / "editor.html"
sys.path.insert(0, str(PROJECT_ROOT))
from precheck.verifier import Verifier

PROTOCOL_FILE = PRECHECK_DIR / "protocol_plan.yaml"
HARDWARE_FILE = PRECHECK_DIR / "hardware_config.json"
LABWARE_FILE = PRECHECK_DIR / "labware_config.json"
PROTOCOL_CONFIG_FILE = PRECHECK_DIR / "protocol_config.json"

# Step-2 editor: the plan being edited lives here as JSON. Seeded from the
# bundled simple demo the first time the editor is opened.
WORKSPACE_FILE = Path(__file__).parent / "workspace" / "protocol_plan.json"
SEED_PLAN_FILE = PRECHECK_DIR / "protocol_plan_simple.yaml"

DECK_ID = "opentrons_ot2_v1"
TRASH_SLOT = 12
TRASH_IDS = {"waste", "trash", "fixed_trash"}
KNOWN_ACTIONS = {"tips_on", "tips_off", "aspirate", "dispense"}

# labware_config.json category -> deck role
CATEGORY_ROLES = {
    "tip_racks": "tip_rack",
    "plates": "plate",
    "reagent_containers": "reservoir",
}

# Input files the run view needs. `labware_config` is a persistent library:
# the built-in file is used unless the user uploads a replacement.
FILE_SPECS = [
    {
        "key": "protocol_plan",
        "label": "Protocol plan",
        "filename": "protocol_plan.yaml",
        "format": "yaml",
        "required": True,
        "scope": "run",
        "description": "The steps to run: a YAML file with protocol_name, version and a `steps` list. "
                       "Each step has an action (tips_on, aspirate, dispense, tips_off), a labware id, "
                       "a 1-based column, channels, and volume_ul for liquid steps.",
    },
    {
        "key": "hardware_config",
        "label": "Deck / hardware config",
        "filename": "hardware_config.json",
        "format": "json",
        "required": True,
        "scope": "run",
        "description": "Deck layout: a `hardware_configurations` list. The visualizer uses the "
                       "`opentrons_ot2_v1` entry to place tip_rack, plate and reservoir in deck slots.",
    },
    {
        "key": "protocol_config",
        "label": "Initial state",
        "filename": "protocol_config.json",
        "format": "json",
        "required": False,
        "scope": "run",
        "description": "Optional. Starting hardware state under `initial_state` (plate volumes, tip rack, "
                       "mounted tips). If omitted, the run starts with an empty plate, full tip rack and no tips mounted.",
    },
    {
        "key": "labware_config",
        "label": "Labware library",
        "filename": "labware_config.json",
        "format": "json",
        "required": True,
        "scope": "library",
        "description": "Static library of labware specs (plates, tip_racks, reagent_containers) with volume limits. "
                       "The built-in library stays loaded between runs; upload a new one only if you need labware it doesn't define.",
    },
]

SAMPLE_SETS = [
    {
        "id": "serial_dilution",
        "name": "2-fold serial dilution",
        "summary": "12 steps · 3 transfers across reservoir and plate",
        "files": {
            "protocol_plan": "protocol_plan.yaml",
            "hardware_config": "hardware_config.json",
            "protocol_config": "protocol_config.json",
        },
    },
    {
        "id": "simple_demo",
        "name": "Simple demo",
        "summary": "4 steps · one pick-aspirate-dispense-drop cycle",
        "files": {
            "protocol_plan": "protocol_plan_simple.yaml",
            "hardware_config": "hardware_config.json",
        },
    },
]
SAMPLE_FILES = {"protocol_plan.yaml", "protocol_plan_simple.yaml", "hardware_config.json",
                "protocol_config.json", "labware_config.json"}


class InputError(Exception):
    """Per-file validation errors: {file_key: [messages]}."""
    def __init__(self, errors):
        super().__init__("Invalid input files")
        self.errors = errors


def _labware_spec(labware_lib, labware_id):
    """Return (role, spec) for a labware id from labware_config.json."""
    for category, role in CATEGORY_ROLES.items():
        spec = labware_lib.get(category, {}).get(labware_id)
        if spec:
            return role, spec
    return "unknown", {}


def _display_name(role, labware_id, spec):
    if role == "trash":
        return "Trash"
    if spec.get("product_name"):
        return spec["product_name"]
    parts = [spec.get("manufacturer") or spec.get("size"), spec.get("type")]
    return " ".join(p for p in parts if p) or labware_id


def resolve_deck(protocol, hardware, labware_lib):
    """Assign each labware referenced in the protocol to a deck slot.

    Slots come from the matching resource role in hardware_config.json
    (tip_rack/plate/reservoir); trash goes to the OT-2 fixed trash slot.
    """
    deck_cfg = next(
        (c for c in hardware.get("hardware_configurations", []) if c.get("id") == DECK_ID),
        None,
    )
    role_slots = {}
    if deck_cfg:
        for res in deck_cfg.get("resources", []):
            slot = int(str(res["position"]).replace("slot_", ""))
            role_slots.setdefault(res["name"], []).append(slot)

    used_slots = {TRASH_SLOT}
    labware = {}
    for step in protocol.get("steps", []):
        lw_id = step.get("labware")
        if not lw_id or lw_id in labware:
            continue
        if lw_id in TRASH_IDS:
            labware[lw_id] = {"id": lw_id, "role": "trash", "slot": TRASH_SLOT,
                              "name": "Trash", "spec": {}}
            continue

        role, spec = _labware_spec(labware_lib, lw_id)
        candidates = [s for s in role_slots.get(role, []) if s not in used_slots]
        free = [s for s in range(1, 12) if s not in used_slots]
        if not candidates and not free:
            raise InputError({"protocol_plan": ["More labware than free deck slots (11)."]})
        slot = candidates[0] if candidates else free[0]
        used_slots.add(slot)
        labware[lw_id] = {
            "id": lw_id,
            "role": role,
            "slot": slot,
            "name": _display_name(role, lw_id, spec),
            "spec": spec,
        }

    return {
        "deck": {
            "id": deck_cfg["id"] if deck_cfg else DECK_ID,
            "name": deck_cfg["name"] if deck_cfg else "Opentrons OT-2",
            "instrument": deck_cfg.get("instrument") if deck_cfg else "Opentrons OT-2",
            "num_slots": 12,
            "trash_slot": TRASH_SLOT,
        },
        "labware": labware,
    }


def default_texts():
    """Built-in file contents, used when the request doesn't provide them."""
    texts = {
        "protocol_plan": PROTOCOL_FILE.read_text(),
        "hardware_config": HARDWARE_FILE.read_text(),
        "labware_config": LABWARE_FILE.read_text(),
    }
    if PROTOCOL_CONFIG_FILE.exists():
        texts["protocol_config"] = PROTOCOL_CONFIG_FILE.read_text()
    return texts


def parse_inputs(texts):
    """Parse and cross-check input file texts. Raises InputError with per-file messages."""
    errors = {spec["key"]: [] for spec in FILE_SPECS}
    parsed = {}

    for spec in FILE_SPECS:
        key, text = spec["key"], texts.get(spec["key"])
        if text is None or not str(text).strip():
            if spec["required"]:
                errors[key].append(f"Missing required file ({spec['filename']}).")
            continue
        try:
            parsed[key] = yaml.safe_load(text) if spec["format"] == "yaml" else json.loads(text)
        except (yaml.YAMLError, json.JSONDecodeError) as e:
            errors[key].append(f"Couldn't parse {spec['format'].upper()}: {e}")
            continue
        if not isinstance(parsed[key], dict):
            errors[key].append("Top level must be an object/mapping.")
            del parsed[key]

    if "labware_config" in parsed:
        lib = parsed["labware_config"]
        if not any(isinstance(lib.get(c), dict) and lib[c] for c in CATEGORY_ROLES):
            errors["labware_config"].append(
                "No labware found. Expected at least one of: plates, tip_racks, reagent_containers.")

    if "hardware_config" in parsed:
        configs = parsed["hardware_config"].get("hardware_configurations")
        if not isinstance(configs, list) or not configs:
            errors["hardware_config"].append("Expected a non-empty `hardware_configurations` list.")
        elif not any(isinstance(c, dict) and c.get("id") == DECK_ID for c in configs):
            errors["hardware_config"].append(f"No `{DECK_ID}` deck configuration found.")

    if "protocol_config" in parsed:
        init = parsed["protocol_config"].get("initial_state")
        if init is not None and not isinstance(init, dict):
            errors["protocol_config"].append("`initial_state` must be an object.")

    if "protocol_plan" in parsed:
        steps = parsed["protocol_plan"].get("steps")
        if not isinstance(steps, list) or not steps:
            errors["protocol_plan"].append("Expected a non-empty `steps` list.")
        else:
            lib = parsed.get("labware_config", {})
            for i, step in enumerate(steps, 1):
                if not isinstance(step, dict):
                    errors["protocol_plan"].append(f"Step {i}: must be a mapping.")
                    continue
                n = step.get("step", i)
                action = step.get("action")
                if action not in KNOWN_ACTIONS:
                    errors["protocol_plan"].append(
                        f"Step {n}: unknown action '{action}' (expected one of {', '.join(sorted(KNOWN_ACTIONS))}).")
                lw_id = step.get("labware")
                if not lw_id:
                    errors["protocol_plan"].append(f"Step {n}: missing `labware`.")
                elif lw_id not in TRASH_IDS and "labware_config" in parsed \
                        and _labware_spec(lib, lw_id)[0] == "unknown":
                    errors["protocol_plan"].append(
                        f"Step {n}: labware '{lw_id}' isn't defined in the labware library.")
                if action in ("aspirate", "dispense") and not isinstance(step.get("volume_ul"), (int, float)):
                    errors["protocol_plan"].append(f"Step {n}: {action} needs a numeric `volume_ul`.")
                if action in ("tips_on", "aspirate", "dispense"):
                    col = step.get("column")
                    if not isinstance(col, int) or not 1 <= col <= 12:
                        errors["protocol_plan"].append(f"Step {n}: `column` must be an integer 1–12.")
                chs = step.get("channels", [])
                if not isinstance(chs, list) or any(not isinstance(c, int) or not 0 <= c <= 7 for c in chs):
                    errors["protocol_plan"].append(f"Step {n}: `channels` must be a list of integers 0–7.")

    errors = {k: v for k, v in errors.items() if v}
    if errors:
        raise InputError(errors)
    return parsed


def request_texts():
    """File texts from a JSON request body, falling back to built-in files."""
    body = request.get_json(silent=True)
    if not body:
        return default_texts()
    texts = {k: body.get(k) for k in ("protocol_plan", "hardware_config", "protocol_config", "labware_config")}
    if not texts.get("labware_config"):
        texts["labware_config"] = LABWARE_FILE.read_text()
    return texts


def build_session(parsed):
    return {
        "protocol": parsed["protocol_plan"],
        **resolve_deck(parsed["protocol_plan"], parsed["hardware_config"], parsed["labware_config"]),
        "initial_state": parsed.get("protocol_config", {}).get("initial_state", {}),
    }


@app.route("/")
def index():
    return FRONTEND_FILE.read_text()


@app.route("/api/protocol")
def get_protocol():
    """Load protocol YAML file"""
    if not PROTOCOL_FILE.exists():
        return jsonify({"error": "Protocol file not found"}), 404
    try:
        return jsonify(yaml.safe_load(PROTOCOL_FILE.read_text()))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/deck")
def get_deck():
    """Load hardware configuration"""
    if not HARDWARE_FILE.exists():
        return jsonify({"error": "Hardware config not found"}), 404
    try:
        return jsonify(json.loads(HARDWARE_FILE.read_text()))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/files")
def list_files():
    """Describe the input files and the bundled sample sets."""
    return jsonify({"files": FILE_SPECS, "sample_sets": SAMPLE_SETS})


@app.route("/api/samples/<name>")
def get_sample(name):
    """Serve a bundled sample file (also used as the built-in labware library)."""
    if name not in SAMPLE_FILES or not (PRECHECK_DIR / name).exists():
        return jsonify({"error": f"Unknown sample file: {name}"}), 404
    mimetype = "application/x-yaml" if name.endswith((".yaml", ".yml")) else "application/json"
    return Response((PRECHECK_DIR / name).read_text(), mimetype=mimetype)


@app.route("/api/session", methods=["GET", "POST"])
def get_session():
    """Validate input files and return protocol + resolved deck for the run view.

    POST body: {protocol_plan, hardware_config, protocol_config?, labware_config?} as file
    texts. GET (or an empty body) uses the built-in sample files.
    """
    try:
        texts = request_texts() if request.method == "POST" else default_texts()
        return jsonify(build_session(parse_inputs(texts)))
    except InputError as e:
        return jsonify({"error": "Some files are missing or invalid.", "file_errors": e.errors}), 422
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def run_verification(texts):
    """Validate the file texts, then run the precheck gate on them. Raises InputError."""
    parse_inputs(texts)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / "labware_config.json").write_text(texts["labware_config"])
        (tmp / "protocol_plan.yaml").write_text(texts["protocol_plan"])
        config_path = None
        if texts.get("protocol_config"):
            config_path = str(tmp / "protocol_config.json")
            Path(config_path).write_text(texts["protocol_config"])
        verifier = Verifier(str(tmp / "labware_config.json"), str(tmp / "protocol_plan.yaml"), config_path)
        result = verifier.run_verification()
    match = re.match(r"Step (\d+):", result.get("message", ""))
    if result.get("status") == "FAILED" and match:
        result["failed_step"] = int(match.group(1))
    return result


@app.route("/api/verify", methods=["POST"])
def verify():
    """Run protocol verification on the posted files (or the built-in ones)."""
    try:
        return jsonify(run_verification(request_texts()))
    except InputError as e:
        return jsonify({"status": "ERROR", "message": "Some files are missing or invalid.",
                        "file_errors": e.errors}), 422
    except Exception as e:
        return jsonify({"status": "ERROR", "message": str(e)}), 500


# ---------- Step-2 editor ----------

def load_workspace_plan():
    """The editor's working plan, seeded from the bundled demo on first use."""
    if not WORKSPACE_FILE.exists():
        WORKSPACE_FILE.parent.mkdir(parents=True, exist_ok=True)
        seed = yaml.safe_load(SEED_PLAN_FILE.read_text())
        WORKSPACE_FILE.write_text(json.dumps(seed, indent=2))
    return json.loads(WORKSPACE_FILE.read_text())


def plan_file_errors(plan):
    """Validation errors for a plan object, keyed by file, using the same checks as the run view."""
    texts = default_texts()
    texts["protocol_plan"] = json.dumps(plan)
    try:
        parse_inputs(texts)
        return {}
    except InputError as e:
        return e.errors


def save_workspace_plan(plan):
    """Renumber steps to their position, persist the plan, and return it with any validation errors."""
    steps = plan.get("steps")
    if isinstance(steps, list):
        for i, step in enumerate(steps, 1):
            if isinstance(step, dict):
                step["step"] = i
    WORKSPACE_FILE.parent.mkdir(parents=True, exist_ok=True)
    WORKSPACE_FILE.write_text(json.dumps(plan, indent=2))
    # Drafts are saved even when invalid; the editor shows the errors on the blocks.
    return {"plan": plan, "file_errors": plan_file_errors(plan)}


@app.route("/editor")
def editor():
    return EDITOR_FILE.read_text()


@app.route("/api/editor/plan", methods=["GET", "PUT"])
def editor_plan():
    """GET the workspace plan. PUT replaces it with the posted plan object."""
    try:
        if request.method == "GET":
            plan = load_workspace_plan()
            return jsonify({"plan": plan, "file_errors": plan_file_errors(plan)})
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return jsonify({"error": "Expected a JSON object with a `steps` list."}), 400
        return jsonify(save_workspace_plan(body))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/editor/labware")
def editor_labware():
    """Labware ids the editor can pick, grouped by library category."""
    lib = json.loads(LABWARE_FILE.read_text())
    items = [
        {"id": lw_id, "category": category}
        for category in CATEGORY_ROLES
        for lw_id in lib.get(category, {})
    ]
    return jsonify({"labware": items})


@app.route("/api/editor/verify", methods=["POST"])
def editor_verify():
    """Verify the workspace plan (saved by the editor) against the built-in deck and library."""
    try:
        texts = default_texts()
        texts["protocol_plan"] = json.dumps(load_workspace_plan())
        return jsonify(run_verification(texts))
    except InputError as e:
        return jsonify({"status": "ERROR", "message": "Some files are missing or invalid.",
                        "file_errors": e.errors}), 422
    except Exception as e:
        return jsonify({"status": "ERROR", "message": str(e)}), 500


if __name__ == "__main__":
    print("\n✅ Precheck Visualizer")
    print("🌐 http://localhost:8000          (run view)")
    print("✏️  http://localhost:8000/editor   (plan editor)\n")
    app.run(port=8000, debug=False)
