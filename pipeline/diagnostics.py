"""Translate PyLabRobot runtime exceptions into lab-concept diagnostics.

The simulator (stage 3) catches the exception, works out which IR step raised it, and
captures deck state. This module turns that into a structured diagnostic a scientist
(or a small model in the self-healing loop) can act on: what went wrong in physical
terms, the relevant numbers, and the IR changes that would fix it.
"""

import math
import re
from typing import Any, Dict, List, Optional

from pylabrobot.liquid_handling.errors import ChannelizedError, ChannelsDoNotFitError
from pylabrobot.resources.errors import (
    CrossContaminationError,
    HasTipError,
    NoTipError,
    TooLittleLiquidError,
    TooLittleVolumeError,
)

ROWS = "ABCDEFGH"
CHANNEL_PITCH_MM = 9.0  # minimum spacing between Hamilton 1 mL channels


def unwrap(exc: BaseException) -> BaseException:
    """PLR wraps per-channel failures in ChannelizedError; return the first underlying error."""
    if isinstance(exc, ChannelizedError) and exc.errors:
        return next(iter(exc.errors.values()))
    return exc


def planned_aspirate_ul(protocol: Dict[str, Any], labware: str) -> float:
    """Total volume the IR aspirates from `labware` across all steps (all channels)."""
    return sum(
        float(s.get("volume_ul", 0)) * len(s.get("channels", [0]))
        for s in protocol.get("steps", [])
        if s.get("action") == "aspirate" and s.get("labware") == labware
    )


def capture_state(lh, res: Dict[str, Any], deck_config: Dict[str, Any], step: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Snapshot the parts of the deck relevant to diagnosing a failure."""
    state: Dict[str, Any] = {
        "tips_mounted": {ch: lh.head[ch].has_tip for ch in range(lh.backend.num_channels)},
        "container_volumes_ul": {},
        "unused_tip_columns": {},
    }
    for lid, spec in deck_config["labware"].items():
        if spec["kind"] == "container":
            state["container_volumes_ul"][lid] = round(res[lid].tracker.get_used_volume(), 2)
        elif spec["kind"] == "tip_rack":
            rack = res[lid]
            state["unused_tip_columns"][lid] = [
                c for c in range(1, 13)
                if all(rack.get_item(f"{r}{c}").tracker.has_tip for r in ROWS)
            ]
    if step and step.get("column") and deck_config["labware"].get(step.get("labware"), {}).get("kind") == "plate":
        plate = res[step["labware"]]
        state["plate_column_volumes_ul"] = {
            f"{ROWS[ch]}{step['column']}": round(plate.get_item(f"{ROWS[ch]}{step['column']}").tracker.get_used_volume(), 2)
            for ch in step.get("channels", [0])
        }
    return state


def translate(
    exc: BaseException,
    step: Optional[Dict[str, Any]],
    protocol: Dict[str, Any],
    res: Dict[str, Any],
    state: Dict[str, Any],
) -> Dict[str, Any]:
    """Build a lab-concept diagnostic for an exception raised while running `step`."""
    err = unwrap(exc)
    raw = f"{type(err).__name__}: {err}"
    step = step or {}
    n = step.get("step")
    labware = step.get("labware")
    channels = step.get("channels", [0])
    diag: Dict[str, Any] = {"step": n, "step_ir": step, "raw_error": raw, "deck_state": state}

    if isinstance(err, ChannelsDoNotFitError) or (isinstance(err, ValueError) and "space channels" in str(err)):
        width = res[labware].get_size_y() if labware in res else 0.0
        fit = max(1, math.floor(width / CHANNEL_PITCH_MM))
        diag.update(
            error_code="CHANNEL_SPACING",
            explanation=(
                f"Step {n} sends {len(channels)} channels into '{labware}' at the same time. "
                f"Hamilton channels must stay at least {CHANNEL_PITCH_MM:g} mm apart, and '{labware}' is only "
                f"{width:g} mm wide, so about {fit} channel(s) fit in it at once. The robot physically cannot "
                f"lower all {len(channels)} channels into it together."
            ),
            suggested_fixes=[
                f"Replace step {n} with {len(channels)} steps of the same action, each using a single channel "
                f"(channels [0], then [1], ... [{channels[-1]}]) and the same labware and volume_ul.",
                "Or move this reagent to a container wide enough for 8 channels (a trough), if one is on the deck.",
            ],
        )
    elif isinstance(err, TooLittleLiquidError):
        available = state["container_volumes_ul"].get(labware)
        requested = re.findall(r"([\d.]+)uL", str(err))
        fixes = [f"Lower volume_ul in step {n} so the source keeps enough liquid."]
        detail = ""
        if labware in protocol.get("initial_volumes_ul", {}):
            start = protocol["initial_volumes_ul"][labware]
            needed = planned_aspirate_ul(protocol, labware)
            load = math.ceil(needed * 1.1 / 50) * 50  # 10% margin, rounded up to 50 uL
            detail = (
                f" The plan loads {start:g} uL into '{labware}' but aspirates {needed:g} uL from it in total, "
                f"so it runs dry before the protocol finishes."
            )
            fixes.insert(0, f"Have the scientist load more reagent (needed {needed:g} uL plus a 10% margin): "
                            f'{{"op": "set_initial_volume", "labware": "{labware}", "volume_ul": {load}}}. '
                            "This keeps every step unchanged.")
        diag.update(
            error_code="INSUFFICIENT_LIQUID",
            explanation=(
                f"Step {n} tries to aspirate {requested[0] if requested else step.get('volume_ul')} uL per channel "
                f"from '{labware}', but it only holds {available if available is not None else 'too little'} uL "
                f"at this point.{detail}"
            ),
            suggested_fixes=fixes,
        )
    elif isinstance(err, TooLittleVolumeError) and step.get("action") == "aspirate":
        diag.update(
            error_code="TIP_OVERFLOW",
            explanation=(
                f"Step {n} aspirates {step.get('volume_ul')} uL per channel, more than the mounted tips have room "
                f"for (tips may already hold liquid from earlier aspirates). {err}"
            ),
            suggested_fixes=[
                f"Lower volume_ul in step {n}, or dispense what the tips already hold before aspirating again."
            ],
        )
    elif isinstance(err, TooLittleVolumeError):
        diag.update(
            error_code="CONTAINER_OVERFLOW",
            explanation=f"Step {n} dispenses more into '{labware}' than it can hold. {err}",
            suggested_fixes=[f"Lower volume_ul in step {n}, or dispense into an emptier well or column."],
        )
    elif isinstance(err, HasTipError):
        what = "a tip spot that already holds a tip" if step.get("action") != "tips_on" else "channels that already carry tips"
        diag.update(
            error_code="TIP_ALREADY_MOUNTED",
            explanation=f"Step {n} ({step.get('action')}) hits {what}. {err}",
            suggested_fixes=[f"Add a tips_off step before step {n} so the channels are empty before picking up new tips."],
        )
    elif isinstance(err, NoTipError):
        if step.get("action") == "tips_on":
            free = state["unused_tip_columns"].get(labware, [])
            diag.update(
                error_code="TIP_SPOT_EMPTY",
                explanation=f"Step {n} picks up tips from '{labware}' column {step.get('column')}, but those tips were already used.",
                suggested_fixes=[f"Change the column in step {n} to an unused one. Unused full columns in '{labware}': {free}."],
            )
        else:
            diag.update(
                error_code="NO_TIP_MOUNTED",
                explanation=f"Step {n} ({step.get('action')}) runs on channels {channels} without tips mounted.",
                suggested_fixes=[f"Add a tips_on step for channels {channels} before step {n}."],
            )
    elif isinstance(err, CrossContaminationError):
        diag.update(
            error_code="CROSS_CONTAMINATION",
            explanation=f"Step {n} would reuse a tip that touched a different liquid. {err}",
            suggested_fixes=[f"Add tips_off and tips_on (fresh tips) before step {n}."],
        )
    else:
        diag.update(
            error_code="UNRECOGNIZED",
            explanation=f"Step {n} failed in simulation with {raw}. No lab-concept translation exists for this error yet.",
            suggested_fixes=[],
        )
    return diag
