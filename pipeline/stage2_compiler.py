"""Stage 2: Protocol Compiler (JSON IR -> PyLabRobot module).

A deterministic translator: the same IR always compiles to the same code. Models in the
self-healing loop never write Python; they edit the IR, and this compiler turns it into PLR.

Generated module contract:
    async def run_protocol(lh, res) -> None
        lh:  the device, already set up (pipeline/pipetting.py: the STAR device, or the legacy LiquidHandler)
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


def venus_troughs(deck_config: Dict[str, Any]) -> frozenset:
    """Containers built from VENUS's definition: they know where VENUS sends each channel (pipeline.deck.reach)."""
    return frozenset(lid for lid, spec in deck_config["labware"].items()
                     if spec.get("kind") == "container" and spec.get("build") == "venus")


def translate_step(step: Dict[str, Any], kinds: Dict[str, str], troughs: frozenset = frozenset()) -> str:
    n, action, labware = step.get("step"), step.get("action"), step.get("labware")
    channels = step.get("channels", [0])

    if action not in ACTIONS:
        raise CompilationError(f"Step {n}: unknown action '{action}'. Supported: {', '.join(ACTIONS)}.")
    if action == "tips_off":
        return "await tips_off(lh)"
    if labware not in kinds:
        raise CompilationError(f"Step {n}: labware '{labware}' is not on the deck.")
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
        return f"await tips_on(lh, {_spots(labware, step['column'], channels)}, use_channels={channels})"

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
    where = f', **reach(res["{labware}"], {channels})' if labware in troughs else ""  # VENUS's channel positions
    return f"await {action}(lh, {targets}, vols={vols}, use_channels={channels}{where})"


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
        f"await aspirate(lh, _wells, vols=_vols, use_channels={channels})",
        f'await dispense(lh, [res["{waste}"]] * {len(channels)}, vols=_vols, use_channels={channels})',
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
    troughs = venus_troughs(deck_config)
    if any(s.get("labware") in troughs and s.get("action") in ("aspirate", "dispense") for s in protocol.get("steps", [])):
        lines.append("from pipeline.deck import reach")
    lines.append("from pipeline.pipetting import aspirate, dispense, tips_off, tips_on")
    lines += ["", "async def run_protocol(lh, res):"]
    for step in protocol.get("steps", []):
        desc = step.get("description") or f"{step.get('action')} {step.get('labware', '')}".strip()
        lines.append(f"    # step {step.get('step')}: {desc}")
        lines.extend("    " + line for line in translate_step(step, kinds, troughs).splitlines())
    return "\n".join(lines) + "\n"


STANDALONE_HEADER = """\
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # repo root, for pipeline.deck
"""

STANDALONE_MAIN = """

# --- Standalone runner: python {name} --backend chatterbox|star ---
DECK_CONFIG = {deck_file!r}
INITIAL_VOLUMES_UL = {volumes!r}


async def _main(backend_name):
    from pylabrobot.resources import set_tip_tracking, set_volume_tracking
    from pipeline.deck import build_deck, load_deck_config, machines
    from pipeline.instrument import firmware_configuration
    from pipeline.pipetting import close_device, open_device

    set_tip_tracking(True)
    set_volume_tracking(True)
    deck_config = load_deck_config(str(Path(__file__).resolve().parents[1] / DECK_CONFIG))
    deck, res = build_deck(deck_config, INITIAL_VOLUMES_UL)
    lh = await open_device(deck, backend_name, firmware_configuration(deck_config))
    for machine in machines(res):
        await machine.setup()
    try:
        await run_protocol(lh, res)
    finally:
        for machine in machines(res):
            await machine.stop()
        await close_device(lh)


if __name__ == "__main__":
    import argparse
    import asyncio

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=["chatterbox", "star"], default="chatterbox")
    args = parser.parse_args()
    if args.backend == "star":
        answer = input("Run on the real STARlet? The deck must match the setup checklist "
                       "(demo/server.py -> Execute). Type 'run' to continue: ")
        if answer.strip().lower() != "run":
            sys.exit("Not run.")
    asyncio.run(_main(args.backend))
"""


def compile_standalone(protocol: Dict[str, Any], deck_config: Dict[str, Any], deck_file: str, name: str) -> str:
    """`compile_protocol` plus a `__main__` that builds the deck and runs it on ChatterBox or the STAR.

    This is the script written to healed/. Stage 3 checks the plain module; the runner only adds
    deck construction around the same `run_protocol`.
    """
    docstring, rest = compile_protocol(protocol, deck_config).split("\n", 1)
    return (docstring + "\n" + STANDALONE_HEADER + rest
            + STANDALONE_MAIN.format(name=name, deck_file=deck_file, volumes=protocol.get("initial_volumes_ul", {})))


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
