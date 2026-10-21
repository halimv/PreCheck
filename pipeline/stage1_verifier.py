"""Stage 1: Declarative Protocol Verifier.

Safety gate enforcing volume limits, tip management, and contamination prevention
before any code is compiled or executed.
"""

import yaml
import json
import os
from typing import Dict, Any, List


class SafetyGateError(ValueError):
    """Custom exception for Pre-Execution Safety Gate failures."""
    def __init__(self, message: str, code: str = "VALIDATION_ERROR"):
        super().__init__(message)
        self.code = code


class Verifier:
    """
    Precheck safety gate for liquid handling protocols.

    Enforces:
    - Volume limits: Per-labware specs (min/max from labware.json)
    - Tip management: 96-tip rack, 8-channel head, per-rack per-channel tracking
    - Contamination prevention: Smart tracking of source wells per channel
      * Tips can be reused for same source well (serial dilution pattern)
      * Tips_off required to switch to different source well
      * Each channel tracks its own contamination state independently

    Initial hardware state is loaded from protocol_defaults.json if provided,
    otherwise uses safe defaults (empty plate, full tip rack, no mounted tips).

    Error codes:
    - TIP_DEPLETED: tip position already used
    - MISSING_TIP: channel lacks mounted tip for operation
    - DRY_ASPIRATE: would violate minimum volume (includes dead volume)
    - VOLUMETRIC_OVERFLOW: would violate maximum volume
    - CONTAMINATED_TIP: attempting cross-contamination (different source well)
    """

    def __init__(self, labware_path: str, plan_path: str, config_path: str = None):
        with open(labware_path, "r") as f:
            self.labware_lib = json.load(f)
        with open(plan_path, "r") as f:
            self.plan = yaml.safe_load(f)

        # Load protocol config for initial state (optional, auto-discover if not provided)
        self.protocol_config = {}
        if config_path and os.path.exists(config_path):
            with open(config_path, "r") as f:
                self.protocol_config = json.load(f)
        elif not config_path:
            # Try to auto-discover protocol_defaults.json in config/ directory
            plan_dir = os.path.dirname(plan_path)
            inferred_config = os.path.join(plan_dir, "..", "config", "protocol_defaults.json")
            if os.path.exists(inferred_config):
                with open(inferred_config, "r") as f:
                    self.protocol_config = json.load(f)

        # Initialize hardware state from protocol_config or defaults
        self._initialize_hardware_state()

    def _initialize_hardware_state(self):
        """Initialize hardware state from protocol_config or safe defaults."""
        initial_state = self.protocol_config.get("initial_state", {})

        # Plate state: 8 rows x 12 columns (volume in uL)
        plate_config = initial_state.get("plate", {})
        if plate_config.get("wells_volume_ul") == "empty":
            self.plate_state = [[0.0 for _ in range(12)] for _ in range(8)]
        else:
            self.plate_state = [[0.0 for _ in range(12)] for _ in range(8)]  # Default to empty

        # Tip rack state per labware: {rack_name: 8 rows x 12 columns}
        # (True = tip present, False = used/depleted). Racks are created on first use.
        self.tip_rack_state = {}

        # Pipette head mounted tips: 8-channel head (True = tip mounted, False = no tip)
        head_config = initial_state.get("pipette_head", {})
        mounted = head_config.get("channels_mounted_tips", [False] * 8)
        self.channel_mounted_tips = mounted if len(mounted) == 8 else [False] * 8

        # Contamination tracking: per-channel source well (None = clean)
        self.tip_source_well = {ch: None for ch in range(8)}

    def run_verification(self) -> Dict[str, Any]:
        try:
            steps = self.plan.get("steps", [])
            for step_data in steps:
                self._evaluate_step(step_data)

            return {
                "status": "PASSED",
                "message": f"Successfully verified {len(steps)} declarative protocol steps.",
                "errors": []
            }
        except SafetyGateError as e:
            return {
                "status": "FAILED",
                "error_code": e.code,
                "message": str(e)
            }

    def _get_plate_specs(self, labware: str) -> Dict[str, Any]:
        """Get volume specs from labware.json for given labware."""
        if labware in self.labware_lib.get("plates", {}):
            return self.labware_lib["plates"][labware]["well_specifications"]["well_volume_range"]
        return {}

    def _evaluate_step(self, step: Dict[str, Any]):
        step_num = step.get("step")
        action = step.get("action")
        labware = step.get("labware")
        channels = step.get("channels", [0])
        col_idx = step.get("column", 1) - 1 if step.get("column") else None  # Convert 1-indexed to 0-indexed

        if action == "tips_on":
            if col_idx is None:
                raise SafetyGateError(
                    f"Step {step_num}: tips_on action requires 'column' field.",
                    code="VALIDATION_ERROR"
                )
            for ch in channels:
                rack = self.tip_rack_state.setdefault(labware, [[True for _ in range(12)] for _ in range(8)])
                # Check tip availability at (row=ch, column=col_idx) in this rack
                if not rack[ch][col_idx]:
                    raise SafetyGateError(
                        f"Step {step_num}: No tip available in rack '{labware}' at Row {ch+1}, Col {col_idx+1}.",
                        code="TIP_DEPLETED"
                    )
                rack[ch][col_idx] = False
                self.channel_mounted_tips[ch] = True

        elif action == "tips_off":
            for ch in range(8):
                self.channel_mounted_tips[ch] = False
                self.tip_source_well[ch] = None  # Clear contamination tracking

        elif action == "aspirate":
            if col_idx is None:
                raise SafetyGateError(
                    f"Step {step_num}: aspirate action requires 'column' field.",
                    code="VALIDATION_ERROR"
                )
            vol = step.get("volume_ul", 0.0)

            for ch in channels:
                # 1. Validate channel has a mounted tip
                if not self.channel_mounted_tips[ch]:
                    raise SafetyGateError(
                        f"Step {step_num}: Channel {ch} attempted aspirate without a mounted tip.",
                        code="MISSING_TIP"
                    )

                # 2. Check contamination (smart tracking: allow same source reuse)
                source_well = (labware, col_idx)
                current_source = self.tip_source_well[ch]

                if current_source is not None and current_source != source_well:
                    raise SafetyGateError(
                        f"Step {step_num}: Channel {ch} attempted aspirate from different source well. "
                        f"Previously aspirated from {current_source[0]} column {current_source[1]+1}, "
                        f"now attempting column {col_idx+1}. Use tips_off before switching sources.",
                        code="CONTAMINATED_TIP"
                    )

                # Record this as the source well for this channel
                self.tip_source_well[ch] = source_well

                # 3. Volumetric check (read specs from labware.json)
                plate_specs = self._get_plate_specs(labware)
                if plate_specs:
                    min_vol = plate_specs["min_ul"]
                    current_vol = self.plate_state[ch][col_idx]

                    if current_vol - vol < min_vol:
                        raise SafetyGateError(
                            f"Step {step_num}: Dry aspirate risk at Row {ch+1}, Col {col_idx+1}. "
                            f"Current: {current_vol}uL, requested aspirate: {vol}uL (min accessible: {min_vol}uL from {labware}).",
                            code="DRY_ASPIRATE"
                        )
                    self.plate_state[ch][col_idx] -= vol

        elif action == "dispense":
            if col_idx is None:
                raise SafetyGateError(
                    f"Step {step_num}: dispense action requires 'column' field.",
                    code="VALIDATION_ERROR"
                )
            vol = step.get("volume_ul", 0.0)

            for ch in channels:
                # 1. Validate channel has a mounted tip
                if not self.channel_mounted_tips[ch]:
                    raise SafetyGateError(
                        f"Step {step_num}: Channel {ch} attempted dispense without a mounted tip.",
                        code="MISSING_TIP"
                    )

                # 2. Volumetric check (read specs from labware.json)
                plate_specs = self._get_plate_specs(labware)
                if plate_specs:
                    max_vol = plate_specs["max_ul"]
                    current_vol = self.plate_state[ch][col_idx]

                    if current_vol + vol > max_vol:
                        raise SafetyGateError(
                            f"Step {step_num}: Volumetric overflow risk at Row {ch+1}, Col {col_idx+1}. "
                            f"Current: {current_vol}uL + {vol}uL exceeds max usable capacity ({max_vol}uL from {labware}).",
                            code="VOLUMETRIC_OVERFLOW"
                        )
                    self.plate_state[ch][col_idx] += vol
