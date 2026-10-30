"""Benchmark scenes: one protocol IR plus the ground truth for the faults it contains.

S1 is the v1 protocol as written (channel spacing at step 2, then too little stock).
S2 and S3 start from the healed v1 IR, which passes all stages, and under-load one source.
Each fault is injected by changing `initial_volumes_ul` only, so the injection is one documented edit.
"""

import copy
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent.parent
V1_PATH = ROOT / "protocols" / "serial_dilution_v1.json"
HEALED_PATH = ROOT / "docs" / "runs" / "2026-10-21_v1_qwen2.5-coder-7b" / "serial_dilution_v1_healed.json"

STOCK_NEEDED_UL = 800.0     # 8 channels x 100 uL from tube_15ml
DILUENT_NEEDED_UL = 4400.0  # 8 channels x (200 + 200 + 150) uL from reservoir_50ml


@dataclass
class Fault:
    code: str      # diagnostic error code the fault produces
    labware: str
    required_ul: float = 0.0  # INSUFFICIENT_LIQUID only: minimum load that fixes it


@dataclass
class Scene:
    scene_id: str
    family: str
    protocol: Dict[str, Any]
    faults: List[Fault]
    injection: Dict[str, Any] = field(default_factory=dict)


def _load(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text())


def _under_load(base: Dict[str, Any], labware: str, volume: float) -> Dict[str, Any]:
    protocol = copy.deepcopy(base)
    protocol["initial_volumes_ul"][labware] = volume
    return protocol


def build_scenes() -> List[Scene]:
    v1, healed = _load(V1_PATH), _load(HEALED_PATH)
    scenes = [Scene(
        "S1_v1_natural", "S1", v1,
        [Fault("CHANNEL_SPACING", "tube_15ml"), Fault("INSUFFICIENT_LIQUID", "tube_15ml", STOCK_NEEDED_UL)],
        {"note": "v1 as written; tube_15ml loaded at 600 uL"},
    )]
    for vol in (150, 350, 550, 700, 790):
        scenes.append(Scene(
            f"S2_stock_{vol}", "S2", _under_load(healed, "tube_15ml", vol),
            [Fault("INSUFFICIENT_LIQUID", "tube_15ml", STOCK_NEEDED_UL)],
            {"labware": "tube_15ml", "initial_volume_ul": vol},
        ))
    for vol in (1000, 2000, 3000, 4000, 4390):
        scenes.append(Scene(
            f"S3_diluent_{vol}", "S3", _under_load(healed, "reservoir_50ml", vol),
            [Fault("INSUFFICIENT_LIQUID", "reservoir_50ml", DILUENT_NEEDED_UL)],
            {"labware": "reservoir_50ml", "initial_volume_ul": vol},
        ))
    return scenes


def expected_concentrations() -> Dict[int, float]:
    """Expected concentration (uM) per plate column, from the v1 IR's dilution table."""
    return {c["column"]: c["concentration_um"] for c in _load(V1_PATH)["dilution"]["columns"]}
