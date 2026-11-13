"""Where precheck reads and where it writes.

Two folders, and nothing else is used:

- PLUGIN: the folder this package lives in. Its code, and the lab's ground truth in config/ (the instrument, VENUS's
  labware library, the policy and the AHC accepted types). Read only, in a run.
- WORK: the working folder a run happens in: the folder precheck is started from, unless PRECHECK_WORKDIR names
  another. Everything a run writes goes here: healed/ (the passing protocols, their scripts, layouts and reports),
  drafts/ and decks/ (what the drafter and the deck builder produced), build/ (per-round work files) and
  knowledge/ (the diagnostics knowledge base, which runs add to).

When precheck runs from its own repo folder the two are the same folder, and nothing changes.
"""

import json
import os
import shutil
from pathlib import Path
from typing import Any, Dict, Optional

PLUGIN = Path(__file__).resolve().parent.parent
WORK = Path(os.environ.get("PRECHECK_WORKDIR") or os.getcwd()).resolve()

HEALED = WORK / "healed"
DRAFTS = WORK / "drafts"
DECKS = WORK / "decks"
BUILD = WORK / "build"
KNOWLEDGE = WORK / "knowledge" / "diagnostics.json"
KNOWLEDGE_SEED = PLUGIN / "knowledge" / "diagnostics.json"

# Settings the person gives once (the VENUS library's folder). They live outside the plugin folder, so an update of
# the plugin does not lose them.
CONFIG_FILE = Path(os.environ.get("PRECHECK_CONFIG") or Path.home() / ".config" / "precheck" / "config.json")


def saved_settings() -> Dict[str, Any]:
    try:
        return json.loads(CONFIG_FILE.read_text())
    except (OSError, ValueError):
        return {}


def save_setting(key: str, value: str) -> None:
    settings = saved_settings()
    settings[key] = value
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(settings, indent=2))


def labware() -> Path:
    """VENUS's Labware folder (the one with ML_STAR inside): PRECHECK_LABWARE if set, else the folder setup saved,
    else config/Labware in the plugin (a development checkout that has the library in place)."""
    env = os.environ.get("PRECHECK_LABWARE")
    if env:
        return Path(env).expanduser()
    saved: Optional[str] = saved_settings().get("labware")
    if saved:
        return Path(saved).expanduser()
    return PLUGIN / "config" / "Labware"


def ensure_knowledge() -> Path:
    """The knowledge base a run reads and adds to: the working folder's copy, made from the plugin's seed the first
    time. The seed itself is never written."""
    if not KNOWLEDGE.exists():
        KNOWLEDGE.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(KNOWLEDGE_SEED, KNOWLEDGE)
    return KNOWLEDGE


def in_work(path: Path) -> str:
    """A path shown to the person: relative to the working folder when it is inside it."""
    return str(path.relative_to(WORK)) if path.is_relative_to(WORK) else str(path)


def resolve(relative: str) -> Path:
    """A file a protocol names by a relative path (a deck config it drafted, or a ground-truth file): found in the
    working folder first, then in the plugin."""
    for root in (WORK, PLUGIN):
        candidate = root / relative
        if candidate.exists():
            return candidate
    return WORK / relative
