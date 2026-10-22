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

from pipeline.deck import build_deck
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
            await self.lh.stop()


async def visualize_protocol(
    protocol: Dict[str, Any],
    deck_config: Dict[str, Any],
    step_delay_s: float = 0.4,
    open_browser: bool = True,
    wait_for_browser_s: float = 20.0,
    name: Optional[str] = None,
) -> VisualizerSession:
    """Start the visualizer and replay `protocol` on a fresh ChatterBox deck.

    Waits up to `wait_for_browser_s` for the page to connect before replaying, then leaves the
    visualizer running so the final deck state can be inspected. Exceptions from the protocol
    propagate; stage 3 should have caught them already.
    """
    set_tip_tracking(True)
    set_volume_tracking(True)
    namespace: Dict[str, Any] = {}
    exec(compile(compile_protocol(protocol, deck_config), "<stage4_replay>", "exec"), namespace)

    deck, resources = build_deck(deck_config, protocol.get("initial_volumes_ul"))
    lh = LiquidHandler(backend=LiquidHandlerChatterboxBackend(num_channels=8), deck=deck)
    visualizer = Visualizer(resource=lh, open_browser=open_browser, name=name or protocol.get("protocol_name"))
    with contextlib.redirect_stdout(io.StringIO()):  # hide ChatterBox's and the servers' printouts
        await lh.setup()
        await visualizer.setup()
    session = VisualizerSession(visualizer, lh, resources, f"http://{visualizer.host}:{visualizer.fs_port}")

    for _ in range(int(wait_for_browser_s / 0.2)):
        if visualizer.has_connection():
            break
        await asyncio.sleep(0.2)

    try:
        with contextlib.redirect_stdout(io.StringIO()):
            await namespace["run_protocol"](Paced(lh, step_delay_s), resources)
    except Exception:
        await session.stop()
        raise
    return session
