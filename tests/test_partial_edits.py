"""Partial acceptance in the self-healing loop: edits that pass their checks are applied even when
another edit in the same reply is rejected.

The scripted replies are the ones qwen2.5-coder:7b actually sent: a correct set_initial_volume
bundled with a replace_step that fails to compile, or that changes how much liquid moves.
"""

import json
from pathlib import Path

from pipeline.deck import load_deck_config
from pipeline.self_heal import SelfHealer, apply_valid_edits

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config"
ALL = list(range(8))


def test_apply_valid_edits_keeps_order_and_indices():
    kinds = {"tube_15ml": "container", "corning_3595": "plate"}
    p = {"steps": [{"step": 1, "action": "tips_off"}], "initial_volumes_ul": {}}
    new, applied, errors = apply_valid_edits(p, [
        {"op": "bogus"},
        {"op": "set_initial_volume", "labware": "tube_15ml", "volume_ul": 10},
        {"op": "set_initial_volume", "labware": "corning_3595", "volume_ul": 10},
    ], kinds)
    assert applied == [1]
    assert len(errors) == 2
    assert new["initial_volumes_ul"] == {"tube_15ml": 10}
    assert p["initial_volumes_ul"] == {}
