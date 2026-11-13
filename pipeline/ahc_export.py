"""Hand a deck to AHC: a deck config (and a protocol's starting volumes) written as an AHC layout.

AHC (github.com/xthomaswang/ahc) loads a Hamilton layout as carriers on tracks, each site holding a
PyLabRobot labware type, plus the liquids loaded before the run. A task folder keeps layouts in
.ahc/layouts/<name>.yaml; `load_layout(name=...)` loads one, and on a real robot the person still checks
the deck before anything moves. Exporting from here gives AHC the same deck Precheck simulated, or the deck
the instrument library's VENUS layout says is on the STARlet (`--instrument`).

AHC accepts only the types its own device description lists. That list is read from the installed AHC plugin
(INSTALLED_AHC), so Precheck and AHC cannot disagree about it; config/ahc_starlet.json is the copy used when AHC
is not installed. VENUS labware that AHC models under another name goes across by the `equivalents` declared in
that file, with what differs written into the layout. Anything with neither is reported and left out, and a
layout with anything left out is written only with `--partial`.

    python -m pipeline.ahc_export --protocol healed/<name>.json --out <task>/.ahc/layouts/<name>.yaml
    python -m pipeline.ahc_export --instrument --out <task>/.ahc/layouts/starlet_now.yaml --partial
"""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pylabrobot.resources as plr
import yaml

from pipeline.deck import deck_config_for, load_deck_config
from pipeline.instrument import load_instrument, real_deck_layout
from pipeline.venus_layout import deck_config_from_lay, load_venus_map, read_lay

ROOT = Path(__file__).resolve().parent.parent
AHC_TYPES = "config/ahc_starlet.json"


INSTALLED_AHC = ("marketplaces/*/src/ahc/devices/hamilton/starlet.md", "cache/*/ahc/*/src/ahc/devices/hamilton/starlet.md")


def installed_ahc_types(plugins: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """The layout types the installed AHC plugin's STARlet description lists, or None when AHC is not installed."""
    plugins = plugins or Path.home() / ".claude" / "plugins"
    for pattern in INSTALLED_AHC:
        for path in sorted(plugins.glob(pattern), reverse=True):
            try:
                layout = yaml.safe_load(path.read_text().split("---")[1])["layout"]
                labware = layout["labware"]
                return {"tracks": layout["tracks"], "carriers": list(layout["carriers"]), "source": str(path),
                        "labware": [t for group in labware.values() for t in group] if isinstance(labware, dict) else list(labware)}
            except (OSError, IndexError, KeyError, TypeError, yaml.YAMLError):
                continue
    return None


def load_ahc_types(root: Path = ROOT, plugins: Optional[Path] = None) -> Dict[str, Any]:
    """What AHC accepts: the installed AHC's own list, else the copy in config/ahc_starlet.json. The declared
    VENUS equivalents always come from the config file."""
    copy = json.loads((root / AHC_TYPES).read_text())
    return {**copy, "source": AHC_TYPES, **(installed_ahc_types(plugins) or {})}


def _ahc_name(name: Optional[str], accepted: List[str]) -> Optional[str]:
    return next((a for a in accepted if name and a.lower() == name.lower()), None)


def to_ahc_layout(deck_config: Dict[str, Any], ahc: Dict[str, Any], initial_volumes_ul: Optional[Dict[str, float]] = None
                  ) -> Tuple[Dict[str, Any], List[str], List[str]]:
    """(AHC layout, problems, warnings). Labware IDs become AHC labware names, so targets read the same in both.
    Problems are items left out. Warnings are items AHC builds from PyLabRobot's factory where Precheck builds
    them from VENUS (config/venus_labware.json), so AHC's geometry differs from VENUS's there."""
    problems: List[str] = []
    warnings: List[str] = []

    def venus_note(spec: Dict[str, Any], what: str) -> None:
        if spec.get("build") == "venus" and hasattr(plr, spec.get("factory") or ""):
            from pipeline.venus_labware import compare
            diffs = compare(spec["factory"], spec["venus"])
            if diffs:
                warnings.append(f"{what}: AHC builds PyLabRobot's {spec['factory']}, which differs from VENUS ({diffs[0]}"
                                + (f", and {len(diffs) - 1} more" if len(diffs) > 1 else "") + ")")
    carriers = []
    for spec in deck_config["carriers"]:
        kind = _ahc_name(spec["factory"], ahc["carriers"])
        if kind is None:
            problems.append(f"carrier {spec['name']} ({spec['factory']}, rail {spec['rails']}) is not a carrier AHC accepts")
            continue
        if not ahc["tracks"]["min"] <= spec["rails"] <= ahc["tracks"]["max"]:
            problems.append(f"carrier {spec['name']} is on rail {spec['rails']}, outside AHC's tracks")
            continue
        venus_note(spec, f"carrier {spec['name']}")
        sites = {}
        for lid, ls in sorted(deck_config["labware"].items(), key=lambda x: x[1].get("slot", 0)):
            if ls.get("carrier") != spec["name"]:
                continue
            labware = _ahc_name(ls["factory"], ahc["labware"])
            same = ahc.get("equivalents", {}).get(ls.get("venus_type"))
            if labware is None and same and _ahc_name(same["type"], ahc["labware"]):
                labware = _ahc_name(same["type"], ahc["labware"])
                warnings.append(f"{lid}: VENUS's {ls['venus_type']} goes to AHC as {labware} ({same['note']})")
            elif labware is None:
                problems.append(f"{lid} ({ls.get('venus_type') or ls['factory']}) on {spec['name']} is not labware AHC accepts")
                continue
            else:
                venus_note(ls, lid)
            sites[str(ls["slot"])] = {"name": lid, "type": labware}
        carriers.append({"name": spec["name"], "type": kind, "track": spec["rails"], "sites": sites})
    for lid, ls in deck_config["labware"].items():
        if "on" in ls:
            problems.append(f"{lid} sits on machine {ls['on']}; AHC's STARlet has no machines")
    placed = {s["name"] for c in carriers for s in c["sites"].values()}
    liquids = {}
    for lid, volume in (initial_volumes_ul or {}).items():
        if lid in placed:
            liquids[lid] = volume
        else:
            problems.append(f"the {volume:g} uL loaded in {lid} has no place in the AHC layout")
    layout: Dict[str, Any] = {"carriers": carriers}
    if liquids:
        layout["liquids"] = liquids
    return layout, problems, warnings


def write_layout(layout: Dict[str, Any], path: Path, source: str, problems: List[str],
                 warnings: Optional[List[str]] = None) -> None:
    lines = [f"# AHC layout exported by LLNL Capstone Precheck (pipeline/ahc_export.py) at {time.strftime('%Y-%m-%dT%H:%M:%S')}.",
             f"# Source: {source}"]
    if problems:
        lines.append("# NOT ON THIS LAYOUT (AHC would not know these are on the deck):")
        lines += [f"#   - {p}" for p in problems]
    if warnings:
        lines.append("# AHC'S MODEL DIFFERS FROM VENUS HERE (AHC uses PyLabRobot's definition):")
        lines += [f"#   - {w}" for w in warnings]
    lines.append("# Load it with load_layout(name=...); the deck check confirms it before anything moves.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n" + yaml.safe_dump(layout, sort_keys=False))


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Write a deck as an AHC layout (.ahc/layouts/<name>.yaml).")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--protocol", help="a protocol IR: its deck config and starting volumes")
    source.add_argument("--deck", help="a deck config (config/plr_deck*.json)")
    source.add_argument("--instrument", nargs="?", const="config/instrument/starlet_F553.json",
                        help="the deck the instrument library's VENUS layout says is on the STARlet")
    parser.add_argument("--out", required=True, help="where to write the layout, e.g. <task>/.ahc/layouts/<name>.yaml")
    parser.add_argument("--partial", action="store_true", help="write it even when some items cannot be exported")
    args = parser.parse_args(argv)

    volumes = None
    if args.protocol:
        protocol = json.loads(Path(args.protocol).read_text())
        deck_config, volumes, label = deck_config_for(protocol, ROOT), protocol.get("initial_volumes_ul"), args.protocol
        problems: List[str] = []
    elif args.deck:
        deck_config, label, problems = load_deck_config(args.deck), args.deck, []
    else:
        lay = real_deck_layout(load_instrument(args.instrument), ROOT)
        deck_config, lay_problems = deck_config_from_lay(read_lay(lay.read_bytes()), load_venus_map(ROOT), lay.name)
        label = f"{lay.relative_to(ROOT)} (instrument library)"
        problems = [f"{p['id']}: {p['problem']}" for p in lay_problems]
    layout, export_problems, warnings = to_ahc_layout(deck_config, load_ahc_types(ROOT), volumes)
    problems += export_problems
    for p in problems:
        print(f"not exported: {p}", file=sys.stderr)
    for w in warnings:
        print(f"warning: {w}", file=sys.stderr)
    if problems and not args.partial:
        print("Nothing written: AHC would not know about the items above. Use --partial to write the rest.", file=sys.stderr)
        return 1
    write_layout(layout, Path(args.out), label, problems, warnings)
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
