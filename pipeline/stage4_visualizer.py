"""Stage 4: Visualizer (replay in PyLabRobot's browser visualizer).

Replays a protocol that passed stages 1-3 so a person can watch it before stage 5 sends it to
hardware. It uses PyLabRobot's own `pylabrobot.visualizer.Visualizer`, which serves a web page
that draws the deck and updates live as tips are picked up and liquid moves.

The replay runs on a fresh ChatterBox deck with the same deck config, compiled code and
trackers as stage 3, pausing after each step so the changes are visible.
"""

import asyncio
import contextlib
import inspect
import io
from dataclasses import dataclass
from typing import Any, Dict, Optional

from pylabrobot.liquid_handling import LiquidHandler
from pylabrobot.liquid_handling.backends import LiquidHandlerChatterboxBackend
from pylabrobot.resources import set_tip_tracking, set_volume_tracking
from pylabrobot.visualizer import Visualizer

from pipeline.deck import build_deck, machines
from pipeline.stage2_compiler import compile_protocol


class Paced:
    """Wraps a LiquidHandler so every call the protocol makes pauses afterwards, slow enough to watch."""

    def __init__(self, lh: LiquidHandler, delay_s: float):
        self._lh, self._delay_s = lh, delay_s

    def __getattr__(self, name: str):
        method = getattr(self._lh, name)

        async def paced(*args, **kwargs):
            result = method(*args, **kwargs)
            if inspect.isawaitable(result):
                result = await result
            await asyncio.sleep(self._delay_s)
            return result
        return paced


@dataclass
class VisualizerSession:
    """A running visualizer and the simulated deck it shows. Call `stop()` when done."""

    visualizer: Visualizer
    lh: LiquidHandler
    resources: Dict[str, Any]
    url: str

    async def stop(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()):
            await self.visualizer.stop()
            for machine in machines(self.resources):
                await machine.stop()
            await self.lh.stop()


async def start_visualizer(
    protocol: Dict[str, Any],
    deck_config: Dict[str, Any],
    open_browser: bool = True,
    name: Optional[str] = None,
) -> VisualizerSession:
    """Build a fresh ChatterBox deck for `protocol` and start the visualizer on it (no steps run yet)."""
    set_tip_tracking(True)
    set_volume_tracking(True)
    deck, resources = build_deck(deck_config, protocol.get("initial_volumes_ul"))
    lh = LiquidHandler(backend=LiquidHandlerChatterboxBackend(num_channels=8), deck=deck)
    visualizer = Visualizer(resource=lh, open_browser=open_browser, name=name or protocol.get("protocol_name"))
    with contextlib.redirect_stdout(io.StringIO()):  # hide ChatterBox's and the servers' printouts
        await lh.setup()
        for machine in machines(resources):
            await machine.setup()
        await visualizer.setup()
    return VisualizerSession(visualizer, lh, resources, f"http://{visualizer.host}:{visualizer.fs_port}")


async def replay(
    session: VisualizerSession,
    protocol: Dict[str, Any],
    deck_config: Dict[str, Any],
    step_delay_s: float = 0.4,
    wait_for_browser_s: float = 20.0,
) -> None:
    """Wait up to `wait_for_browser_s` for the page to connect, then run `protocol` step by step.

    The visualizer stays running afterwards. Exceptions from the protocol propagate (stage 3 should
    have caught them already) and stop the session.
    """
    namespace: Dict[str, Any] = {}
    exec(compile(compile_protocol(protocol, deck_config), "<stage4_replay>", "exec"), namespace)

    for _ in range(int(wait_for_browser_s / 0.2)):
        if session.visualizer.has_connection():
            break
        await asyncio.sleep(0.2)

    try:
        with contextlib.redirect_stdout(io.StringIO()):
            await namespace["run_protocol"](Paced(session.lh, step_delay_s), session.resources)
    except Exception:
        await session.stop()
        raise


async def visualize_protocol(
    protocol: Dict[str, Any],
    deck_config: Dict[str, Any],
    step_delay_s: float = 0.4,
    open_browser: bool = True,
    wait_for_browser_s: float = 20.0,
    name: Optional[str] = None,
) -> VisualizerSession:
    """Start the visualizer and replay `protocol` on it; returns the still-running session."""
    session = await start_visualizer(protocol, deck_config, open_browser=open_browser, name=name)
    await replay(session, protocol, deck_config, step_delay_s=step_delay_s, wait_for_browser_s=wait_for_browser_s)
    return session
