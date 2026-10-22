"""Build the PyLabRobot deck described by config/plr_deck.json.

Deck construction is fixed config, not model output: stages 2-5 all build the same
deck from the same file. Starting reagent volumes come from the protocol IR
(`initial_volumes_ul`), because how much liquid the scientist loads is part of the plan.
"""

import json
from typing import Any, Dict, Optional, Tuple

import pylabrobot.resources as plr


def load_deck_config(path: str) -> Dict[str, Any]:
    with open(path, "r") as f:
        return json.load(f)


def build_deck(
    config: Dict[str, Any], initial_volumes_ul: Optional[Dict[str, float]] = None
) -> Tuple[plr.Deck, Dict[str, plr.Resource]]:
    """Create the deck and return it with a map of protocol labware ID -> PLR resource.

    Containers listed in `initial_volumes_ul` start with that volume; everything else starts empty.
    """
    deck = getattr(plr, config["deck"])()

    carriers = {}
    for spec in config["carriers"]:
        carriers[spec["name"]] = getattr(plr, spec["factory"])(name=spec["name"])

    resources: Dict[str, plr.Resource] = {}
    for labware_id, spec in config["labware"].items():
        if spec["kind"] == "trash":
            resources[labware_id] = deck.get_trash_area()
            continue
        resource = getattr(plr, spec["factory"])(name=labware_id)
        carriers[spec["carrier"]][spec["slot"]] = resource
        resources[labware_id] = resource

    for spec in config["carriers"]:
        deck.assign_child_resource(carriers[spec["name"]], rails=spec["rails"])

    for labware_id, volume in (initial_volumes_ul or {}).items():
        container = resources.get(labware_id)
        if not isinstance(container, plr.Container):
            raise KeyError(f"initial_volumes_ul names '{labware_id}', which is not a container on the deck")
        container.tracker.set_volume(volume)

    return deck, resources
