"""Stage 2: Protocol Compiler (JSON IR -> PyLabRobot module).

A deterministic translator: the same IR always compiles to the same code. Models in the
self-healing loop never write Python; they edit the IR, and this compiler turns it into PLR.

Generated module contract:
    async def run_protocol(lh, res) -> None
        lh:  pylabrobot LiquidHandler, already set up (backend chosen by stage 3/4)
        res: dict of protocol labware ID -> PLR resource (built by pipeline/deck.py)

Each IR step becomes one or more statements preceded by a `# step N: ...` comment, so stage 3
can map a runtime exception back to the IR step that caused it.

Device steps (incubate, shake) act on a plate sitting on a heater-shaker. Hold times are not
waited out in simulation; the step only sets the device state the hardware would be in.
`empty` aspirates everything in a plate column, whatever it holds at that point, into waste.
"""

import json
from pathlib import Path
from typing import Any, Dict, List

import yaml

ROWS = "ABCDEFGH"
ACTIONS = ("tips_on", "tips_off", "aspirate", "dispense", "empty", "incubate", "shake")
DEVICE_ACTIONS = ("incubate", "shake")


class CompilationError(ValueError):
    """Raised when an IR step cannot be translated (unknown action or labware, missing field)."""


def _spots(labware: str, column: int, channels: List[int]) -> str:
    return "[" + ", ".join(f'res["{labware}"].get_item("{ROWS[ch]}{column}")' for ch in channels) + "]"


def translate_step(step: Dict[str, Any], kinds: Dict[str, str]) -> str:
    n, action, labware = step.get("step"), step.get("action"), step.get("labware")
    channels = step.get("channels", [0])

    if action not in ACTIONS:
        raise CompilationError(f"Step {n}: unknown action '{action}'. Supported: {', '.join(ACTIONS)}.")
    if action == "tips_off":
        return "await lh.discard_tips()"
    if labware not in kinds:
        raise CompilationError(f"Step {n}: labware '{labware}' is not on the deck (config/plr_deck.json).")
    if any(not isinstance(ch, int) or not 0 <= ch < len(ROWS) for ch in channels):
        raise CompilationError(f"Step {n}: channels must be integers 0-7, got {channels}.")

    kind = kinds[labware]
    if action in DEVICE_ACTIONS:
        return _device_step(step, kind)
    if action == "empty":
        return _empty_step(step, kind, kinds)
    if action == "tips_on":
        if kind != "tip_rack":
            raise CompilationError(f"Step {n}: tips_on needs a tip rack, '{labware}' is a {kind}.")
        if "column" not in step:
            raise CompilationError(f"Step {n}: tips_on needs a 'column'.")
        return f"await lh.pick_up_tips({_spots(labware, step['column'], channels)}, use_channels={channels})"

    if "volume_ul" not in step:
        raise CompilationError(f"Step {n}: {action} needs 'volume_ul'.")
    vols = [float(step["volume_ul"])] * len(channels)
    if kind == "plate":
        if "column" not in step:
            raise CompilationError(f"Step {n}: {action} on a plate needs a 'column'.")
        targets = _spots(labware, step["column"], channels)
    elif kind in ("container", "trash"):
        targets = f'[res["{labware}"]] * {len(channels)}'
    else:
        raise CompilationError(f"Step {n}: cannot {action} on a {kind} ('{labware}').")
    return f"await lh.{action}({targets}, vols={vols}, use_channels={channels})"


def _number(step: Dict[str, Any], key: str, minimum: float = 0) -> float:
    value = step.get(key)
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= minimum:
        raise CompilationError(f"Step {step.get('step')}: {step.get('action')} needs '{key}' greater than {minimum:g}.")
    return float(value)


def _device_step(step: Dict[str, Any], kind: str) -> str:
    n, action, labware = step.get("step"), step.get("action"), step.get("labware")
    if kind != "plate":
        raise CompilationError(f"Step {n}: {action} needs a plate on a heater-shaker, '{labware}' is a {kind}.")
    duration = _number(step, "duration_s")
    hs = f'heater_shaker(res, "{labware}")'
    if step.get("temperature_c") is not None:
        temp = _number(step, "temperature_c", minimum=-273)
        lines = [f"await {hs}.set_temperature({temp})", f"await {hs}.wait_for_temperature()"]
    elif action == "incubate":
        lines = [f"await {hs}.deactivate()  # room temperature"]
    else:
        lines = []
    if action == "shake":
        speed = _number(step, "speed_rpm")
        lines += [f"await {hs}.shake(speed={speed})", f"await {hs}.stop_shaking()", f"await {hs}.unlock_plate()"]
    lines.append(f"# hold {duration:g} s (not waited out in simulation)")
    return "\n".join(lines)


def _empty_step(step: Dict[str, Any], kind: str, kinds: Dict[str, str]) -> str:
    n, labware, channels = step.get("step"), step.get("labware"), step.get("channels", [0])
    if kind != "plate" or "column" not in step:
        raise CompilationError(f"Step {n}: empty needs a plate and a 'column', got '{labware}' ({kind}).")
    waste = step.get("waste") or next((lid for lid, k in kinds.items() if k == "trash"), None)
    if kinds.get(waste) not in ("trash", "container"):
        raise CompilationError(f"Step {n}: empty needs a waste container on the deck, got '{waste}'.")
    return "\n".join([
        f"_wells = {_spots(labware, step['column'], channels)}",
        "_vols = [w.tracker.get_used_volume() for w in _wells]",
        f"await lh.aspirate(_wells, vols=_vols, use_channels={channels})",
        f'await lh.dispense([res["{waste}"]] * {len(channels)}, vols=_vols, use_channels={channels})',
    ])


def compile_protocol(protocol: Dict[str, Any], deck_config: Dict[str, Any]) -> str:
    """Translate an IR dict into the source of a PLR module."""
    kinds = {lid: spec["kind"] for lid, spec in deck_config["labware"].items()}
    lines = [
        f'"""Compiled from protocol: {protocol.get("protocol_name", "unnamed")}. Do not edit; recompile from the IR."""',
        "",
    ]
    if any(s.get("action") in DEVICE_ACTIONS for s in protocol.get("steps", [])):
        lines.append("from pipeline.deck import heater_shaker")
    lines += ["", "async def run_protocol(lh, res):"]
    for step in protocol.get("steps", []):
        desc = step.get("description") or f"{step.get('action')} {step.get('labware', '')}".strip()
        lines.append(f"    # step {step.get('step')}: {desc}")
        lines.extend("    " + line for line in translate_step(step, kinds).splitlines())
    return "\n".join(lines) + "\n"


def compile_file(protocol_path: str, deck_config_path: str, output_dir: str) -> Path:
    """Compile an IR file and write `<stem>_plr.py` to output_dir. Returns the module path."""
    with open(protocol_path) as f:
        protocol = yaml.safe_load(f)  # JSON is valid YAML
    with open(deck_config_path) as f:
        deck_config = json.load(f)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    module_path = out / f"{Path(protocol_path).stem}_plr.py"
    module_path.write_text(compile_protocol(protocol, deck_config))
    return module_path
