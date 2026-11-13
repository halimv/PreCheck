"""Stage 4: Visualizer (replay in PyLabRobot's 3D viewer, on the STAR device).

Replays a protocol that passed the simulator so a person can watch the whole assay before it goes on. The
viewer's root is the STAR device itself (pipeline/pipetting.py), the same model AHC shows: the body, the arms and the
channels are in its tree and move as the protocol moves them; tips leave their racks and wells fill as the replay
runs. Each step waits `step_delay_s` so the changes can be followed.

The replay runs on a fresh deck with the same deck config, compiled code and trackers as stage 3.
"""

import asyncio
import contextlib
import io
import socket
from dataclasses import dataclass
from typing import Any, Dict, Optional

from pylabrobot.resources import set_tip_tracking, set_volume_tracking
from pylabrobot.visualizer3D import Viewer3D

from pipeline.deck import build_deck, machines
from pipeline.instrument import firmware_configuration
from pipeline.pipetting import close_device, draw_height, open_device, set_pace
from pipeline.stage2_compiler import compile_protocol


@dataclass
class VisualizerSession:
    """A running viewer and the simulated device it shows. Call `stop()` when done."""

    visualizer: Viewer3D
    lh: Any  # the STAR device the replay drives
    resources: Dict[str, Any]
    url: str

    async def stop(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()):
            await self.visualizer.stop()
            for machine in machines(self.resources):
                await machine.stop()
            await close_device(self.lh)


def _free_port() -> int:
    """A port nothing listens on now, so this viewer never lands on AHC's or another run's."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


async def start_visualizer(
    protocol: Dict[str, Any],
    deck_config: Dict[str, Any],
    open_browser: bool = True,
    name: Optional[str] = None,
) -> VisualizerSession:
    """Build a fresh simulated deck for `protocol`, its STAR device, and the viewer on the device (no steps run yet)."""
    set_tip_tracking(True)
    set_volume_tracking(True)
    deck, resources = build_deck(deck_config, protocol.get("initial_volumes_ul"))
    with contextlib.redirect_stdout(io.StringIO()):  # hide the device's and the servers' printouts
        dev = await open_device(deck, "chatterbox", firmware_configuration(deck_config))
        for machine in machines(resources):
            await machine.setup()
        draw_height(deck)  # frame the box the arms ride in, as AHC does
        visualizer = Viewer3D(dev, open_browser=open_browser, name=name or protocol.get("protocol_name") or "protocol",
                              fs_port=_free_port(), ws_port=_free_port())
        await visualizer.start()
    return VisualizerSession(visualizer, dev, resources, visualizer.url)


async def _wait_for_browser(visualizer: Viewer3D, timeout_s: float) -> None:
    try:
        await visualizer.wait_for_browser(timeout_s)
    except (asyncio.TimeoutError, TimeoutError):
        pass


async def replay(
    session: VisualizerSession,
    protocol: Dict[str, Any],
    deck_config: Dict[str, Any],
    step_delay_s: float = 1.0,
    wait_for_browser_s: float = 20.0,
) -> None:
    """Wait up to `wait_for_browser_s` for the page to connect, then run `protocol` step by step, pausing
    `step_delay_s` after each pipetting call. The viewer stays running afterwards. Exceptions from the protocol
    propagate (stage 3 should have caught them already) and stop the session."""
    namespace: Dict[str, Any] = {}
    exec(compile(compile_protocol(protocol, deck_config), "<stage4_replay>", "exec"), namespace)

    await _wait_for_browser(session.visualizer, wait_for_browser_s)
    set_pace(step_delay_s)
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            await namespace["run_protocol"](session.lh, session.resources)
    except Exception:
        await session.stop()
        raise
    finally:
        set_pace(0.0)


async def visualize_protocol(
    protocol: Dict[str, Any],
    deck_config: Dict[str, Any],
    step_delay_s: float = 1.0,
    open_browser: bool = True,
    wait_for_browser_s: float = 20.0,
    name: Optional[str] = None,
) -> VisualizerSession:
    """Start the viewer and replay `protocol` on it; returns the still-running session."""
    session = await start_visualizer(protocol, deck_config, open_browser=open_browser, name=name)
    await replay(session, protocol, deck_config, step_delay_s=step_delay_s, wait_for_browser_s=wait_for_browser_s)
    return session
