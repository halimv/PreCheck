"""Build the PyLabRobot deck a protocol names in its `deck_config` field.

Deck construction is fixed config, not model output: stages 2-5 all build the same
deck from the same file. Starting reagent volumes come from the protocol IR
(`initial_volumes_ul`), because how much liquid the scientist loads is part of the plan.

The deck is ground truth from VENUS: a `deck_config` that is a .lay (INSTRUMENT_DECK, the deck on the
STARlet) is read directly, with every carrier and labware built as config/venus_labware.json says
(PyLabRobot's factory where it matches VENUS, else VENUS's own definition in config/Labware). Labware
IDs are the VENUS IDs. JSON deck configs remain for the reference simulation deck in config/reference/,
which protocols written before the real deck was known (no `deck_config` field) still use.

A deck config may also list `machines` (heater-shakers). Labware with `"on": "<machine id>"`
sits on that machine instead of a carrier slot, so incubate and shake steps can reach it.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pylabrobot.resources as plr
from pylabrobot.legacy.heating_shaking import HeaterShaker
from pylabrobot.legacy.heating_shaking.chatterbox import HeaterShakerChatterboxBackend
from pylabrobot.legacy.machines.machine import Machine
from pylabrobot.resources import Coordinate

AMBIENT_C = 22.0
ROOT = Path(__file__).resolve().parent.parent
INSTRUMENT_DECK = "config/instrument/ahc_deck.lay"  # the deck on the STARlet (VENUS); new protocols are drafted on it
REFERENCE_DECK = "config/reference/plr_deck.json"  # the hand-written simulation deck of the benchmark and tests
DEFAULT_DECK = REFERENCE_DECK  # for protocols that name no deck: they all predate the real deck


class DeckError(ValueError):
    pass


class DeviceError(ValueError):
    """A device step the hardware would refuse. `code` names the lab-concept failure."""

    def __init__(self, message: str, code: str):
        super().__init__(message)
        self.code = code


class SimulatedHamiltonHeaterShakerBackend(HeaterShakerChatterboxBackend):
    """ChatterBox heater-shaker that enforces the limits PLR's real Hamilton backend asserts
    (20-2000 rpm, 0-105 C) and, like the hardware, starts at room temperature and cannot cool."""

    def __init__(self, min_rpm: float = 20, max_rpm: float = 2000, max_temperature_c: float = 105):
        super().__init__()
        self.min_rpm, self.max_rpm, self.max_temperature_c = min_rpm, max_rpm, max_temperature_c
        self._dummy_temperature = AMBIENT_C

    async def start_shaking(self, speed: float):
        if not self.min_rpm <= speed <= self.max_rpm:
            raise DeviceError(
                f"Shaking speed {speed:g} rpm is outside the heater-shaker's range "
                f"({self.min_rpm:g}-{self.max_rpm:g} rpm).", code="SHAKE_SPEED_OUT_OF_RANGE")
        await super().start_shaking(speed)

    async def set_temperature(self, temperature: float):
        if not 0 < temperature <= self.max_temperature_c:
            raise DeviceError(
                f"Temperature {temperature:g} C is outside the heater-shaker's range "
                f"(above 0, up to {self.max_temperature_c:g} C).", code="TEMPERATURE_OUT_OF_RANGE")
        await super().set_temperature(temperature)

    async def deactivate(self):
        # The heater switches off and the plate cools passively; a room-temperature hold
        # (the only step that deactivates) is assumed to be long enough to reach ambient.
        await super().deactivate()
        self._dummy_temperature = AMBIENT_C


def heater_shaker(res: Dict[str, Any], labware: str) -> HeaterShaker:
    """The heater-shaker holding `labware` (compiled incubate and shake steps call this)."""
    holder = res[labware].parent
    if not isinstance(holder, HeaterShaker):
        raise DeviceError(
            f"'{labware}' is not on a heater-shaker (it sits on '{getattr(holder, 'name', holder)}'), "
            "so it cannot be incubated or shaken.", code="NOT_ON_HEATER_SHAKER")
    return holder


def machines(res: Dict[str, Any]) -> List[Machine]:
    """The machines on a built deck, which need setup() before a run and stop() after."""
    return [r for r in res.values() if isinstance(r, Machine)]


def load_deck_config(path: str) -> Dict[str, Any]:
    """A deck config from a JSON file, or from a VENUS layout (.lay) read as ground truth."""
    if str(path).lower().endswith(".lay"):
        return deck_config_from_venus(path)
    with open(path, "r") as f:
        return json.load(f)


def deck_config_from_venus(path: str, root: Path = ROOT) -> Dict[str, Any]:
    """The deck a VENUS layout describes. Refused if anything on it cannot be built: a deck missing an item
    would not know it is there."""
    from pipeline.instrument import DEFAULT_INSTRUMENT
    from pipeline.venus_layout import deck_config_from_lay, load_venus_map, read_lay

    lay = Path(path)
    config, problems = deck_config_from_lay(read_lay(lay.read_bytes()), load_venus_map(root), lay.name)
    if problems:
        raise DeckError(f"{lay.name} cannot be built: " + "; ".join(f"{p['id']}: {p['problem']}" for p in problems))
    return {**config, "instrument": DEFAULT_INSTRUMENT}


def is_reference(deck_config: Dict[str, Any]) -> bool:
    """A hand-written simulation deck, not the instrument's: never for a run on the robot."""
    return bool(deck_config.get("reference"))


def deck_config_for(protocol: Dict[str, Any], root: Path) -> Dict[str, Any]:
    """The deck a protocol names in its `deck_config` field (relative to the repo root), else the default deck."""
    return load_deck_config(str(root / protocol.get("deck_config", DEFAULT_DECK)))


def make_resource(spec: Dict[str, Any], name: str) -> plr.Resource:
    """A carrier or labware from its deck-config entry: PyLabRobot's factory, or, with `"build": "venus"`, the
    VENUS definition in config/Labware (pipeline/venus_labware.py)."""
    if spec.get("build") == "venus":
        from pipeline.venus_labware import make
        return make(spec["venus"], name, factory=spec.get("factory"), role=spec.get("role"))
    return getattr(plr, spec["factory"])(name=name)


def _build_machine(machine_id: str, spec: Dict[str, Any]) -> Machine:
    if spec["kind"] != "heater_shaker":
        raise KeyError(f"machine '{machine_id}' has unknown kind '{spec['kind']}'")
    sx, sy, sz = spec["size_mm"]
    cx, cy, cz = spec["child_location_mm"]
    lo, hi = spec.get("speed_rpm", [20, 2000])
    backend = SimulatedHamiltonHeaterShakerBackend(lo, hi, spec.get("max_temperature_c", 105))
    return HeaterShaker(name=machine_id, size_x=sx, size_y=sy, size_z=sz, backend=backend,
                        child_location=Coordinate(x=cx, y=cy, z=cz))


def build_deck(
    config: Dict[str, Any], initial_volumes_ul: Optional[Dict[str, float]] = None
) -> Tuple[plr.Deck, Dict[str, plr.Resource]]:
    """Create the deck and return it with a map of protocol labware ID -> PLR resource.

    Machines are included in the map under their own IDs. Containers listed in
    `initial_volumes_ul` start with that volume; everything else starts empty.
    """
    deck = getattr(plr, config["deck"])()

    carriers = {}
    for spec in config["carriers"]:
        carriers[spec["name"]] = make_resource(spec, spec["name"])

    resources: Dict[str, plr.Resource] = {}
    for machine_id, spec in config.get("machines", {}).items():
        resources[machine_id] = _build_machine(machine_id, spec)

    for labware_id, spec in config["labware"].items():
        if spec["kind"] == "trash":
            resources[labware_id] = deck.get_trash_area()
            continue
        resource = make_resource(spec, labware_id)
        if "on" in spec:
            resources[spec["on"]].assign_child_resource(resource)
        elif "offset_mm" in spec:  # a trough's container inside its rack's footprint (pipeline/venus_labware.py)
            carriers[spec["carrier"]].sites[spec["slot"]].assign_child_resource(resource, location=Coordinate(*spec["offset_mm"]))
        else:
            carriers[spec["carrier"]][spec["slot"]] = resource
        resources[labware_id] = resource

    for spec in config["carriers"]:
        deck.assign_child_resource(carriers[spec["name"]], rails=spec["rails"])
    for machine_id, spec in config.get("machines", {}).items():
        deck.assign_child_resource(resources[machine_id], rails=spec["rails"])

    for labware_id, volume in (initial_volumes_ul or {}).items():
        container = resources.get(labware_id)
        if not isinstance(container, plr.Container):
            raise KeyError(f"initial_volumes_ul names '{labware_id}', which is not a container on the deck")
        container.tracker.set_volume(volume)

    if config.get("instrument"):  # the real instrument, from config/instrument/ (pipeline/instrument.py)
        from pipeline.instrument import apply_to_deck, load_instrument
        apply_to_deck(deck, load_instrument(config["instrument"]))

    return deck, resources
