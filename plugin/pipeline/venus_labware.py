"""VENUS's labware library (config/Labware) as the reference for labware geometry.

VENUS describes every carrier (.tml), rack or plate (.rck) and well shape (.ctr) as a text HxCfgFile. The lab's
copy of its library is config/Labware: the definitions the lab's VENUS runs on this STARlet use, so they are the
reference geometry. PyLabRobot ships its own definitions of many of the same items, written by hand from the
same sources; most agree with VENUS, some do not, and some labware it lacks.

- `read_cfg`, `find`, `carrier_sites`, `rack_geometry`: read the definitions.
- `compare`: a PyLabRobot factory against its VENUS definition (carrier sites; rack or plate footprint, A1, pitch).
- `make`: a PyLabRobot resource built from the VENUS definition: a carrier with VENUS's site positions (in the
  PyLabRobot factory's class, when there is one), or a plate with VENUS's footprint, wells and volume equations.

config/venus_labware.json says, per VENUS type, which PyLabRobot factory it is and whether decks build it from
PyLabRobot (`"build": "plr"`) or from VENUS (`"build": "venus"`); `check_map` verifies those choices when the map
loads. Tip racks stay PyLabRobot's: a .rck has the rack, not the tip PyLabRobot needs to pipette.
"""

import ast
import functools
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import pylabrobot.resources as plr
from pylabrobot.resources import Coordinate, Plate, Well
from pylabrobot.resources import Container
from pylabrobot.resources.carrier import Carrier, PlateCarrier, PlateHolder, ResourceHolder, create_resources
from pylabrobot.resources.utils import create_ordered_items_2d
from pylabrobot.resources.well import CrossSectionType, WellBottomType

from pipeline import paths

ROOT = Path(__file__).resolve().parent.parent
LIBRARY = str(paths.labware())  # the folder setup saved, or config/Labware; --labware overrides it for one run
TOLERANCE_MM = 0.15


class VenusLabwareError(ValueError):
    pass


def read_cfg(path: Path) -> Dict[str, str]:
    """The key/value pairs of a text HxCfgFile (`Key, "value",` lines)."""
    text = path.read_text(encoding="latin-1")
    if not text.startswith("HxCfgFile"):
        raise VenusLabwareError(f"{path} is not a text VENUS definition.")
    pairs = {}
    for line in text.splitlines():
        m = re.match(r'\s*([^,{}"]+?),\s*"(.*)",?\s*$', line)
        if m:
            pairs[m.group(1)] = m.group(2)
    return pairs


@functools.lru_cache(maxsize=4)
def _index(root: str) -> Dict[str, Path]:
    library = Path(root) / LIBRARY
    return {str(p.relative_to(library)).replace("\\", "/").lower(): p for p in library.rglob("*") if p.is_file()}


def find(venus_file: str, root: Path = ROOT) -> Path:
    """A VENUS path as files name it (ML_STAR\\STF_L.rck; any case, as on Windows) in the library."""
    key = re.sub(r"/+", "/", venus_file.replace("\\", "/")).lower().removeprefix("labware/")  # text files escape \ as \\
    path = _index(str(root)).get(key)
    if path is None:
        raise VenusLabwareError(f"{venus_file} is not in {LIBRARY}.")
    return path


def _f(pairs: Dict[str, str], key: str) -> float:
    return float(pairs[key])


def carrier_sites(pairs: Dict[str, str]) -> List[Dict[str, Any]]:
    """The carrier's sites, front-most first (PyLabRobot's order); `position` is VENUS's (1 = rear-most)."""
    numbers = sorted({int(m.group(1)) for k in pairs if (m := re.match(r"Site\.(\d+)\.Id$", k))})
    sites = [{"position": int(pairs[f"Site.{n}.Id"]), "x": _f(pairs, f"Site.{n}.X"), "y": _f(pairs, f"Site.{n}.Y"),
              "z": _f(pairs, f"Site.{n}.Z"), "dx": _f(pairs, f"Site.{n}.Dx"), "dy": _f(pairs, f"Site.{n}.Dy")}
             for n in numbers]
    return sorted(sites, key=lambda s: s["y"])


def rack_geometry(pairs: Dict[str, str]) -> Dict[str, Any]:
    """Footprint, grid and A1 of a rectangular rack or plate. VENUS's BndryX/BndryY locate the front-left
    item's center (column 1, last row); A1 is at the back."""
    rows, columns = int(pairs["Rows"]), int(pairs["Columns"])
    pitch = (_f(pairs, "Dx"), _f(pairs, "Dy"))
    return {"size": (_f(pairs, "Dim.Dx"), _f(pairs, "Dim.Dy"), _f(pairs, "Dim.Dz")), "rows": rows, "columns": columns,
            "pitch": pitch, "a1": (_f(pairs, "BndryX"), _f(pairs, "BndryY") + (rows - 1) * pitch[1])}


# --- PyLabRobot resources from VENUS definitions ---

def make(venus_file: str, name: str, factory: Optional[str] = None, role: Optional[str] = None,
         root: Path = ROOT) -> plr.Resource:
    """`role`: "carrier" (a .tml, or a sample-tube rack that sits on the rails), "plate", or "container" (the one
    container of a trough, or one tube of a tube rack). Without one: a .tml is a carrier, a .rck a plate."""
    path = find(venus_file, root)
    role = role or ("carrier" if path.suffix.lower() == ".tml" else "plate")
    if role == "carrier":
        return make_carrier(path, name, factory) if path.suffix.lower() == ".tml" else make_tube_carrier(path, name, root)
    if role == "plate":
        return make_plate(path, name, root)
    if role == "container":
        return make_container(path, name, root)
    raise VenusLabwareError(f"{venus_file}: unknown role {role!r}.")


def make_carrier(path: Path, name: str, factory: Optional[str] = None) -> Carrier:
    """VENUS's carrier, in the PyLabRobot factory's class and site class when it has one."""
    pairs = read_cfg(path)
    sites = carrier_sites(pairs)
    klass, site_klass = Carrier, ResourceHolder
    if factory and hasattr(plr, factory):
        template = getattr(plr, factory)(name=name)
        klass, site_klass = type(template), type(next(iter(template.sites.values())))
    elif sites and all(abs(s["dx"] - 127) < 2 and abs(s["dy"] - 86) < 2 for s in sites):
        klass, site_klass = PlateCarrier, PlateHolder  # plate footprint: plates sit on PlateHolders in PyLabRobot
    holders = create_resources(
        klass=site_klass,
        locations=[Coordinate(s["x"], s["y"], s["z"]) for s in sites],
        resource_size_x=[s["dx"] for s in sites], resource_size_y=[s["dy"] for s in sites],
        name_prefix=name, **({"pedestal_size_z": 0} if issubclass(site_klass, PlateHolder) else {}))
    return klass(name=name, size_x=_f(pairs, "Dim.Dx"), size_y=_f(pairs, "Dim.Dy"), size_z=_f(pairs, "Dim.Dz"),
                 sites=holders, model=f"venus:{path.stem}")


_ALLOWED = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.USub, ast.UAdd,
            ast.Constant, ast.Name, ast.Load)


def _compile_equation(text: str):
    tree = ast.parse(text.strip(), mode="eval")
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED) or (isinstance(node, ast.Name) and node.id != "h") \
                or (isinstance(node, ast.Constant) and not isinstance(node.value, (int, float))):
            raise VenusLabwareError(f"volume equation {text!r} is not arithmetic in h; it is not supported.")
    return compile(tree, "<EqnOfVol>", "eval")


def volume_equation(text: str) -> Callable[[float], float]:
    """A segment's volume (uL) as a function of the liquid height in it (mm), from VENUS's EqnOfVol, e.g.
    "h*128.7451" (a cylinder) or "h*h*(19.3208 - 1.0472*h)" (a round bottom). Only arithmetic in h is accepted."""
    code = _compile_equation(text)
    return lambda h: float(eval(code, {"__builtins__": {}}, {"h": h}))


class SegmentVolume:
    """A container's volume (uL) at a liquid height (mm): VENUS's segments, each [from mm, to mm, EqnOfVol].
    Plain data, so PyLabRobot can serialize the container (its visualizer sends every resource as JSON); the
    compiled equations are private and skipped."""

    def __init__(self, segments: List[List[Any]]):
        self.segments = segments
        self._equations = [volume_equation(text) for _, _, text in segments]

    def __call__(self, h: float) -> float:
        return sum(eqn(min(max(h - lo, 0.0), hi - lo)) for (lo, hi, _), eqn in zip(self.segments, self._equations))


class SegmentHeight:
    """The liquid height (mm) for a volume (uL): SegmentVolume inverted by bisection (volume rises with height)."""

    def __init__(self, volume: SegmentVolume):
        self.volume = volume

    def __call__(self, v: float) -> float:
        top = self.volume.segments[-1][1]
        if v > self.volume(top) + 1e-6:
            raise ValueError(f"{v:g} uL is more than the container holds ({self.volume(top):g} uL)")
        lo, hi = 0.0, top
        for _ in range(60):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if self.volume(mid) < v else (lo, mid)
        return (lo + hi) / 2


def _segments(ctr: Dict[str, str]) -> List[List[Any]]:
    """[from mm, to mm, EqnOfVol] per segment, bottom first."""
    out = [[_f(ctr, f"{n}.Min"), _f(ctr, f"{n}.Max"), ctr[f"{n}.EqnOfVol"]]
           for n in range(1, int(ctr.get("Segments", "0")) + 1)]
    if not out:
        raise VenusLabwareError("the container has no segments, so its volume is unknown.")
    return sorted(out, key=lambda seg: seg[0])


def volume_functions(ctr: Dict[str, str]) -> Tuple[SegmentVolume, SegmentHeight]:
    volume = SegmentVolume(_segments(ctr))
    return volume, SegmentHeight(volume)


def container_capacity(ctr: Dict[str, str]) -> float:
    volume, _ = volume_functions(ctr)
    return volume(_f(ctr, "Depth"))


def make_plate(path: Path, name: str, root: Path = ROOT) -> Plate:
    """A plate with VENUS's footprint, grid, well size and volume equations (one container type per plate)."""
    rck = read_cfg(path)
    ctr = _container_cfg(rck, root)
    geometry = rack_geometry(rck)
    volume, height = volume_functions(ctr)
    well_x, well_y, depth = _f(ctr, "Dim.Dx"), _f(ctr, "Dim.Dy"), _f(ctr, "Depth")
    first_x, first_y = _f(rck, "BndryX"), _f(rck, "BndryY")
    return Plate(
        name=name, size_x=geometry["size"][0], size_y=geometry["size"][1], size_z=geometry["size"][2],
        model=f"venus:{path.stem}",
        ordered_items=create_ordered_items_2d(
            Well, name_prefix=name, num_items_x=geometry["columns"], num_items_y=geometry["rows"],
            dx=first_x - well_x / 2, dy=first_y - well_y / 2, dz=_f(rck, "Cntr.1.base"),
            item_dx=geometry["pitch"][0], item_dy=geometry["pitch"][1],
            size_x=well_x, size_y=well_y, size_z=depth, material_z_thickness=_f(ctr, "BaseMM"),
            bottom_type=WellBottomType.UNKNOWN, cross_section_type=CrossSectionType.CIRCLE,
            max_volume=volume(depth), compute_volume_from_height=volume, compute_height_from_volume=height))


def _container_cfg(rck: Dict[str, str], root: Path) -> Dict[str, str]:
    if rck.get("SingleCntr", "1") != "1":
        raise VenusLabwareError("the rack has more than one container type; not supported yet.")
    return read_cfg(find(rck["Cntr.1.file"], root))


def access_positions(rck: Dict[str, str]) -> List[Tuple[float, float]]:
    """Where the channels go into a rack whose positions share one liquid (a trough: VENUS's ConnectedCtr), as
    (x, y) offsets in mm from position 1, in VENUS's order: position 1 is the rear-most, the one channel 1 uses.
    Empty for anything else."""
    if rck.get("ConnectedCtr") != "1":
        return []
    out, n = [], 1
    while f"{n}.ID" in rck and f"{n}.Y" in rck:
        out.append((float(rck.get(f"{n}.X", 0)), float(rck[f"{n}.Y"])))
        n += 1
    return out if len(out) > 1 else []


def container_offset(rck: Dict[str, str], ctr: Dict[str, str]) -> Tuple[float, float, float]:
    """Where a single-container rack's container sits in it (its front-left-bottom corner), for a trough placed in
    a carrier site. A trough with several access positions is one container spanning them all."""
    positions = access_positions(rck) or [(0.0, 0.0)]
    return (_f(rck, "BndryX") + min(x for x, _ in positions) - _f(ctr, "Dim.Dx") / 2,
            _f(rck, "BndryY") + min(y for _, y in positions) - _f(ctr, "Dim.Dy") / 2, _f(rck, "Cntr.1.base"))


def rack_capacity(rck: Dict[str, str], ctr: Dict[str, str]) -> float:
    """What a single-container rack holds: its container, times the access positions that share the liquid."""
    return container_capacity(ctr) * (len(access_positions(rck)) or 1)


def make_container(path: Path, name: str, root: Path = ROOT) -> Container:
    """The rack's container (a trough's, or one tube of a tube rack) with VENUS's size and volume equations.

    VENUS draws a trough as several access positions, one per channel, that share one liquid (ConnectedCtr). It
    is built as one container spanning them, holding all of their volume, and it keeps where VENUS sends each
    channel (`venus_access_y`: mm from its centre, channel 1 first), which pipeline.deck.reach hands to
    PyLabRobot. Built as the first position alone, a 90 mm trough would be 9 mm wide and take one channel."""
    rck = read_cfg(path)
    ctr = _container_cfg(rck, root)
    positions = access_positions(rck)
    n = len(positions) or 1
    segments = [[lo, hi, f"({text})*{n}"] for lo, hi, text in _segments(ctr)] if n > 1 else _segments(ctr)
    volume = SegmentVolume(segments)
    height = SegmentHeight(volume)
    depth = _f(ctr, "Depth")
    xs, ys = [x for x, _ in positions] or [0.0], [y for _, y in positions] or [0.0]
    container = Container(name=name, size_x=_f(ctr, "Dim.Dx") + max(xs) - min(xs),
                          size_y=_f(ctr, "Dim.Dy") + max(ys) - min(ys), size_z=depth,
                          material_z_thickness=_f(ctr, "BaseMM"), max_volume=volume(depth),
                          compute_volume_from_height=volume, compute_height_from_volume=height,
                          model=f"venus:{path.stem}")
    if positions:
        middle = (max(ys) + min(ys)) / 2
        container.venus_access_y = [y - middle for y in ys]
    return container


def make_tube_carrier(path: Path, name: str, root: Path = ROOT) -> Carrier:
    """A sample-tube rack (it sits on the rails itself) as a carrier with one site per tube position, front-most
    first; each site is where a tube's container stands."""
    rck = read_cfg(path)
    ctr = _container_cfg(rck, root)
    rows, columns = int(rck["Rows"]), int(rck["Columns"])
    dx, dy = _f(ctr, "Dim.Dx"), _f(ctr, "Dim.Dy")
    x0, y0, z = _f(rck, "BndryX") - dx / 2, _f(rck, "BndryY") - dy / 2, _f(rck, "Cntr.1.base")
    locations = [Coordinate(x0 + c * _f(rck, "Dx"), y0 + r * _f(rck, "Dy"), z) for r in range(rows) for c in range(columns)]
    holders = create_resources(klass=ResourceHolder, locations=locations, resource_size_x=[dx] * len(locations),
                               resource_size_y=[dy] * len(locations), name_prefix=name)
    return Carrier(name=name, size_x=_f(rck, "Dim.Dx"), size_y=_f(rck, "Dim.Dy"), size_z=_f(rck, "Dim.Dz"),
                   sites=holders, model=f"venus:{path.stem}")


# --- PyLabRobot's definitions against VENUS's ---

def compare(factory: str, venus_file: str, root: Path = ROOT) -> List[str]:
    """Where a PyLabRobot factory differs from its VENUS definition by more than TOLERANCE_MM."""
    path = find(venus_file, root)
    pairs = read_cfg(path)
    ours = getattr(plr, factory)(name="compare")
    diffs: List[str] = []

    def near(what: str, a: float, b: float) -> None:
        if abs(a - b) > TOLERANCE_MM:
            diffs.append(f"{what}: PyLabRobot {a:g}, VENUS {b:g} ({a - b:+.2f} mm)")

    if path.suffix.lower() == ".tml":
        sites = carrier_sites(pairs)
        holders = [ours.sites[i] for i in sorted(ours.sites)]
        if len(holders) != len(sites):
            return [f"{len(holders)} sites in PyLabRobot, {len(sites)} in VENUS"]
        for holder, site in zip(holders, sites):
            # Compare where labware of VENUS's footprint lands, not the site's own corner: PyLabRobot 1.0 draws
            # some sites smaller than the labware and centres it on them. Height is still the site's.
            probe = plr.Resource(name="probe", size_x=site["dx"], size_y=site["dy"], size_z=0)
            try:
                landed = holder.location + holder.get_default_child_location(probe)
            except ValueError:  # a tip carrier's sites take only tip racks, which they centre on the opening
                landed = holder.location + Coordinate((holder.get_size_x() - site["dx"]) / 2,
                                                      (holder.get_size_y() - site["dy"]) / 2, 0)
            near(f"position {site['position']} x", landed.x, site["x"])
            near(f"position {site['position']} y", landed.y, site["y"])
            near(f"position {site['position']} z", holder.location.z, site["z"])
    else:
        geometry = rack_geometry(pairs)
        near("size x", ours.get_size_x(), geometry["size"][0])
        near("size y", ours.get_size_y(), geometry["size"][1])
        a1 = ours.get_item("A1")
        center = a1.location + a1.center()
        near("A1 x", center.x, geometry["a1"][0])
        near("A1 y", center.y, geometry["a1"][1])
        if ours.num_items_x != geometry["columns"] or ours.num_items_y != geometry["rows"]:
            diffs.append(f"grid: PyLabRobot {ours.num_items_x}x{ours.num_items_y}, VENUS {geometry['columns']}x{geometry['rows']}")
    return diffs


def check_map(venus_map: Dict[str, Any], root: Path = ROOT) -> Dict[str, List[str]]:
    """{venus type: differences} for every type with both a factory and a VENUS file. A type built from
    PyLabRobot must not differ from VENUS: that would put the deck somewhere VENUS does not."""
    report = {}
    for venus_type, spec in venus_map["labware"].items():
        if spec.get("venus"):
            find(spec["venus"], root)  # every cited definition must be in the library
        if spec.get("factory") and spec.get("venus"):
            report[venus_type] = compare(spec["factory"], spec["venus"], root)
            if spec.get("build", "plr") == "plr" and report[venus_type]:
                raise VenusLabwareError(f"{venus_type} is built from PyLabRobot's {spec['factory']}, which differs from "
                                        f"VENUS: {'; '.join(report[venus_type])}. Set \"build\": \"venus\".")
    return report
