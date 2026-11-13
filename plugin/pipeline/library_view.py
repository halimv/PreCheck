"""What the Library page shows, and nothing else: ground truth only.

- labware: VENUS's own library (config/Labware), as deck_builder reads it: every plate, tip rack and reagent
  container VENUS defines and Precheck can place.
- deck: the deck on the STARlet now, from the instrument's VENUS layout (config/instrument/ahc_deck.lay).
- used_by: which protocols are drafted for that deck.
"""

from pathlib import Path
from typing import Any, Dict, List

from pipeline.deck import INSTRUMENT_DECK, ROOT, deck_config_from_venus
from pipeline.deck_builder import catalog

GROUP_OF_KIND = {"plate": "plates", "tip_rack": "tips", "reservoir": "reagent_containers", "tube_rack": "reagent_containers"}
DESCRIPTION = ("VENUS's labware library (config/Labware) as Precheck reads it: the plates, tip racks and reagent "
               "containers it can place on the STARlet's deck. Capacities are VENUS's own volume equations.")


def inventory(root: Path = ROOT) -> Dict[str, Any]:
    out: Dict[str, Any] = {"labware_library": {"description": DESCRIPTION, "source": "config/Labware (VENUS)"},
                           "plates": {}, "tips": {}, "reagent_containers": {}}
    for e in catalog(root):
        group = GROUP_OF_KIND.get(e["kind"])
        ident = e["venus_type"]
        if group is None or ident in out[group]:
            continue
        common = {"id": ident, "source": e["venus_file"], "description": e.get("description") or None}
        if group == "plates":
            item = {**common, "product_name": ident, "well_format": f"{e['rows']} × {e['columns']}",
                    "capacity_ul_per_well": e["capacity_ul"], "size_mm": e["size"][:2]}
        elif group == "tips":
            item = {**common, "tip_type": "Hamilton tip", "specifications": {
                "capacity_ul": e.get("tip_volume_ul"), "filter": e.get("filter")}}
        else:
            item = {**common, "type": "Tube rack" if e["kind"] == "tube_rack" else "Reservoir",
                    "volume_ul": e["capacity_ul"]}
        out[group][ident] = item
    return out


def instrument_deck(root: Path = ROOT) -> Dict[str, Any]:
    """The STARlet's deck as VENUS lays it out now, in the shape the Library page draws."""
    config = deck_config_from_venus(str(root / INSTRUMENT_DECK), root)
    labware = {lid: {k: v for k, v in spec.items() if k != "offset_mm"} for lid, spec in config["labware"].items()}
    return {"file": Path(INSTRUMENT_DECK).name, "description": config.get("description", ""), "deck": config["deck"],
            "carriers": config["carriers"], "labware": labware, "machines": {}, "plr_version": None}


def used_by(protocol_files: List[Path], root: Path = ROOT) -> List[str]:
    """The protocols (by file name) drafted for the STARlet's deck."""
    names = []
    for path in protocol_files:
        if path.suffix not in (".json", ".yaml", ".yml") or path.stem.endswith(("_heal_log", "_report")):
            continue
        names.append(path.name)
    return names
