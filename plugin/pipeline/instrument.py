"""The real instrument, from the static library in config/instrument/.

Precheck reads static config that reflects the real world: VENUS's library (config/Labware) is the labware, a deck is
where it sits, and config/instrument/<serial>.json is the instrument itself. Its facts come from two sources kept
next to it: the instrument's firmware configuration (read with reads only), VENUS's deck template (.tpl: the
deck's fixed parts) and the VENUS layout (.lay) of what is on the deck now. `load_instrument` checks the facts against both when it loads, so a stale file fails at once instead
of on the robot.

A deck config names its instrument in an `instrument` field; `pipeline.deck.build_deck` then calls
`apply_to_deck`, which changes PyLabRobot's deck where its defaults differ from the instrument. Today that is
one thing: where the 96 head is initialized. PyLabRobot 0.2.2 centers the head over its 96 waste resource (the
same x and y VENUS uses) and lowers it to the resource's height, 216.4 mm, where VENUS stops at 229.0 mm. The
waste resource is raised so the initialization PyLabRobot sends is VENUS's.
"""

import copy
import functools
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

import pylabrobot.resources as plr
from pylabrobot.legacy.liquid_handling.backends import STARBackend
from pylabrobot.resources import Coordinate

from pipeline.venus_layout import lay_items, read_lay

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INSTRUMENT = "config/instrument/starlet_F553.json"
MATCH_MM = 0.05


class InstrumentError(ValueError):
    pass


@functools.lru_cache(maxsize=8)
def _load(path: str, root: str) -> Dict[str, Any]:
    base = Path(root)
    instrument = json.loads((base / path).read_text())
    firmware = json.loads((base / instrument["firmware_configuration"]).read_text())["device"]
    template = read_lay((base / instrument["deck_template"]["file"]).read_bytes())
    layout = read_lay((base / instrument["deck_layout"]["file"]).read_bytes())
    problems = check(instrument, firmware, template, layout)
    if problems:
        raise InstrumentError(f"{path} does not match its sources: " + "; ".join(problems))
    return instrument


def load_instrument(path: str = DEFAULT_INSTRUMENT, root: Path = ROOT) -> Dict[str, Any]:
    """The instrument's facts, checked against its firmware configuration and VENUS layout."""
    return copy.deepcopy(_load(str(path), str(root)))


def check(instrument: Dict[str, Any], firmware: Dict[str, Any], template: Dict[str, str],
          layout: Dict[str, str]) -> List[str]:
    """Where the curated facts disagree with the firmware configuration, VENUS's deck template (the fixed parts)
    or the VENUS layout of the deck now."""
    problems: List[str] = []

    def same(fact: str, ours: Any, theirs: Any, source: str) -> None:
        if ours != theirs:
            problems.append(f"{fact} is {ours!r} here but {theirs!r} in the {source}")

    fw = "firmware configuration"
    same("serial", instrument["serial"], firmware["serial_number"], fw)
    same("channels.count", instrument["channels"]["count"], firmware["num_pip_channels"], fw)
    same("channels.volume_ul == 1000", instrument["channels"]["volume_ul"] == 1000, firmware["pip_type_1000ul"], fw)
    same("channels.min_pitch_mm", instrument["channels"]["min_pitch_mm"], firmware["min_raster_pitch_pip_channels"], fw)
    same("deck.rails", instrument["deck"]["rails"], firmware["instrument_size_slots"], fw)
    same("head96.installed", instrument["head96"]["installed"], firmware["head96_installed"], fw)
    same("iswap", instrument["iswap"], firmware["kb_iswap_installed"], fw)
    same("autoload", instrument["autoload"], firmware["autoload_installed"], fw)
    same("tip_waste.x_mm", instrument["tip_waste"]["x_mm"], firmware["tip_waste_x_position"], fw)

    same("deck.venus_deck", instrument["deck"]["venus_deck"], layout.get("Deck"), "VENUS layout")
    lay = "VENUS deck template"
    same("deck.venus_deck", instrument["deck"]["venus_deck"], template.get("Deck"), lay)
    items = lay_items(template)
    if instrument["head96"]["installed"]:
        slide = next((i for i in items if i["type"].lower() == "core96slidewaste" and i["parent"]), None)
        eject = instrument["head96"]["eject"]
        if slide is None:
            problems.append("the VENUS deck template has no CO-RE 96 slide waste for head96.eject")
        else:
            same("head96.eject (x, y)", (eject["x_mm"], eject["y_mm"]), (slide["x"], slide["y"]), lay)
    waste = next((i for i in items if i["type"].lower() == "waste2"), None)
    if waste is not None:
        same("tip_waste.x_mm", instrument["tip_waste"]["x_mm"], waste["x"], lay)
    return problems


def head96_a1(deck: plr.Deck) -> Coordinate:
    """Where PyLabRobot's STAR initialization sends the 96 head's A1, computed by PyLabRobot itself."""
    return STARBackend._position_96_head_in_resource(SimpleNamespace(deck=deck), deck.get_trash_area96())


def apply_to_deck(deck: plr.Deck, instrument: Dict[str, Any]) -> None:
    """Make PyLabRobot's deck match the instrument where its defaults do not (see the module docstring)."""
    if not instrument["head96"]["installed"]:
        return
    eject = instrument["head96"]["eject"]
    a1 = head96_a1(deck)
    if abs(a1.x - eject["x_mm"]) > MATCH_MM or abs(a1.y - eject["y_mm"]) > MATCH_MM:
        raise InstrumentError(
            f"PyLabRobot would initialize the 96 head at x {a1.x:.1f}, y {a1.y:.1f}, not at VENUS's x {eject['x_mm']}, "
            f"y {eject['y_mm']}. Its 96 waste model changed (another PyLabRobot version?): fix the deck before a run.")
    trash = deck.get_trash_area96()
    trash.location = Coordinate(trash.location.x, trash.location.y, trash.location.z + eject["z_mm"] - a1.z)


def real_deck_layout(instrument: Dict[str, Any], root: Path = ROOT) -> Path:
    """The VENUS layout of what is on the instrument's deck now."""
    return root / instrument["deck_layout"]["file"]


# --- The instrument as the simulated device ---

def firmware_configuration(deck_config: Dict[str, Any], root: Path = ROOT) -> Optional[str]:
    """The instrument's firmware report, which the simulated STAR device answers as this instrument does (its
    channels, the 96 head, iSWAP, autoload, deck size, tip waste). None for a deck that names no instrument."""
    if not deck_config.get("instrument"):
        return None
    instrument = load_instrument(deck_config["instrument"], root)
    return str(root / instrument["firmware_configuration"])


def use(instrument: str = None, labware: str = None) -> None:
    """Point Precheck at other ground truth than the repo's default: an instrument file (config/instrument/
    <serial>.json: it names the firmware configuration, VENUS's deck template and the layout of the deck now) and
    a VENUS labware library (a `Labware` folder). Paths are relative to the repo root, or absolute."""
    global DEFAULT_INSTRUMENT
    if instrument:
        DEFAULT_INSTRUMENT = str(instrument)
        _load.cache_clear()
    if labware:
        from pipeline import deck_builder, venus_labware
        if not Path(ROOT / labware).is_dir():
            raise InstrumentError(f"{labware} is not a folder: give VENUS's Labware folder.")
        venus_labware.LIBRARY = deck_builder.LIBRARY = str(labware)
        for cached in (venus_labware._index, deck_builder._catalog, deck_builder._category_names):
            cached.cache_clear()
