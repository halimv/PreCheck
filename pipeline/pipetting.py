"""Pipetting for Precheck, on either device. The compiled protocol calls these helpers and never a device directly.

Two devices:

- the STAR device, PyLabRobot's current STAR model (`pylabrobot.hamilton.star.STARlet`). It is what AHC runs, what
  the simulation runs on, and what the 3D view draws: its body, arms and channels are resources in the tree, and
  they move as the protocol moves them. Its pipetting is `device.pipettes`.
- the legacy LiquidHandler with the real STARBackend (`pylabrobot.legacy`), the path to the robot until it moves to
  the STAR device's driver. It is the device itself.

The two take the same arguments except for keyword names, which these helpers translate.
"""

import asyncio
from typing import Any, Dict, List, Optional, Sequence

from pylabrobot.hamilton.star import STARlet
from pylabrobot.legacy.liquid_handling import LiquidHandler as LegacyLiquidHandler

# Seconds to pause after each pipetting call, so a person can watch a replay. Zero for simulations and runs.
PACE_S = 0.0


def set_pace(seconds: float) -> None:
    global PACE_S
    PACE_S = seconds


async def _paced(call):
    result = await call
    if PACE_S:
        await asyncio.sleep(PACE_S)
    return result


def is_legacy(dev: Any) -> bool:
    return isinstance(dev, LegacyLiquidHandler)


def _pipettes(dev: Any) -> Any:
    return dev if is_legacy(dev) else dev.pipettes


def num_channels(dev: Any) -> int:
    return dev.backend.num_channels if is_legacy(dev) else dev.pipettes.num_channels


def mounted_channels(dev: Any) -> List[int]:
    """The channels that hold a tip now."""
    if is_legacy(dev):
        return [ch for ch in range(dev.backend.num_channels) if dev.head[ch].has_tip]
    p = dev.pipettes
    return [ch for ch in range(p.num_channels) if p.get_mounted_tip(ch) is not None]


async def open_device(deck: Any, backend: str, firmware: Optional[str] = None) -> Any:
    """The device a run uses, set up and ready: the STAR device simulated ("chatterbox"), answering as the instrument
    whose firmware report is `firmware` (pipeline/instrument.firmware_configuration), or the legacy LiquidHandler with
    the real STARBackend ("star")."""
    if backend == "star":
        from pylabrobot.legacy.liquid_handling.backends import STARBackend
        dev = LegacyLiquidHandler(backend=STARBackend(), deck=deck)
    elif backend == "chatterbox":
        dev = STARlet(deck=deck, simulation=True, declared_configuration_json=firmware)
    else:
        raise ValueError(f"backend must be 'chatterbox' or 'star', got {backend!r}")
    await dev.setup()
    if backend == "chatterbox" and firmware:
        _plan_at_instrument_pitch(dev, firmware)
    return dev


def _plan_at_instrument_pitch(dev: Any, firmware: str) -> None:
    """Plan the channels at the instrument's minimum pitch, as AHC does (ahc/devices/hamilton/starlet.py,
    `_plan_channel_spacing`). A channel reports its body width (about 18 mm), which would keep the channels of a
    9 mm plate column from working together; on this instrument they do, at its own minimum pitch (the firmware's
    min_raster_pitch_pip_channels, 9 mm). Set after setup, which reads the widths."""
    import json
    pitch = float(json.loads(open(firmware).read())["device"]["min_raster_pitch_pip_channels"])
    for channel in dev.pipettes.configuration.channels:
        channel.width = pitch


async def close_device(dev: Any) -> None:
    await dev.stop()


async def tips_on(dev: Any, spots: Sequence[Any], use_channels: List[int]) -> None:
    await _paced(_pipettes(dev).pick_up_tips(list(spots), use_channels=use_channels))


async def tips_off(dev: Any, use_channels: Optional[List[int]] = None) -> None:
    """Discard the tips into the waste (every mounted tip, unless channels are given)."""
    await _paced(_pipettes(dev).discard_tips(use_channels=use_channels))


async def return_tips(dev: Any, use_channels: Optional[List[int]] = None) -> None:
    await _paced(_pipettes(dev).return_tips(use_channels=use_channels))


async def aspirate(dev: Any, containers: Sequence[Any], vols: Sequence[float], use_channels: List[int],
                   offsets: Optional[List[Any]] = None) -> None:
    p = _pipettes(dev)
    if is_legacy(dev):
        call = p.aspirate(list(containers), vols=list(vols), use_channels=use_channels, offsets=offsets)
    else:
        call = p.aspirate(list(containers), volumes=list(vols), use_channels=use_channels, resource_offsets=offsets)
    await _paced(call)


async def dispense(dev: Any, containers: Sequence[Any], vols: Sequence[float], use_channels: List[int],
                   offsets: Optional[List[Any]] = None) -> None:
    p = _pipettes(dev)
    if is_legacy(dev):
        call = p.dispense(list(containers), vols=list(vols), use_channels=use_channels, offsets=offsets)
    else:
        call = p.dispense(list(containers), volumes=list(vols), use_channels=use_channels, resource_offsets=offsets)
    await _paced(call)


def draw_height(deck: Any) -> None:
    """The 3D view frames the device's box. The STAR's working envelope is 900 mm tall, but the top of the X-arm
    rides above it (334.7 mm of channel travel plus 140 mm of arm): that is the height the view should show.
    Drawing only; the same correction AHC applies (ahc/devices/hamilton/starlet.py)."""
    deck._size_z = deck._local_size_z = 334.7 + 140.0


def compiled_names() -> Dict[str, Any]:
    """What a compiled protocol's namespace needs from this module."""
    return {"tips_on": tips_on, "tips_off": tips_off, "aspirate": aspirate, "dispense": dispense,
            "return_tips": return_tips}
