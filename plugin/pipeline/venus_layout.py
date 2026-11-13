"""Read a Venus deck layout (.lay) and check it against a PyLabRobot deck config.

PyLabRobot has no Venus layout format; this reads one, so a .lay can be the deck itself. A .lay is how the
lab describes the deck that is physically on the STARlet, so it is the thing to compare with before a run.

The file is Venus's binary HxCfgFile. The "DECKLAY,ML_STAR" section holds length-prefixed key/value
strings; each labware is `Labware.<n>.<field>`:

- `File`: its Venus definition (ML_STAR\\STF_L.rck); the file name without extension is its type.
- `Id`, and `Template`: the carrier it sits on, or `default` for the deck itself.
- `SiteId`: the position on that carrier, 1 = rear-most (a carrier's own is like `6T-7`: 6 tracks wide, rail 7).
- `TForm.3.X` / `TForm.3.Y` (mm): a carrier's front-left corner; a rack's or plate's A1.

What this module gives:

- `deck_config_from_lay`: the layout as a deck config, with config/venus_labware.json naming the
  PyLabRobot factory for each Venus type. Types it cannot map are reported, never guessed.
- `position_checks`: PyLabRobot's coordinates for each placed item against the .lay's, so a
  PyLabRobot definition whose geometry differs from the Venus one shows up as a difference in mm.
  Labware with the same footprint (a 1000 uL tip rack where 300 uL tips are) does not: only the
  Venus type -> factory map guards that.
- `compare_with_deck`: whether every labware a protocol uses is on the .lay deck where the protocol's
  deck config puts it (same carrier type and rails, same position, same labware type).
"""

import json
import re
import struct
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pylabrobot.resources as plr

from pipeline.deck import build_deck, make_resource

VENUS_LABWARE = "config/venus_labware.json"
RAIL_MM = 22.5
RAIL_1_X_MM = 100.0  # x of rail 1 on Hamilton STAR decks
TOLERANCE_MM = 0.5


class LayoutError(ValueError):
    pass


def read_lay(data: bytes) -> Dict[str, str]:
    """The key/value pairs of the DECKLAY section of a binary .lay."""
    start = data.find(b"DECKLAY,")
    if start < 1 or data.startswith(b"HxCfgFile"):
        raise LayoutError("Not a binary Venus deck layout: no DECKLAY section found. "
                          "Export the layout from Venus as a .lay file (the binary default).")
    pos = start - 1
    try:
        name_len = data[pos]
        pos += 1 + name_len
        _kind, count = struct.unpack_from("<HI", data, pos)
        pos += 6
        pairs: Dict[str, str] = {}
        for _ in range(count):
            key, pos = _string(data, pos)
            value, pos = _string(data, pos)
            pairs[key] = value
    except (IndexError, struct.error) as e:
        raise LayoutError(f"The layout file ends early or is damaged ({e}).") from e
    if not any(k.startswith("Labware.") for k in pairs):
        raise LayoutError("The layout has no labware entries.")
    return pairs


def _string(data: bytes, pos: int) -> Tuple[str, int]:
    n = data[pos]
    end = pos + 1 + n
    if end > len(data):
        raise IndexError("string runs past the end of the file")
    return data[pos + 1:end].decode("latin-1"), end


def lay_items(pairs: Dict[str, str]) -> List[Dict[str, Any]]:
    """One dict per labware: id, type, file, parent (None on the deck), site, x, y."""
    fields: Dict[int, Dict[str, str]] = {}
    for key, value in pairs.items():
        m = re.match(r"Labware\.(\d+)\.(.+)$", key)
        if m:
            fields.setdefault(int(m.group(1)), {})[m.group(2)] = value
    items = []
    for n in sorted(fields):
        f = fields[n]
        if "Id" not in f or "File" not in f:
            continue
        items.append({
            "id": f["Id"],
            "type": re.split(r"[\\/]", f["File"])[-1].rsplit(".", 1)[0],
            "file": f["File"],
            "parent": None if f.get("Template", "default") == "default" else f["Template"],
            "site": f.get("SiteId", ""),
            "x": float(f.get("TForm.3.X", "nan")),
            "y": float(f.get("TForm.3.Y", "nan")),
        })
    return items


def load_venus_map(root: Path) -> Dict[str, Any]:
    """config/venus_labware.json, checked against VENUS's library (pipeline/venus_labware.check_map)."""
    from pipeline.venus_labware import check_map
    venus_map = json.loads((root / VENUS_LABWARE).read_text())
    check_map(venus_map, root)
    return venus_map


def _placeable(spec: Dict[str, Any]) -> bool:
    return spec.get("build") == "venus" or bool(spec.get("factory"))


def _source(spec: Dict[str, Any], venus_type: str) -> Dict[str, Any]:
    """The deck-config fields that say how to build an item: a PyLabRobot factory, or its VENUS definition."""
    if spec.get("build") == "venus":
        return {"factory": spec.get("factory") or venus_type, "venus": spec["venus"], "build": "venus", "venus_type": venus_type}
    return {"factory": spec["factory"], "venus_type": venus_type}


def _rails(x: float) -> Optional[int]:
    r = (x - RAIL_1_X_MM) / RAIL_MM + 1
    return round(r) if abs(r - round(r)) < 0.05 else None


def deck_config_from_lay(pairs: Dict[str, str], venus_map: Dict[str, Any], name: str = "layout"
                         ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """(deck config, problems). Labware IDs are the Venus IDs. Every problem names the item it is about;
    a deck config with problems leaves those items out and must not be used for a run."""
    items = lay_items(pairs)
    types = venus_map["labware"]
    ignored_types = {t.lower() for t in venus_map["ignore"]["types"]}
    problems: List[Dict[str, Any]] = []
    deck_file = pairs.get("Deck", "")
    deck_class = venus_map["decks"].get(deck_file)
    if deck_class is None:
        problems.append({"id": deck_file, "problem": f"Unknown Venus deck '{deck_file}'.",
                         "fix": f"Add it under 'decks' in {VENUS_LABWARE}."})
        deck_class = "STARLetDeck"

    ignored = {i["id"] for i in items if i["type"].lower() in ignored_types}
    ignored |= {i["id"] for i in items if i["parent"] in ignored}
    carriers: Dict[str, Dict[str, Any]] = {}
    labware: Dict[str, Dict[str, Any]] = {}
    for item in items:
        if item["id"] in ignored:
            continue
        spec = types.get(item["type"])
        if spec is None:
            problems.append({"id": item["id"], "problem": f"Venus type '{item['type']}' ({item['file']}) is not in "
                             f"{VENUS_LABWARE}.", "fix": "Add it with its PyLabRobot factory, then load the layout again."})
            continue
        if not _placeable(spec):
            problems.append({"id": item["id"], "problem": f"'{item['type']}' has no PyLabRobot definition.",
                             "fix": spec.get("note", "") + f" Or set its VENUS file and \"build\": \"venus\" in {VENUS_LABWARE}."})
            continue
        if item["parent"] is None:
            if spec["kind"] != "carrier":
                problems.append({"id": item["id"], "problem": f"'{item['type']}' sits on the deck, not on a carrier."})
                continue
            rails = _rails(item["x"])
            if rails is None:
                problems.append({"id": item["id"], "problem": f"x = {item['x']:g} mm is not on a rail."})
                continue
            carriers[item["id"]] = {"name": item["id"], **_source(spec, item["type"]), "rails": rails}

    sites: Dict[str, int] = {c["name"]: len(make_resource(c, c["name"]).sites) for c in carriers.values()}
    for item in items:
        spec = types.get(item["type"])
        if item["id"] in ignored or item["parent"] is None or not spec or not _placeable(spec):
            continue
        if item["parent"] not in carriers:
            problems.append({"id": item["id"], "problem": f"Sits on '{item['parent']}', which is not a carrier "
                             "this import could place."})
            continue
        n_sites = sites[item["parent"]]
        if not item["site"].isdigit() or not 1 <= int(item["site"]) <= n_sites:
            problems.append({"id": item["id"], "problem": f"Position '{item['site']}' is not on a {n_sites}-position carrier."})
            continue
        labware[item["id"]] = {**_source(spec, item["type"]), "carrier": item["parent"],
                               "slot": n_sites - int(item["site"]), "kind": spec["kind"],
                               "venus_position": int(item["site"])}
    labware["waste"] = {"kind": "trash", "note": "The deck's built-in trash area."}

    config = {
        "description": f"Generated from the Venus layout {name} by pipeline/venus_layout.py. Labware IDs are the "
                       "Venus IDs. Starting reagent volumes live in the protocol IR.",
        "deck": deck_class,
        "source": {"venus_layout": name, "venus_deck": deck_file},
        "carriers": sorted(carriers.values(), key=lambda c: c["rails"]),
        "labware": labware,
    }
    return config, problems


def position_checks(pairs: Dict[str, str], deck_config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """PyLabRobot's position of each placed carrier, rack and plate (its A1) against the .lay's, in mm."""
    by_id = {i["id"]: i for i in lay_items(pairs)}
    deck, res = build_deck(deck_config)
    checks = []

    def add(item_id: str, what: str, plr_xy: Tuple[float, float], lay_xy: Tuple[float, float], only_x: bool = False):
        dx, dy = plr_xy[0] - lay_xy[0], 0.0 if only_x else plr_xy[1] - lay_xy[1]
        checks.append({"id": item_id, "what": what, "plr": [round(v, 2) for v in plr_xy], "lay": list(lay_xy),
                       "dx": round(dx, 2), "dy": round(dy, 2),
                       "ok": abs(dx) <= TOLERANCE_MM and abs(dy) <= TOLERANCE_MM})

    for spec in deck_config["carriers"]:
        carrier = next(c for c in deck.children if c.name == spec["name"])
        loc, lay = carrier.get_absolute_location(), by_id[spec["name"]]
        add(spec["name"], "carrier origin", (loc.x, loc.y), (lay["x"], lay["y"]))
    for lid, spec in deck_config["labware"].items():
        if spec["kind"] not in ("tip_rack", "plate") or lid not in by_id:
            continue
        a1 = res[lid].get_item("A1")
        c = a1.get_absolute_location() + a1.center()
        add(lid, "A1", (c.x, c.y), (by_id[lid]["x"], by_id[lid]["y"]))
    checks += height_checks(pairs, deck_config, deck, res)
    waste = next((i for i in by_id.values() if i["type"].lower() == "waste2"), None)
    if waste is not None:
        add("waste", "tip waste x", (deck.get_trash_area().get_absolute_location().x, 0.0), (waste["x"], 0.0), only_x=True)
    return checks


def height_checks(pairs: Dict[str, str], deck_config: Dict[str, Any], deck: Any, res: Dict[str, Any]) -> List[Dict[str, Any]]:
    """PyLabRobot's heights against VENUS's, in mm: each carrier's height on the deck, where a tip's top and end
    are (what a pickup is computed from) and where a plate well's cavity starts (what an aspirate is). VENUS's
    come from the layout itself (each item's ZTrans: its height on this deck) plus the labware's definition in
    the library: the rack's container base (.rck) and the container's depth (.ctr)."""
    from pipeline.venus_labware import ROOT, find, read_cfg

    types = json.loads((ROOT / VENUS_LABWARE).read_text())["labware"]
    lay_z, n = {}, 1
    while f"Labware.{n}.Id" in pairs:
        if pairs.get(f"Labware.{n}.ZTrans") not in (None, ""):
            lay_z[pairs[f"Labware.{n}.Id"]] = float(pairs[f"Labware.{n}.ZTrans"])
        n += 1
    checks = []

    def add(lid: str, what: str, plr_z: float, venus_z: float) -> None:
        dz = plr_z - venus_z
        checks.append({"id": lid, "what": what, "plr": [round(plr_z, 2)], "lay": [round(venus_z, 2)],
                       "dx": 0.0, "dy": 0.0, "dz": round(dz, 2), "ok": abs(dz) <= TOLERANCE_MM})

    for spec in deck_config["carriers"]:
        if spec["name"] in lay_z:
            carrier = next(c for c in deck.children if c.name == spec["name"])
            add(spec["name"], "carrier height", carrier.get_absolute_location().z, lay_z[spec["name"]])
    for lid, spec in deck_config["labware"].items():
        rack_file = spec.get("venus") or types.get(spec.get("venus_type"), {}).get("venus")
        if spec["kind"] not in ("tip_rack", "plate") or not rack_file or lid not in lay_z:
            continue
        rck = read_cfg(find(rack_file))
        ctr = read_cfg(find(rck["Cntr.1.file"]))
        base = lay_z[lid] + float(rck["Cntr.1.base"])  # the bottom of VENUS's container
        a1 = res[lid].get_item("A1")
        if spec["kind"] == "tip_rack":
            tip = a1.get_tip()
            end = tip.get_absolute_location().z
            add(lid, "tip top height", end + tip.get_size_z(), base + float(ctr["Depth"]))
            add(lid, "tip end height", end, base)
        else:
            add(lid, "well bottom height", a1.get_absolute_location().z + a1.material_z_thickness,
                base + float(ctr["BaseMM"]))
    return checks


def _placement(deck_config: Dict[str, Any], lid: str) -> Optional[Dict[str, Any]]:
    spec = deck_config["labware"].get(lid)
    if not spec or "carrier" not in spec:
        return None
    carrier = next(c for c in deck_config["carriers"] if c["name"] == spec["carrier"])
    return {"factory": spec["factory"], "carrier_factory": carrier["factory"], "rails": carrier["rails"], "slot": spec["slot"]}


def _describe(p: Dict[str, Any], n_sites: Optional[int] = None) -> str:
    where = f"PLR site {p['slot']}" + (f" (Hamilton position {n_sites - p['slot']})" if n_sites else "")
    return f"{p['factory']} on {p['carrier_factory']} at rail {p['rails']}, {where}"


def compare_with_deck(lay_deck: Dict[str, Any], protocol_deck: Dict[str, Any], used: List[str]) -> Dict[str, Any]:
    """Is each labware the protocol uses on the .lay deck at the same place? {"ok", "items", "extra"}."""
    lay_places = {lid: _placement(lay_deck, lid) for lid in lay_deck["labware"]}
    lay_places = {k: v for k, v in lay_places.items() if v}
    items, matched = [], set()
    for lid in sorted(used):
        spec = protocol_deck["labware"].get(lid, {})
        if spec.get("kind") == "trash":
            continue
        want = _placement(protocol_deck, lid)
        if want is None:
            items.append({"id": lid, "status": "not_checked", "detail": "Not on a carrier (on a machine); check it by hand."})
            continue
        n_sites = len(make_resource(next(c for c in protocol_deck["carriers"] if c["rails"] == want["rails"] and c["factory"] == want["carrier_factory"]), "c").sites)
        same = next((k for k, p in lay_places.items() if p == want and k not in matched), None)
        if same:
            matched.add(same)
            items.append({"id": lid, "status": "match", "venus_id": same, "expected": _describe(want, n_sites)})
            continue
        there = next((k for k, p in lay_places.items()
                      if p["rails"] == want["rails"] and p["slot"] == want["slot"]), None)
        elsewhere = [k for k, p in lay_places.items() if p["factory"] == want["factory"]]
        carrier = next((c for c in lay_deck["carriers"] if c["rails"] == want["rails"]), None)
        if there:
            detail = f"The layout has {there} ({_describe(lay_places[there])}) there."
        elif carrier:
            detail = (f"At rail {want['rails']} the layout has {carrier['factory']} ({carrier['name']}), with nothing "
                      "PyLabRobot can place at that position.")
        else:
            detail = f"The layout has no carrier at rail {want['rails']}."
        if elsewhere:
            detail += f" The same labware type is at: {', '.join(f'{k} ({_describe(lay_places[k])})' for k in elsewhere)}."
        items.append({"id": lid, "status": "different", "expected": _describe(want, n_sites), "detail": detail})
    extra = [k for k in lay_places if k not in matched]
    return {"ok": bool(items) and all(i["status"] == "match" for i in items), "items": items, "extra": extra}


def import_layout(data: bytes, name: str, root: Path) -> Dict[str, Any]:
    """Everything the Execute page shows for a .lay: its items, the deck config, problems and position checks."""
    pairs = read_lay(data)
    deck_config, problems = deck_config_from_lay(pairs, load_venus_map(root), name)
    return {
        "name": name,
        "venus_version": pairs.get("PhoenixVersion"),
        "deck_file": pairs.get("Deck"),
        "items": lay_items(pairs),
        "deck_config": deck_config,
        "problems": problems,
        "positions": position_checks(pairs, deck_config),
    }
