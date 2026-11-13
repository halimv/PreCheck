"""Deck setup checklist for a protocol that passed stages 1-3.

The deck is the protocol's deck config, usually the VENUS layout of the STARlet's deck. Before a
hardware run the operator has to make the physical STARlet match it, and load exactly the liquids
the simulation assumed. This module turns the deck config and the passing IR into that checklist:
carriers on their rails, labware in their positions, full tip racks, the reagent volumes from
`initial_volumes_ul`, and an empty plate. Only labware the protocol touches is listed.

Positions: PLR numbers carrier sites from the front (site 0 is front-most), Hamilton numbers them
from the back (position 1 is rear-most). Each item gives both.
"""

import re
from typing import Any, Dict, List, Optional, Set

from pipeline.deck import build_deck

RAIL_MM = 22.5


def nominal_tip_ul(factory: str, maximal_volume: float) -> float:
    """The tip size the rack is sold as (300 uL), from the PLR factory name. PLR's
    `maximal_volume` (360 uL for that tip) is the physical capacity, not the working volume."""
    m = re.search(r"(\d+)uL", factory)
    return float(m.group(1)) if m else maximal_volume


def _used_labware(protocol: Dict[str, Any]) -> List[str]:
    used = {s.get("labware") for s in protocol.get("steps", [])} | set(protocol.get("initial_volumes_ul", {}))
    used |= {s.get("waste") for s in protocol.get("steps", []) if s.get("waste")}
    return [lid for lid in used if lid]


def _tip_columns(protocol: Dict[str, Any], rack: str) -> List[int]:
    return sorted({s["column"] for s in protocol["steps"] if s.get("action") == "tips_on" and s.get("labware") == rack})


def _ul(v: float) -> str:
    return f"{v / 1000:g} mL" if v >= 1000 else f"{v:g} uL"


def setup_checklist(protocol: Dict[str, Any], deck_config: Dict[str, Any]) -> Dict[str, Any]:
    """{"items": [...], "deck": {...}} for the Execution page.

    Each item has id, group, title, detail and, where it applies, the carrier it is about (so
    the page can highlight it on the deck drawing).
    """
    deck, res = build_deck(deck_config, protocol.get("initial_volumes_ul"))
    used = set(_used_labware(protocol))
    reagents = protocol.get("reagents", {})
    volumes = protocol.get("initial_volumes_ul", {})
    labware = deck_config["labware"]

    items: List[Dict[str, Any]] = [{
        "id": "clear", "group": "Prepare",
        "title": "Clear the deck",
        "detail": "Remove every carrier and labware not listed below. Anything extra on the deck is a collision risk.",
    }]

    for spec in deck_config["carriers"]:
        carrier = next(c for c in deck.children if c.name == spec["name"])
        width = max(1, round(carrier.get_size_x() / RAIL_MM))
        on_it = [(lid, ls) for lid, ls in labware.items() if ls.get("carrier") == spec["name"]]
        needed = [(lid, ls) for lid, ls in on_it if lid in used]
        n_sites = len(carrier.sites)
        if not needed:
            continue
        last = spec["rails"] + width - 1
        rails = f"rail {spec['rails']}" + (f"-{last}" if last > spec["rails"] else "")
        group = f"{rails.capitalize()}: {spec['name']}"
        items.append({
            "id": f"carrier:{spec['name']}", "group": group, "carrier": spec["name"],
            "title": f"{spec['factory']} on {rails}",
            "detail": f"Slide the carrier in so its left edge sits on rail {spec['rails']} and it is pushed fully back "
                      f"until it latches.",
        })
        for lid, ls in sorted(needed, key=lambda x: x[1]["slot"]):
            items.append({**_labware_item(lid, ls, res[lid], spec["name"], n_sites, protocol, reagents, volumes),
                          "group": group})

    for lid, ls in labware.items():
        if lid in used and "on" in ls:
            items.append({
                "id": f"labware:{lid}", "group": "Heater-shakers",
                "title": f"{lid} on heater-shaker {ls['on']}",
                "detail": f"Place the plate ({ls['factory']}) on {ls['on']}, A1 at the back left.",
            })
        if lid in used and ls["kind"] == "trash":
            items.append({
                "id": f"waste:{lid}", "group": "Waste", "title": "Tip waste ready",
                "detail": "The deck's tip waste chute is in place and its bag/container has room for every tip this run uses.",
            })

    tips = sum(len(_tip_columns(protocol, lid)) * 8 for lid, ls in labware.items() if ls["kind"] == "tip_rack")
    items.append({
        "id": "final", "group": "Before you start",
        "title": "Front cover closed, nobody reaching into the deck",
        "detail": f"The run picks up {tips} tips and moves liquid in "
                  f"{len([s for s in protocol['steps'] if s.get('action') in ('aspirate', 'dispense')])} steps. "
                  "Keep a hand near the instrument's stop button.",
    })
    return {
        "items": items,
        "deck": deck_drawing(deck_config, used),
        "assumptions": protocol.get("assumptions", []),
    }


def deck_drawing(deck_config: Dict[str, Any], used: Set[str], labels: Optional[Dict[str, str]] = None,
                 added: Optional[Set[str]] = None) -> Dict[str, Any]:
    """What the Execute page draws: each carrier on its rails and the labware in its sites. `used`: labware the
    protocol touches; `labels`: names to show instead of labware IDs; `added`: labware (and the carriers marked
    `added`) the operator still has to place."""
    deck, _ = build_deck(deck_config)
    labels, added = labels or {}, added or set()
    drawn = []
    for spec in deck_config["carriers"]:
        carrier = next(c for c in deck.children if c.name == spec["name"])
        on_it = [(lid, ls) for lid, ls in deck_config["labware"].items() if ls.get("carrier") == spec["name"]]
        drawn.append({
            "name": spec["name"], "factory": spec.get("venus_type", spec["factory"]), "rails": spec["rails"],
            "width": max(1, round(carrier.get_size_x() / RAIL_MM)), "sites": len(carrier.sites),
            "needed": any(lid in used or lid in added for lid, _ in on_it), "added": bool(spec.get("added")),
            "labware": [{"id": labels.get(lid, lid), "slot": ls["slot"], "used": lid in used, "added": lid in added}
                        for lid, ls in on_it],
        })
    return {"num_rails": getattr(deck, "num_rails", 30), "carriers": drawn}


def _labware_item(lid, ls, resource, carrier, n_sites, protocol, reagents, volumes) -> Dict[str, Any]:
    slot = ls["slot"]
    where = f"position {n_sites - slot} of {n_sites} (Hamilton, counted from the back); PLR site {slot}, " \
            f"{'the front-most' if slot == 0 else f'{slot} from the front'}"
    item = {"id": f"labware:{lid}", "group": "Labware", "carrier": carrier, "labware": lid}
    if ls["kind"] == "tip_rack":
        cols = _tip_columns(protocol, lid)
        tip = resource.get_item("A1").get_tip()
        item["title"] = f"Full tip rack in {carrier} {where.split(';')[0]}"
        item["detail"] = (f"{lid}: a FULL rack of {nominal_tip_ul(ls['factory'], tip.maximal_volume):g} uL "
                          f"{'filtered ' if tip.has_filter else ''}tips ({ls['factory']}), A1 at the back left. "
                          f"The run uses column(s) {', '.join(map(str, cols)) or 'none'}. {where}.")
    elif ls["kind"] == "plate":
        item["title"] = f"Empty plate in {carrier} {where.split(';')[0]}"
        item["detail"] = f"{lid} ({ls['factory']}), empty, A1 at the back left, lid off. {where}."
    else:
        vol = volumes.get(lid)
        what = reagents.get(lid, "the reagent the protocol draws from it")
        item["title"] = (f"{_ul(vol)} of {what} in {lid}" if vol else f"{lid} in {carrier}")
        item["detail"] = (f"Place {lid} ({ls['factory']}) in {carrier} {where}. "
                          + (f"Load {_ul(vol)} of {what}; this is the volume the simulation checked "
                             "(a little extra is fine, less is not)." if vol else "Leave it empty."))
        item["volume_ul"] = vol
    return item
