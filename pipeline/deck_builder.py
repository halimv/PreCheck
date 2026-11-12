"""Stage 0b: Deck builder (the labware a protocol needs -> a deck from the lab's labware library).

The drafter names each labware a protocol needs by its role in the protocol (IR names such as `diluent`,
`culture`, `dilution_plate`) and says what it must be, in the IR's `labware` section:

    "culture": {"kind": "tube", "min_capacity_ul": 5000, "description": "overnight culture"}

Kinds: tip_rack (`tip_volume_ul`, `filter`), plate (`wells`, `min_capacity_ul` per well), reservoir and tube
(`min_capacity_ul`), waste. This stage finds real labware for each in VENUS's library (config/Labware), trying:

1. labware on the STARlet's deck now (the instrument's .lay) that fits and no other need has taken;
2. labware from the library in a free site of a carrier that is on the deck (or that this stage added);
3. labware from the library on a carrier from the library, placed on free rails.

Within each, labware the pipeline has checked against PyLabRobot (config/venus_labware.json) comes first, then the
smallest that is big enough. A need nothing fits comes back unresolved, with the closest options, for the drafter to
send back to Claude.

The result is a deck config whose labware IDs are the IR names (everything else on the .lay stays, under its VENUS
ID), and a mapping from each IR name to what was chosen: the VENUS type and file, the barcode mask VENUS expects on
the labware and on its carrier (`Barcode.Value`, `*` for any character), the part number, the carrier, its rails and
the position, and what the operator has to do (nothing, place the labware, or add the carrier too).
"""

import functools
import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from pipeline.deck import ROOT, build_deck, make_resource
from pipeline.instrument import load_instrument
from pipeline.setup_guide import nominal_tip_ul
from pipeline.venus_labware import (LIBRARY, VenusLabwareError, carrier_sites, container_capacity, container_offset,
                                    find, read_cfg)
from pipeline.venus_layout import RAIL_MM, load_venus_map

NEED_KINDS = ("tip_rack", "plate", "reservoir", "tube", "waste")
DECK_KIND = {"tip_rack": "tip_rack", "plate": "plate", "reservoir": "container", "tube": "container", "waste": "trash"}
TIP_CATEGORY = "165"  # VENUS's "ML STAR Tips" (config/Labware/ML_STAR-Category.dat)
CARRIER_LENGTH_MM = 497.0  # a carrier, or a sample-tube rack that sits on the rails like one
PLATE_FOOTPRINT_MM = (127.5, 85.5)
INSTRUMENT_PARTS = re.compile(r"lid|teaching|verification|downholder|needle|waste|wash", re.IGNORECASE)  # not labware
CARRIER_CATEGORY = {"tip_rack": "Tip carriers", "plate": "Plate carriers", "reservoir": "Reagent carriers"}
FIT_MM = 2.0  # a rack fits a carrier site whose footprint is within this of its own


class DeckBuildError(ValueError):
    pass


# --- the catalog: VENUS's library, searchable ---

@functools.lru_cache(maxsize=2)
def _category_names(root: str) -> Dict[str, Tuple[str, str]]:
    """{category id: (parent id, name)} from VENUS's category files."""
    out: Dict[str, Tuple[str, str]] = {}
    for path in (Path(root) / LIBRARY).glob("*Category.dat"):
        for line in path.read_text(encoding="latin-1").splitlines():
            parts = line.split(",")
            if len(parts) >= 3 and parts[0].isdigit():
                out[parts[0]] = (parts[1], parts[2].strip())
    return out


def _categories_of(pairs: Dict[str, str], root: Path) -> List[str]:
    """The definition's VENUS category ids with their ancestors."""
    names = _category_names(str(root))
    ids = [v for k, v in pairs.items() if re.fullmatch(r"Category\.\d+\.Id", k)]
    out = []
    for cid in ids:
        while cid in names and cid not in out:
            out.append(cid)
            cid = names[cid][0]
    return out


def _classify(path: Path, pairs: Dict[str, str], categories: List[str]) -> Optional[str]:
    """What a definition is, from its structure (VENUS's categories are missing for many)."""
    if path.suffix.lower() == ".tml":
        return "carrier" if any(re.fullmatch(r"Site\.\d+\.Id", k) for k in pairs) else None
    if TIP_CATEGORY in categories:
        return "tip_rack"
    if INSTRUMENT_PARTS.search(path.stem) or "lid" in pairs.get("Description", "").lower() \
            or path.parent.name.upper() == "CORE":
        return None
    try:
        rows, columns = int(pairs.get("Rows", 1)), int(pairs.get("Columns", 1))  # VENUS leaves 1 x 1 unwritten
        dx, dy = float(pairs["Dim.Dx"]), float(pairs["Dim.Dy"])
    except (KeyError, ValueError):
        return None
    if abs(dy - CARRIER_LENGTH_MM) < 5 and rows * columns > 1:
        return "tube_rack"
    if (rows, columns) == (8, 12) and abs(dx - PLATE_FOOTPRINT_MM[0]) < 3 and abs(dy - PLATE_FOOTPRINT_MM[1]) < 3:
        return "plate"
    if rows * columns == 1 and dy < CARRIER_LENGTH_MM - 5:
        return "reservoir"
    return None


def _property(pairs: Dict[str, str], name: str) -> Optional[str]:
    n = next((m.group(1) for k, v in pairs.items() if v == name and (m := re.fullmatch(r"Property\.(\d+)", k))), None)
    return pairs.get(f"PropertyValue.{n}") if n else None


def _part_number(description: str) -> Optional[str]:
    m = re.search(r"\b(?:PN|P/N|Cat\.?\s*No\.?)\s*:?\s*([A-Za-z0-9-]+)", description)
    return m.group(1) if m else None


def _tracks(pairs: Dict[str, str]) -> int:
    width = _property(pairs, "MlStarCarWidthAsT")
    return int(width) if width and width.isdigit() else max(1, math.ceil(float(pairs["Dim.Dx"]) / RAIL_MM - 0.05))


@functools.lru_cache(maxsize=2)
def _catalog(root: str) -> Tuple[Dict[str, Any], ...]:
    base = Path(root)
    library = base / LIBRARY
    checked = {spec["venus"].lower(): (t, spec) for t, spec in load_venus_map(base)["labware"].items() if spec.get("venus")}
    names = _category_names(root)
    entries = []
    for path in sorted(p for p in library.rglob("*") if p.suffix.lower() in (".rck", ".tml")):
        if re.search(r"nimbus|vantage", str(path.relative_to(library)), re.IGNORECASE):
            continue
        try:
            pairs = read_cfg(path)
        except (VenusLabwareError, OSError, UnicodeDecodeError):
            continue
        categories = _categories_of(pairs, base)
        kind = _classify(path, pairs, categories)
        if kind is None:
            continue
        category = " / ".join(names[c][1] for c in reversed(categories)) if categories else ""
        suffix = path.suffix.lower()
        venus_file = str(path.relative_to(library)).replace("\\", "/")
        description = pairs.get("Description", "")
        mapped = checked.get(venus_file.lower())
        entry = {"venus_type": path.stem, "venus_file": venus_file, "category": category, "kind": kind,
                 "description": description, "barcode": pairs.get("Barcode.Value", ""),
                 "part_number": _part_number(description), "checked": mapped is not None,
                 "size": [float(pairs.get(f"Dim.D{a}", 0)) for a in "xyz"]}
        if kind == "carrier":
            try:
                sites = carrier_sites(pairs)
            except (KeyError, ValueError):
                continue
            if not sites:
                continue
            entry.update(sites=sites, tracks=_tracks(pairs), label=_property(pairs, "MlStarCarLabelName"),
                         factory=mapped[1]["factory"] if mapped else None, build=mapped[1]["build"] if mapped else "venus")
        elif kind == "tip_rack":
            if not mapped:  # a .rck has the rack, not the tip model PyLabRobot pipettes with
                continue
            factory = mapped[1]["factory"]
            entry.update(factory=factory, build="plr", tip_volume_ul=nominal_tip_ul(factory, 0), filter="filter" in factory)
        else:
            try:
                ctr = read_cfg(find(pairs["Cntr.1.file"], base))
                capacity = container_capacity(ctr)
                rows, columns = int(pairs.get("Rows", 1)), int(pairs.get("Columns", 1))
            except (KeyError, ValueError, VenusLabwareError, OSError):
                continue
            if pairs.get("SingleCntr", "1") != "1" or capacity <= 0:
                continue
            if kind == "plate" and (rows, columns) != (8, 12):
                continue
            if kind == "reservoir" and rows * columns != 1:
                continue
            entry.update(capacity_ul=round(capacity, 1), rows=rows, columns=columns,
                         factory=(mapped[1]["factory"] if mapped and mapped[1]["build"] == "plr" else path.stem),
                         build=mapped[1]["build"] if mapped else "venus")
            if kind == "reservoir":
                entry["offset_mm"] = [round(v, 3) for v in container_offset(pairs, ctr)]
            if kind == "tube_rack":
                entry["tracks"] = _tracks(pairs)
                entry["positions"] = rows * columns
        entries.append(entry)
    return tuple(entries)


def catalog(root: Path = ROOT) -> List[Dict[str, Any]]:
    """Every ML_STAR carrier, tip rack, 96-well plate, single-container reservoir and sample-tube rack in VENUS's
    library that a deck can be built from."""
    return list(_catalog(str(root)))


# --- matching needs ---

def need_errors(needs: Any) -> List[str]:
    """Problems with the IR's `labware` section itself."""
    if not isinstance(needs, dict) or not needs:
        return ["'labware' must be an object naming every labware the steps use"]
    errors = []
    for name, need in needs.items():
        if not isinstance(need, dict) or need.get("kind") not in NEED_KINDS:
            errors.append(f"labware '{name}' needs a kind, one of {', '.join(NEED_KINDS)}")
    return errors


def fits(need: Dict[str, Any], entry: Dict[str, Any]) -> bool:
    kind = need["kind"]
    if kind == "tip_rack":
        return (entry["kind"] == "tip_rack" and entry["tip_volume_ul"] >= float(need.get("tip_volume_ul", 0))
                and ("filter" not in need or bool(need["filter"]) == entry["filter"]))
    want = {"plate": "plate", "reservoir": "reservoir", "tube": "tube_rack"}.get(kind)
    return (entry["kind"] == want and entry["capacity_ul"] >= float(need.get("min_capacity_ul", 0))
            and (kind != "plate" or int(need.get("wells", 96)) == entry["rows"] * entry["columns"]))


def _rank(entry: Dict[str, Any]) -> Tuple:
    size = entry.get("tip_volume_ul", entry.get("capacity_ul", 0))
    return (not entry["checked"], size, entry["venus_type"])


def closest(need: Dict[str, Any], entries: List[Dict[str, Any]], n: int = 5) -> List[str]:
    """Library options of the need's kind nearest in size, for Claude to choose from."""
    want = {"tip_rack": "tip_rack", "plate": "plate", "reservoir": "reservoir", "tube": "tube_rack"}[need["kind"]]
    target = float(need.get("tip_volume_ul") or need.get("min_capacity_ul") or 0)
    pool = [e for e in entries if e["kind"] == want]
    pool.sort(key=lambda e: (abs(e.get("tip_volume_ul", e.get("capacity_ul", 0)) - target), not e["checked"]))
    out = []
    for e in pool[:n]:
        size = (f"{e['tip_volume_ul']:g} uL tips{' with filter' if e['filter'] else ''}" if want == "tip_rack"
                else f"{e['capacity_ul'] / 1000:g} mL" if e["capacity_ul"] >= 1000 else f"{e['capacity_ul']:g} uL")
        out.append(f"{e['venus_type']} ({size}{'; ' + e['description'] if e['description'] else ''})")
    return out


# --- the deck ---

@dataclass
class Resolution:
    deck_config: Dict[str, Any]
    mapping: Dict[str, Any]
    unresolved: Dict[str, str] = field(default_factory=dict)  # IR name -> why, with the closest options

    @property
    def ok(self) -> bool:
        return not self.unresolved

    def feedback(self) -> str:
        return "\n".join(f"- {name}: {why}" for name, why in self.unresolved.items())


class _Deck:
    """The deck as it is being built: the .lay's carriers and labware, then what this stage adds."""

    def __init__(self, base: Dict[str, Any], entries: List[Dict[str, Any]], rails: int):
        self.base, self.rails = base, rails
        self.by_type = {e["venus_type"].lower(): e for e in entries}
        self.carriers: List[Dict[str, Any]] = [dict(c) for c in base["carriers"]]
        self.labware: Dict[str, Dict[str, Any]] = {lid: dict(s) for lid, s in base["labware"].items()}
        self.taken: Dict[str, str] = {}  # .lay labware ID -> IR name using it
        self.added_carriers: set = set()

    def entry(self, spec: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return self.by_type.get(str(spec.get("venus_type", spec.get("factory", ""))).lower())

    def used_rails(self) -> List[Tuple[int, int]]:
        spans = []
        for c in self.carriers:
            e = self.entry(c)
            spans.append((c["rails"], c["rails"] + (e["tracks"] if e else _tracks_of(c)) - 1))
        return spans

    def free_rails(self, tracks: int) -> Optional[int]:
        spans = self.used_rails()
        for start in range(1, self.rails - tracks + 2):
            if all(start + tracks - 1 < lo or start > hi for lo, hi in spans):
                return start
        return None

    def free_sites(self, carrier: Dict[str, Any]) -> List[Tuple[int, Dict[str, Any]]]:
        """(PLR site, VENUS site) of a carrier's empty sites, rear-most first."""
        e = self.entry(carrier)
        if e is None or e["kind"] != "carrier":
            return []
        used = {s["slot"] for s in self.labware.values() if s.get("carrier") == carrier["name"]}
        return [(i, site) for i, site in reversed(list(enumerate(e["sites"]))) if i not in used]


def _tracks_of(carrier: Dict[str, Any]) -> int:
    return max(1, round(make_resource(carrier, "c").get_size_x() / RAIL_MM))


def _carrier_rank(carrier: Dict[str, Any], need_kind: str) -> Tuple:
    """Checked carriers first, then those VENUS files for this kind of labware, then the plain variant (no
    `_empty`, `_Container+Lid` suffixes), then the narrowest."""
    wanted = CARRIER_CATEGORY.get(need_kind, "")
    return (not carrier["checked"], wanted not in carrier["category"], len(carrier["venus_type"]), carrier["tracks"],
            carrier["venus_type"])


def _site_fits(site: Dict[str, Any], entry: Dict[str, Any]) -> bool:
    return abs(site["dx"] - entry["size"][0]) <= FIT_MM and abs(site["dy"] - entry["size"][1]) <= FIT_MM


def _labware_spec(entry: Dict[str, Any], carrier: str, slot: int, need_kind: str) -> Dict[str, Any]:
    spec = {"factory": entry["factory"], "kind": DECK_KIND[need_kind], "carrier": carrier, "slot": slot,
            "venus_type": entry["venus_type"]}
    if entry["build"] == "venus":
        spec.update(venus=entry["venus_file"], build="venus")
        if need_kind in ("reservoir", "tube"):
            spec["role"] = "container"
        if need_kind == "reservoir":
            spec["offset_mm"] = entry["offset_mm"]
    return spec


def _carrier_spec(entry: Dict[str, Any], name: str, rails: int) -> Dict[str, Any]:
    spec = {"name": name, "factory": entry.get("factory") or entry["venus_type"], "rails": rails,
            "venus_type": entry["venus_type"], "added": True}
    if entry.get("build", "venus") == "venus":
        spec.update(venus=entry["venus_file"], build="venus", role="carrier")
    return spec


def _record(entry: Dict[str, Any], carrier_entry: Optional[Dict[str, Any]], carrier: Dict[str, Any], slot: int,
            n_sites: int, action: str, need: Dict[str, Any], on_deck_as: Optional[str] = None) -> Dict[str, Any]:
    return {
        "need": need, "action": action, "on_deck_as": on_deck_as,
        "venus_type": entry["venus_type"], "venus_file": entry["venus_file"], "description": entry["description"],
        "barcode": entry["barcode"] or None, "part_number": entry["part_number"],
        "capacity_ul": entry.get("capacity_ul"), "tip_volume_ul": entry.get("tip_volume_ul"),
        "carrier": {"name": carrier["name"], "venus_type": carrier_entry["venus_type"] if carrier_entry else carrier["factory"],
                    "barcode": (carrier_entry or {}).get("barcode") or None,
                    "label": (carrier_entry or {}).get("label") or None,
                    "part_number": (carrier_entry or {}).get("part_number"),
                    "rails": carrier["rails"], "added": bool(carrier.get("added"))},
        "position": {"hamilton": n_sites - slot, "plr_site": slot},
    }


def resolve(needs: Dict[str, Dict[str, Any]], base_deck: Dict[str, Any], root: Path = ROOT,
            name: str = "protocol") -> Resolution:
    """A deck for `needs` built on `base_deck` (the instrument's .lay, as pipeline.deck reads it)."""
    entries = catalog(root)
    deck = _Deck(base_deck, entries, load_instrument(base_deck.get("instrument", "config/instrument/starlet_F553.json"),
                                                       root)["deck"]["rails"])
    mapping: Dict[str, Any] = {}
    unresolved: Dict[str, str] = {}
    renames: Dict[str, str] = {}  # .lay ID -> IR name

    for ir_name, need in needs.items():
        kind = need["kind"]
        if kind == "waste":
            trash = next(lid for lid, s in deck.labware.items() if s["kind"] == "trash")
            renames[trash] = ir_name
            mapping[ir_name] = {"need": need, "action": "on_deck", "venus_type": None,
                                "description": "the deck's tip waste", "barcode": None}
            continue
        # 1. on the deck now
        hit = None
        for lid, spec in deck.labware.items():
            e = deck.entry(spec)
            if lid in base_deck["labware"] and lid not in deck.taken and spec.get("carrier") and e and fits(need, e):
                if hit is None or _rank(e) < _rank(hit[1]):
                    hit = (lid, e)
        if hit:
            lid, e = hit
            deck.taken[lid] = ir_name
            renames[lid] = ir_name
            spec = deck.labware[lid]
            carrier = next(c for c in deck.carriers if c["name"] == spec["carrier"])
            ce = deck.entry(carrier)
            mapping[ir_name] = _record(e, ce, carrier, spec["slot"], len(ce["sites"]) if ce else 0, "on_deck", need, lid)
            continue
        candidates = sorted((e for e in entries if fits(need, e)), key=_rank)
        if not candidates:
            unresolved[ir_name] = (f"no {kind.replace('_', ' ')} in the library fits {_need_text(need)}. Closest: "
                                   + "; ".join(closest(need, entries) or ["none of that kind"]))
            continue
        placed = None
        if kind == "tube":
            placed = _place_tube(deck, candidates, ir_name, need)
        else:
            placed = _place_on_carrier(deck, candidates, entries, ir_name, need)
        if placed is None:
            unresolved[ir_name] = (f"{', '.join(e['venus_type'] for e in candidates[:3])} would fit {_need_text(need)}, "
                                   "but no carrier on the deck has a free site for it and no library carrier fits on the "
                                   "free rails")
            continue
        mapping[ir_name] = placed

    config = _config(deck, renames, base_deck, name)
    if not unresolved:
        try:
            build_deck(config)  # PyLabRobot refuses overlapping carriers and labware that does not fit its site
        except Exception as e:  # noqa: BLE001
            raise DeckBuildError(f"The built deck does not assemble in PyLabRobot: {type(e).__name__}: {e}") from e
    changes = [f"{n}: {m['action'].replace('_', ' ')}: {m['venus_type']} at {m['carrier']['name']} "
               f"(rail {m['carrier']['rails']}) position {m['position']['hamilton']}"
               for n, m in mapping.items() if m["action"] != "on_deck"]
    return Resolution(config, {"labware": mapping, "operator_changes": changes}, unresolved)


def _need_text(need: Dict[str, Any]) -> str:
    if need["kind"] == "tip_rack":
        return f"tips of at least {float(need.get('tip_volume_ul', 0)):g} uL" + (
            (" with filter" if need["filter"] else " without filter") if "filter" in need else "")
    size = f"at least {float(need.get('min_capacity_ul', 0)):g} uL"
    return f"{int(need.get('wells', 96))} wells of {size}" if need["kind"] == "plate" else size


def _place_on_carrier(deck: _Deck, candidates, entries, ir_name, need) -> Optional[Dict[str, Any]]:
    for e in candidates:
        # 2. a free site on a carrier that is on the deck (or that this stage added)
        for carrier in deck.carriers:
            for slot, site in deck.free_sites(carrier):
                if _site_fits(site, e):
                    deck.labware[ir_name] = _labware_spec(e, carrier["name"], slot, need["kind"])
                    ce = deck.entry(carrier)
                    action = "add_labware" if not carrier.get("added") else "add_carrier"
                    return _record(e, ce, carrier, slot, len(ce["sites"]), action, need)
        # 3. a library carrier on free rails
        for ce in sorted((c for c in entries if c["kind"] == "carrier" and any(_site_fits(s, e) for s in c["sites"])),
                         key=lambda c: _carrier_rank(c, need["kind"])):
            rails = deck.free_rails(ce["tracks"])
            if rails is None:
                continue
            carrier = _carrier_spec(ce, f"{ce['venus_type']}_{rails}", rails)
            deck.carriers.append(carrier)
            slot = next(i for i, s in reversed(list(enumerate(ce["sites"]))) if _site_fits(s, e))
            deck.labware[ir_name] = _labware_spec(e, carrier["name"], slot, need["kind"])
            return _record(e, ce, carrier, slot, len(ce["sites"]), "add_carrier", need)
    return None


def _place_tube(deck: _Deck, candidates, ir_name, need) -> Optional[Dict[str, Any]]:
    """A tube stands in a sample-tube rack, which sits on the rails like a carrier: a rack this stage already added
    takes the next tube, else a new rack goes on free rails."""
    for e in candidates:
        for carrier in deck.carriers:
            if carrier.get("added") and carrier.get("venus_type") == e["venus_type"]:
                used = {s["slot"] for s in deck.labware.values() if s.get("carrier") == carrier["name"]}
                free = [i for i in reversed(range(e["positions"])) if i not in used]
                if free:
                    deck.labware[ir_name] = _labware_spec(e, carrier["name"], free[0], "tube")
                    return _record(e, e, carrier, free[0], e["positions"], "add_carrier", need)
        rails = deck.free_rails(e["tracks"])
        if rails is None:
            continue
        carrier = _carrier_spec({**e, "build": "venus"}, f"{e['venus_type']}_{rails}", rails)
        deck.carriers.append(carrier)
        slot = e["positions"] - 1  # Hamilton position 1, the rear-most
        deck.labware[ir_name] = _labware_spec({**e, "build": "venus"}, carrier["name"], slot, "tube")
        return _record(e, e, carrier, slot, e["positions"], "add_carrier", need)
    return None


def _config(deck: _Deck, renames: Dict[str, str], base: Dict[str, Any], name: str) -> Dict[str, Any]:
    labware = {}
    for lid, spec in deck.labware.items():
        if lid in renames:
            labware[renames[lid]] = {**spec, "venus_id": lid}
        else:
            labware[lid] = spec
    return {
        "description": f"Deck for {name}, built by pipeline/deck_builder.py on {base.get('source', {}).get('venus_layout', 'the instrument deck')} "
                       "from VENUS's labware library. Labware IDs are the protocol's IR names; labware the protocol does "
                       "not use keeps its VENUS ID. Carriers marked `added` are not on the deck yet.",
        "deck": base["deck"], "instrument": base.get("instrument"), "source": base.get("source", {}),
        "carriers": deck.carriers, "labware": labware,
    }


def save(resolution: Resolution, decks_dir: Path, stem: str, root: Path = ROOT) -> Tuple[Path, Path]:
    """Write the deck config and the mapping (decks/<stem>.json, decks/<stem>.mapping.json)."""
    decks_dir.mkdir(parents=True, exist_ok=True)
    deck_path, mapping_path = decks_dir / f"{stem}.json", decks_dir / f"{stem}.mapping.json"
    deck_path.write_text(json.dumps(resolution.deck_config, indent=2) + "\n")
    rel = str(deck_path.relative_to(root)) if deck_path.is_relative_to(root) else str(deck_path)
    mapping_path.write_text(json.dumps({"deck_config": rel, **resolution.mapping}, indent=2) + "\n")
    return deck_path, mapping_path
