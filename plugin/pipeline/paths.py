"""Where PreCheck reads and where it writes.

Two folders, and nothing else is used:

- PLUGIN: the folder this package lives in. Its code, and the lab's ground truth in config/ (the instrument, VENUS's
  labware library, the policy and the AHC accepted types). Read only, in a run.
- WORK: the working folder a run happens in: the folder PreCheck is started from, unless PRECHECK_WORKDIR names
  another. Everything a run writes goes here: healed/ (the passing protocols, their scripts, layouts and reports),
  drafts/ and decks/ (what the drafter and the deck builder produced), build/ (per-round work files) and
  knowledge/ (the diagnostics knowledge base, which runs add to).

When PreCheck runs from its own repo folder the two are the same folder, and nothing changes.
"""

import os
import shutil
from pathlib import Path

PLUGIN = Path(__file__).resolve().parent.parent
WORK = Path(os.environ.get("PRECHECK_WORKDIR") or os.getcwd()).resolve()

HEALED = WORK / "healed"
DRAFTS = WORK / "drafts"
DECKS = WORK / "decks"
BUILD = WORK / "build"
KNOWLEDGE = WORK / "knowledge" / "diagnostics.json"
KNOWLEDGE_SEED = PLUGIN / "knowledge" / "diagnostics.json"


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
