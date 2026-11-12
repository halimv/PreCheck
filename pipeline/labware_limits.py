"""The volume limits stage 1 checks plate wells against.

On a real deck the limits follow from ground truth plus policy: a well's capacity is what its geometry holds
(VENUS's volume equations for labware built from VENUS), and config/precheck_policy.json says how much of it a
protocol may use (dead volume at the bottom, fill fraction at the top). Nothing about the labware is typed in.

A reference simulation deck (config/reference/) names a fixed limits file in `labware_limits` instead, so the
benchmark and the tests keep the numbers their documented results were measured with.

The result has the shape stage 1 reads: {"plates": {labware id: {"well_specifications": {"well_volume_range":
{"min_ul", "max_ul", ...}}}}}.
"""

import json
from pathlib import Path
from typing import Any, Dict

from pipeline.deck import ROOT, build_deck

POLICY = "config/precheck_policy.json"


def load_policy(root: Path = ROOT) -> Dict[str, Any]:
    return json.loads((root / POLICY).read_text())


def labware_limits(deck_config: Dict[str, Any], root: Path = ROOT) -> Dict[str, Any]:
    if deck_config.get("labware_limits"):
        return json.loads((root / deck_config["labware_limits"]).read_text())
    rules = load_policy(root)["plates"]
    _, res = build_deck(deck_config)
    plates = {}
    for lid, spec in deck_config["labware"].items():
        if spec.get("kind") != "plate":
            continue
        rule = {**rules, **rules.get("by_type", {}).get(spec["factory"], {})}
        capacity = res[lid].get_item("A1").max_volume
        source = f"VENUS {spec['venus']}" if spec.get("build") == "venus" else f"PyLabRobot {spec['factory']}"
        plates[lid] = {"well_specifications": {"well_volume_range": {
            "min_ul": rule["dead_volume_ul"],
            "max_ul": round(capacity * rule["max_fill_fraction"], 1),
            "capacity_ul": round(capacity, 1),
            "source": f"capacity from {source}; dead volume and fill fraction from {POLICY}",
        }}}
    return {"plates": plates}
