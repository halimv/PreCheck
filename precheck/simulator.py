"""
Hamilton simulator integration via PyLabRobot.

Executes precheck-verified protocols in PyLabRobot's real STARlet simulator
to validate runtime behavior (deck layout, tip mechanics, volume tracking).
"""

import asyncio
import json
import os
import yaml
from typing import Dict, Any, List
from pylabrobot.hamilton.star import STARlet
import pylabrobot.resources as plr
from pylabrobot.resources import Coordinate
from pylabrobot.resources.corning import cor_96_wellplate_360uL_Fb
from pylabrobot.resources.hamilton import hamilton_96_tiprack_300uL


class SimulatorError(Exception):
    """Raised when simulator encounters a runtime error."""
    pass


class HamiltonSimulator:
    """
    Executes precheck protocols in PyLabRobot's Hamilton STARlet simulator.

    Uses the real STARlet simulator (not chatterbox mock) for proper state tracking.
    This matches AHC's approach and provides full deck visualization + state management.
    """

    def __init__(self, labware_config_path: str, protocol_plan_path: str, hardware_config_path: str = None):
        """
        Initialize simulator with labware specs, protocol plan, and hardware config.

        Args:
            labware_config_path: Path to labware_config.json (safety specs)
            protocol_plan_path: Path to protocol_plan.yaml (precheck-verified protocol)
            hardware_config_path: Path to hardware_config.json (deck layout). Auto-discovers if not provided.
        """
        with open(labware_config_path, "r") as f:
            self.labware_lib = json.load(f)
        with open(protocol_plan_path, "r") as f:
            self.plan = yaml.safe_load(f)

        # Load hardware config (auto-discover if not provided)
        if hardware_config_path is None:
            plan_dir = os.path.dirname(protocol_plan_path)
            hardware_config_path = os.path.join(plan_dir, "hardware_config.json")

        with open(hardware_config_path, "r") as f:
            self.hardware_config = json.load(f)

        # Use first hardware configuration by default (Hamilton STAR)
        self.hw_config = self.hardware_config["hardware_configurations"][0]

        # Create STARlet deck (will initialize device in _setup_deck)
        self.deck = plr.STARLetDeck()
        self.device = None  # Initialized in _setup_deck

        self.execution_log: List[Dict[str, Any]] = []
        self.tip_rack = None
        self.plate = None

    def run_simulation(self) -> Dict[str, Any]:
        """Execute protocol in simulator."""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(self._run_async())
            return result
        finally:
            loop.close()

    async def _run_async(self) -> Dict[str, Any]:
        """Execute protocol asynchronously."""
        try:
            await self._setup_deck()
            steps = self.plan.get("steps", [])

            for step_data in steps:
                await self._execute_step(step_data)

            return {
                "status": "PASSED",
                "message": f"Simulator executed {len(steps)} steps successfully.",
                "execution_log": self.execution_log,
                "errors": []
            }
        except SimulatorError as e:
            return {
                "status": "FAILED",
                "error": str(e),
                "execution_log": self.execution_log
            }
        except Exception as e:
            return {
                "status": "FAILED",
                "error": f"Simulator error: {str(e)}",
                "execution_log": self.execution_log,
                "exception_type": type(e).__name__
            }
        finally:
            if self.device is not None:
                await self.device.stop()

    async def _setup_deck(self):
        """Initialize deck with labware resources from hardware config."""
        # Create resources from hardware config
        for resource_config in self.hw_config["resources"]:
            resource_type = resource_config["type"]
            location_coords = resource_config["location_coordinates"]
            location = Coordinate(
                x=location_coords["x"],
                y=location_coords["y"],
                z=location_coords["z"]
            )

            if resource_type == "hamilton_96_tiprack_300uL":
                self.tip_rack = hamilton_96_tiprack_300uL(name=resource_config["name"])
                self.deck.assign_child_resource(self.tip_rack, location=location)

            elif resource_type == "cor_96_wellplate_360uL_Fb":
                self.plate = cor_96_wellplate_360uL_Fb(name=resource_config["name"])
                self.deck.assign_child_resource(self.plate, location=location)

        # Initialize the STARlet device with simulation=True
        self.device = STARlet(deck=self.deck, simulation=True)
        await self.device.setup()

    async def _execute_step(self, step: Dict[str, Any]):
        """Execute a single precheck protocol step in simulator."""
        step_num = step.get("step")
        action = step.get("action")
        labware_id = step.get("labware")
        channels = step.get("channels", list(range(8)))
        col = step.get("column", 1)
        volume = step.get("volume_ul", 0.0)

        log_entry = {
            "step": step_num,
            "action": action,
            "labware": labware_id,
            "status": "pending"
        }

        try:
            if action == "tips_on":
                await self._execute_tips_on(col, channels)
                log_entry["status"] = "completed"

            elif action == "tips_off":
                await self._execute_tips_off()
                log_entry["status"] = "completed"

            elif action == "aspirate":
                await self._execute_aspirate(col, volume, channels)
                log_entry["volume_ul"] = volume
                log_entry["status"] = "completed"

            elif action == "dispense":
                await self._execute_dispense(col, volume, channels)
                log_entry["volume_ul"] = volume
                log_entry["status"] = "completed"

            else:
                log_entry["status"] = "skipped"
                log_entry["reason"] = f"Unknown action: {action}"

            self.execution_log.append(log_entry)

        except Exception as e:
            log_entry["status"] = "failed"
            log_entry["error"] = str(e)
            self.execution_log.append(log_entry)
            raise SimulatorError(f"Step {step_num} ({action}): {str(e)}")

    async def _execute_tips_on(self, col: int, channels: List[int]):
        """Pick up tips from rack at specified column."""
        try:
            # Convert column-based protocol to individual tip positions
            # Column is 1-indexed in protocol, PyLabRobot uses 0-indexed
            col_idx = col - 1

            # Get individual TipSpot objects from tip_rack.children
            # For 8x12 grid: index = row * 12 + col
            tips_to_pick = []
            for ch in channels:
                tip_index = ch * 12 + col_idx
                tips_to_pick.append(self.tip_rack.children[tip_index])

            # Pick up the tips using STARlet device
            await self.device.pipettes.pick_up_tips(tips_to_pick)
        except Exception as e:
            raise SimulatorError(f"Failed to pick up tips at column {col}: {str(e)}")

    async def _execute_tips_off(self):
        """Discard tips to waste."""
        try:
            # STARlet discard_tips() handles the trash resource internally
            await self.device.pipettes.discard_tips()
        except Exception as e:
            raise SimulatorError(f"Failed to drop tips: {str(e)}")

    async def _execute_aspirate(self, col: int, volume: float, channels: List[int]):
        """Aspirate volume from plate."""
        try:
            # Convert column-based protocol to individual well positions
            # Column is 1-indexed in protocol, PyLabRobot uses 0-indexed
            col_idx = col - 1

            # Get individual Well objects from plate.children
            # For 8x12 grid: index = row * 12 + col
            wells = []
            for ch in channels:
                well_index = ch * 12 + col_idx
                wells.append(self.plate.children[well_index])

            # PyLabRobot aspirate expects vols as a list
            vols = [volume] * len(wells)
            await self.device.pipettes.aspirate(wells, vols=vols)
        except Exception as e:
            raise SimulatorError(f"Failed to aspirate from column {col}: {str(e)}")

    async def _execute_dispense(self, col: int, volume: float, channels: List[int]):
        """Dispense volume to plate."""
        try:
            # Convert column-based protocol to individual well positions
            # Column is 1-indexed in protocol, PyLabRobot uses 0-indexed
            col_idx = col - 1

            # Get individual Well objects from plate.children
            # For 8x12 grid: index = row * 12 + col
            wells = []
            for ch in channels:
                well_index = ch * 12 + col_idx
                wells.append(self.plate.children[well_index])

            # PyLabRobot dispense expects vols as a list
            vols = [volume] * len(wells)
            await self.device.pipettes.dispense(wells, vols=vols)
        except Exception as e:
            raise SimulatorError(f"Failed to dispense to column {col}: {str(e)}")
