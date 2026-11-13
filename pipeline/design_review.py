"""What the scientist reviews before a protocol goes on: the design as numbers, and suggestions.

A protocol that passes the simulator is physically possible on this instrument; whether it is the experiment
the scientist meant is theirs to judge. `review` works the design out of the IR and the deck:

- labware: what real labware each name in the plan became, and where it sits;
- reagents: what is loaded, what the plan draws, what is left over;
- wells: what every plate column ends up holding: volume, and how much of each reagent (so a dilution reads as
  1:10, 1:100, ...), against the lab's dead-volume and fill limits (config/precheck_policy.json);
- tips and channels: how many tips are used, and which steps use fewer channels than the instrument has.

`suggestions` are design improvements, not errors: the simulator passes without them. They are things a person
watching the run would notice (one tip at a time into a trough that takes four, a reagent loaded far beyond what
is drawn, an aspirate per dispense where one would do).

    python -m pipeline.design_review healed/<name>.json
"""

import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from pipeline.deck import INSTRUMENT_DECK, ROOT, build_deck, deck_config_for

from pipeline.labware_limits import labware_limits, load_policy

ROWS = "ABCDEFGH"
SHALLOW_MM = 2.0  # a rule of thumb, not a measurement: review it with the scientist for each container
Mix = Dict[str, float]  # reagent -> uL


def _take(mix: Mix, volume: float) -> Mix:
    """Remove `volume` uL of a mixture, in proportion; returns what was removed."""
    total = sum(mix.values())
    if total <= 0 or volume <= 0:
        return {}
    share = min(volume / total, 1.0)
    out = {k: v * share for k, v in mix.items()}
    for k, v in out.items():
        mix[k] -= v
    return out


def _add(mix: Mix, other: Mix) -> None:
    for k, v in other.items():
        mix[k] = mix.get(k, 0.0) + v


def trace_mixtures(protocol: Dict[str, Any], kinds: Dict[str, str]) -> Tuple[Dict[Any, Mix], Dict[str, float]]:
    """Follow every microliter through the steps. Returns ({container: mixture}, {labware: uL drawn}); a plate's
    containers are (labware, column, row), anything else is its labware name."""
    names = protocol.get("reagents", {})
    where: Dict[Any, Mix] = {lid: {names.get(lid, lid): float(v)}
                             for lid, v in (protocol.get("initial_volumes_ul") or {}).items()}
    tips: Dict[int, Mix] = {}
    drawn: Dict[str, float] = {}

    def spot(labware: str, column: Optional[int], ch: int) -> Any:
        return (labware, column, ch) if kinds.get(labware) == "plate" else labware

    for s in protocol.get("steps", []):
        action, labware, volume = s.get("action"), s.get("labware"), float(s.get("volume_ul") or 0)
        for ch in s.get("channels", [0]):
            if action == "tips_off":
                tips.pop(ch, None)
            elif action == "aspirate":
                _add(tips.setdefault(ch, {}), _take(where.setdefault(spot(labware, s.get("column"), ch), {}), volume))
                drawn[labware] = drawn.get(labware, 0.0) + volume
            elif action == "dispense":
                _add(where.setdefault(spot(labware, s.get("column"), ch), {}), _take(tips.setdefault(ch, {}), volume))
            elif action == "empty":
                where[spot(labware, s.get("column"), ch)] = {}
    return where, drawn


def _position(resource: Any, spec: Dict[str, Any]) -> Any:
    """The carrier position as Hamilton counts it (1 = rear-most); deck configs count sites from the front."""
    if "venus_position" in spec:
        return spec["venus_position"]
    sites = getattr(getattr(resource.parent, "parent", None), "sites", None)
    return len(sites) - spec["slot"] if sites and "slot" in spec else spec.get("slot")


def _fit(resource: Any, pitch: float) -> int:
    """How many channels fit side by side in a container (they spread along y, `pitch` mm apart)."""
    return max(1, math.floor(resource.get_size_y() / pitch))


def review(protocol: Dict[str, Any], deck_config: Dict[str, Any], root: Path = ROOT) -> Dict[str, Any]:
    kinds = {lid: spec["kind"] for lid, spec in deck_config["labware"].items()}
    _, res = build_deck(deck_config)
    limits = labware_limits(deck_config, root).get("plates", {})
    carriers = {c["name"]: c for c in deck_config["carriers"]}
    used = {s.get("labware") for s in protocol.get("steps", [])}
    where, drawn = trace_mixtures(protocol, kinds)

    labware = []
    for lid, spec in deck_config["labware"].items():
        if lid not in used:
            continue
        carrier = carriers.get(spec.get("carrier"))
        labware.append({
            "name": lid, "kind": spec["kind"], "type": spec.get("venus_type") or spec.get("factory") or "tip waste",
            "where": (f"{carrier.get('venus_type') or carrier['factory']} at rail {carrier['rails']}, "
                      f"position {_position(res[lid], spec)}") if carrier else "the deck's tip waste",
            "holds": protocol.get("reagents", {}).get(lid),
        })

    reagents = []
    for lid, loaded in (protocol.get("initial_volumes_ul") or {}).items():
        needed = drawn.get(lid, 0.0)
        reagents.append({"labware": lid, "reagent": protocol.get("reagents", {}).get(lid, lid), "loaded_ul": loaded,
                         "drawn_ul": round(needed, 1), "left_ul": round(loaded - needed, 1),
                         "capacity_ul": round(getattr(res.get(lid), "max_volume", 0) or 0, 1) or None})

    wells = []
    plates = sorted({k[0] for k in where if isinstance(k, tuple)})
    for plate in plates:
        rule = limits.get(plate, {}).get("well_specifications", {}).get("well_volume_range", {})
        columns = sorted({k[1] for k in where if isinstance(k, tuple) and k[0] == plate})
        for column in columns:
            rows = {k[2]: m for k, m in where.items() if isinstance(k, tuple) and k[:2] == (plate, column)}
            totals = [sum(m.values()) for m in rows.values()]
            first = rows[min(rows)]
            total = sum(first.values())
            flags = []
            if rule and max(totals) > rule["max_ul"] + 1e-6:
                flags.append(f"above the {rule['max_ul']:g} uL fill limit")
            if rule and 0 < min(totals) < rule["min_ul"] - 1e-6:
                flags.append(f"below the {rule['min_ul']:g} uL dead volume: it cannot all be drawn back out")
            wells.append({
                "plate": plate, "column": column, "rows": "".join(ROWS[r] for r in sorted(rows)),
                "volume_ul": round(min(totals), 2) if abs(max(totals) - min(totals)) < 0.01
                else [round(min(totals), 2), round(max(totals), 2)],
                "contents": {k: {"ul": round(v, 3) if v >= 1 else float(f"{v:.2g}"), "dilution": (round(total / v, 1) if v > 0 else None)}
                             for k, v in sorted(first.items(), key=lambda kv: -kv[1]) if v > 1e-9} if total > 0 else {},
                "flags": flags,
            })

    tip_steps = [s for s in protocol.get("steps", []) if s.get("action") == "tips_on"]
    racks: Dict[str, List[int]] = {}
    for s in tip_steps:
        racks.setdefault(s["labware"], []).append(s.get("column"))
    n_channels = getattr(next(iter(res.values())), "num_channels", None) or 8
    policy = load_policy(root)["plates"]
    return {
        "protocol": protocol.get("protocol_name"),
        "deck": protocol.get("deck_config") or INSTRUMENT_DECK,
        "assumptions": protocol.get("assumptions", []),
        "labware": labware,
        "reagents": reagents,
        "wells": wells,
        "limits": {plate: limits[plate]["well_specifications"]["well_volume_range"] for plate in plates if plate in limits},
        "policy": policy,
        "tips": {"used": sum(len(s.get("channels", [0])) for s in tip_steps),
                 "columns": {rack: sorted(c for c in cols if c is not None) for rack, cols in racks.items()}},
        "steps": len(protocol.get("steps", [])),
        "channels": n_channels,
    }


def suggestions(protocol: Dict[str, Any], deck_config: Dict[str, Any], root: Path = ROOT) -> List[Dict[str, Any]]:
    """Design improvements the simulator does not ask for. Each is {"id", "title", "detail", "steps", "request"};
    `request` is the change in words, ready to hand to a revision."""
    _, res = build_deck(deck_config)
    kinds = {lid: spec["kind"] for lid, spec in deck_config["labware"].items()}
    pitch = 9.0
    if deck_config.get("instrument"):
        from pipeline.instrument import load_instrument
        pitch = float(load_instrument(deck_config["instrument"], root)["channels"]["min_pitch_mm"])
    steps = protocol.get("steps", [])
    out: List[Dict[str, Any]] = []

    # 1. Runs of single-channel steps on one container that takes more channels at once.
    i = 0
    while i < len(steps):
        s = steps[i]
        run = [s]
        if s.get("action") in ("aspirate", "dispense") and kinds.get(s.get("labware")) == "container":
            while (i + len(run) < len(steps)
                   and all(steps[i + len(run)].get(k) == s.get(k) for k in ("action", "labware", "volume_ul"))):
                run.append(steps[i + len(run)])
            channels = sorted(ch for r in run for ch in r.get("channels", [0]))
            fit = _fit(res[s["labware"]], pitch)
            moves_now, moves_best = len(run), math.ceil(len(channels) / fit)
            if len(run) > 1 and fit > 1 and moves_best < moves_now and len(set(channels)) == len(channels):
                groups = [channels[n:n + fit] for n in range(0, len(channels), fit)]
                out.append({
                    "id": "channels_one_at_a_time", "steps": [r.get("step") for r in run],
                    "title": f"'{s['labware']}' takes {fit} channels at once, but steps {run[0].get('step')}-"
                             f"{run[-1].get('step')} go in with {max(len(r.get('channels', [0])) for r in run)} at a time",
                    "detail": f"{moves_now} separate {s['action']}s where {moves_best} would do: the container is "
                              f"{res[s['labware']].get_size_y():g} mm wide and the channels sit {pitch:g} mm apart.",
                    "request": f"Replace steps {run[0].get('step')}-{run[-1].get('step')} with {moves_best} "
                               f"{s['action']} step(s) on '{s['labware']}' of {s.get('volume_ul'):g} uL per channel, "
                               f"using channels {' then '.join(str(g) for g in groups)}.",
                })
        i += len(run)

    # 2. A reagent loaded far beyond what the plan draws.
    _, drawn = trace_mixtures(protocol, kinds)
    for lid, loaded in (protocol.get("initial_volumes_ul") or {}).items():
        needed = drawn.get(lid, 0.0)
        enough = math.ceil(needed * 1.2 / 50) * 50  # 20% over, rounded up to 50 uL
        if needed > 0 and loaded > max(2 * needed, enough + 500):
            out.append({
                "id": "reagent_overloaded", "steps": [],
                "title": f"'{lid}' is loaded with {loaded:g} uL but the plan draws {needed:g} uL",
                "detail": f"{loaded - needed:g} uL would be left over. About {enough:g} uL covers the plan with 20% to "
                          "spare; a container's own dead volume comes on top of that.",
                "request": f"Load {enough:g} uL in '{lid}' instead of {loaded:g} uL, if the container's dead volume allows.",
            })

    # 2b. A reagent that ends as a film too shallow to draw from. The simulator counts microliters; a tip needs depth.
    for lid, loaded in (protocol.get("initial_volumes_ul") or {}).items():
        to_height = getattr(res.get(lid), "compute_height_from_volume", None)
        left = loaded - drawn.get(lid, 0.0)
        if to_height is None or drawn.get(lid, 0.0) <= 0:
            continue
        try:
            start_mm, end_mm = to_height(loaded), to_height(max(left, 0.0))
        except Exception:
            continue
        if end_mm < SHALLOW_MM:
            out.append({
                "id": "liquid_too_shallow", "steps": [],
                "title": f"'{lid}' starts {start_mm:.1f} mm deep and ends {end_mm:.1f} mm deep",
                "detail": f"{loaded:g} uL spreads thin in this container. Below about {SHALLOW_MM:g} mm a tip draws air "
                          "or misses the liquid; the simulator checks volume, not depth. Load more, or use a narrower "
                          "container (a tube) for a small volume.",
                "request": f"Keep at least {SHALLOW_MM:g} mm of liquid in '{lid}' to the end of the run: load more, or "
                           "move this reagent to a container narrow enough for its volume.",
            })

    # 3. One aspirate per dispense from the same source with the same tips, where one aspirate could feed several.
    i = 0
    while i + 3 < len(steps):
        a, d = steps[i], steps[i + 1]
        pairs = []
        while (i + 2 * len(pairs) + 1 < len(steps)
               and steps[i + 2 * len(pairs)].get("action") == "aspirate"
               and steps[i + 2 * len(pairs) + 1].get("action") == "dispense"
               and all(steps[i + 2 * len(pairs)].get(k) == a.get(k) for k in ("labware", "column", "channels", "volume_ul"))
               and steps[i + 2 * len(pairs) + 1].get("volume_ul") == a.get("volume_ul")
               and steps[i + 2 * len(pairs) + 1].get("labware") == d.get("labware")
               and steps[i + 2 * len(pairs) + 1].get("labware") != a.get("labware")):
            pairs.append((steps[i + 2 * len(pairs)], steps[i + 2 * len(pairs) + 1]))
        if len(pairs) >= 2 and kinds.get(a.get("labware")) == "container":
            tip_ul = _tip_volume(protocol, res, a)
            per_trip = int(tip_ul // float(a["volume_ul"])) if tip_ul and a.get("volume_ul") else 1
            if per_trip >= 2:
                trips = math.ceil(len(pairs) / per_trip)
                out.append({
                    "id": "aspirate_per_dispense", "steps": [p[0].get("step") for p in pairs],
                    "title": f"{len(pairs)} trips to '{a['labware']}' for {a['volume_ul']:g} uL each, with {tip_ul:g} uL tips",
                    "detail": f"One aspirate could feed {per_trip} dispenses, so {trips} trip(s) would do instead of "
                              f"{len(pairs)}. Multi-dispensing is less accurate than one aspirate per dispense (the "
                              "first and last shots differ), so this is a trade of time against precision.",
                    "request": f"Fill steps {pairs[0][0].get('step')}-{pairs[-1][1].get('step')} by multi-dispensing: "
                               f"aspirate enough for up to {per_trip} dispenses at a time from '{a['labware']}'.",
                })
            i += 2 * len(pairs)
        else:
            i += 1
    return out


def _tip_volume(protocol: Dict[str, Any], res: Dict[str, Any], step: Dict[str, Any]) -> Optional[float]:
    """The volume of the tips mounted at `step` (from the last tips_on before it)."""
    rack = None
    for s in protocol.get("steps", []):
        if s is step:
            break
        if s.get("action") == "tips_on":
            rack = s.get("labware")
    try:
        return float(res[rack].get_item("A1").get_tip().maximal_volume)
    except Exception:
        return None


def render(r: Dict[str, Any], hints: Optional[List[Dict[str, Any]]] = None) -> str:
    """The review as text for the terminal."""
    lines = [f"Design review: {r['protocol']}  ({r['steps']} steps, deck {r['deck']})", ""]
    if r["assumptions"]:
        lines.append("Assumptions made when drafting (check each one):")
        lines += [f"  - {a}" for a in r["assumptions"]]
        lines.append("")
    lines.append("Labware chosen:")
    for item in r["labware"]:
        holds = f"  holds: {item['holds']}" if item["holds"] else ""
        lines.append(f"  {item['name']:20s} {item['type']:26s} {item['where']}{holds}")
    lines += ["", "Reagents:"]
    for g in r["reagents"]:
        cap = f" of {g['capacity_ul']:g} uL capacity" if g["capacity_ul"] else ""
        lines.append(f"  {g['labware']:20s} load {g['loaded_ul']:g} uL{cap}; the plan draws {g['drawn_ul']:g} uL, "
                     f"leaving {g['left_ul']:g} uL  ({g['reagent']})")
    if r["policy"]:
        lines += ["", f"Limits (config/precheck_policy.json): dead volume {r['policy']['dead_volume_ul']:g} uL per well, "
                      f"fill to at most {r['policy']['max_fill_fraction']:.0%} of a well."]
    for plate, rule in r["limits"].items():
        cap = f" of {rule['capacity_ul']:g} uL" if rule.get("capacity_ul") else ""
        lines.append(f"  {plate}: usable {rule['min_ul']:g}-{rule['max_ul']:g} uL per well{cap}")
    lines += ["", "What each plate column ends up holding (per well):"]
    for w in r["wells"]:
        if not w["contents"]:
            lines.append(f"  {w['plate']} column {w['column']:>2} rows {w['rows']}: empty")
            continue
        vol = f"{w['volume_ul']:g}" if not isinstance(w["volume_ul"], list) else f"{w['volume_ul'][0]:g}-{w['volume_ul'][1]:g}"
        parts = ", ".join(f"{name[:40]} {c['ul']:.3g} uL" + (f" (1:{c['dilution']:,.4g})" if c["dilution"] >= 2 else "")
                          for name, c in w["contents"].items())
        flag = f"   <-- {'; '.join(w['flags'])}" if w["flags"] else ""
        lines.append(f"  {w['plate']} column {w['column']:>2} rows {w['rows']}: {vol} uL = {parts}{flag}")
    lines += ["", f"Tips: {r['tips']['used']} used; " + "; ".join(
        f"{rack} columns {cols[0]}-{cols[-1]}" if cols else rack for rack, cols in r["tips"]["columns"].items())]
    if hints is not None:
        lines += ["", "Suggestions (improvements, not errors):" if hints else "Suggestions: none."]
        for n, h in enumerate(hints, 1):
            lines += [f"  {n}. {h['title']}", f"     {h['detail']}"]
    return "\n".join(lines)


def main(argv: List[str]) -> int:
    if len(argv) != 1:
        print(__doc__)
        return 2
    protocol = json.loads(Path(argv[0]).read_text())
    deck_config = deck_config_for(protocol, ROOT)
    print(render(review(protocol, deck_config), suggestions(protocol, deck_config)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
