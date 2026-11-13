"""The parts of the one-flow pipeline (pipeline.py) added with it: the instrument's STAR model as the dry-run
backend, VENUS's connected troughs, the Claude repair backend, the design review and its suggestions, and the
AHC layout hand-off. The protocol is the serial dilution drafted and healed on the deck on the STARlet
(tests/fixtures/real_deck_dilution.json, with its built deck beside it)."""

import copy
import json
import subprocess
from pathlib import Path

import pytest

from pipeline import ahc_export, design_review, self_heal
from pipeline.deck import deck_config_for, INSTRUMENT_DECK, build_deck, load_deck_config, reach
from pipeline.instrument import firmware_configuration
from pipeline.self_heal import ClaudeBackend, OllamaBackend, SelfHealer, make_backend
from pipeline.stage2_compiler import compile_protocol
from pipeline.venus_layout import position_checks, read_lay

ROOT = Path(__file__).resolve().parent.parent / "plugin"  # the plugin: code and ground truth
TESTS = Path(__file__).resolve().parent
FIXTURE = TESTS / "fixtures" / "real_deck_dilution.json"


@pytest.fixture(scope="module")
def protocol():
    return json.loads(FIXTURE.read_text())


@pytest.fixture(scope="module")
def deck_config(protocol):
    return deck_config_for(protocol, ROOT)


# --- the dry-run backend is the instrument ---

def test_a_deck_that_names_its_instrument_is_simulated_as_that_instrument(deck_config):
    import asyncio
    from pipeline.deck import build_deck
    from pipeline.pipetting import close_device, mounted_channels, num_channels, open_device
    firmware = firmware_configuration(deck_config)
    assert firmware and firmware.endswith("starlet_F553_configuration.json")
    deck, _ = build_deck(deck_config)

    async def run():
        dev = await open_device(deck, "chatterbox", firmware)
        try:
            return num_channels(dev), mounted_channels(dev), type(dev).__name__
        finally:
            await close_device(dev)

    channels, mounted, kind = asyncio.run(run())
    assert (channels, mounted, kind) == (8, [], "STARDevice")


def test_a_deck_with_no_instrument_has_no_firmware_to_answer(deck_config):
    plain = {k: v for k, v in deck_config.items() if k != "instrument"}
    assert firmware_configuration(plain) is None


def test_the_healed_dilution_is_refused_by_the_piston_rule_on_the_star_model(protocol, deck_config, tmp_path):
    # The STAR device enforces what a piston can push out (the legacy ChatterBox did not). The healed dilution
    # aspirates 180 uL per channel and dispenses it in pieces, which the pistons cannot do as written: the gate
    # must say so, rather than pass a run the instrument would refuse.
    gate = SelfHealer(deck_config, work_dir=str(tmp_path)).evaluate(protocol, 0)
    assert not gate.passed and gate.stage == "simulate"
    assert gate.detail["error_code"] == "PISTON_TRAVEL", gate.summary
    assert "piston holds" in gate.summary


def test_every_height_on_the_instrument_deck_matches_venus():
    lay = ROOT / INSTRUMENT_DECK
    checks = position_checks(read_lay(lay.read_bytes()), load_deck_config(str(lay)))
    heights = [c for c in checks if "dz" in c]
    assert heights and all(c["ok"] for c in checks), [c for c in checks if not c["ok"]]


# --- VENUS's trough: eight connected positions, one liquid ---

def test_a_venus_trough_is_one_container_all_eight_channels_enter(deck_config):
    _, res = build_deck(deck_config)
    trough = res["diluent"]
    assert trough.max_volume == pytest.approx(63000)
    assert len(trough.venus_access_y) == 8
    extra = reach(trough, list(range(8)))
    assert "spread" not in extra and len(extra["offsets"]) == 8  # the offsets are all the device needs
    ys = [o.y for o in extra["offsets"]]
    assert ys == sorted(ys, reverse=True)  # channel 1 at the rear
    assert ys[3] - ys[4] == pytest.approx(14.5)  # the wall across the trough's middle
    assert reach(trough, [2, 5])["offsets"][0].y == ys[2]


def test_other_containers_are_left_to_pylabrobot(deck_config):
    _, res = build_deck(deck_config)
    assert reach(res["dilution_plate"], [0, 1]) == {}
    assert reach(res["diluent"], [8]) == {}  # a channel VENUS gives no position for


def test_compiled_trough_steps_use_venus_positions(protocol, deck_config):
    code = compile_protocol(protocol, deck_config)
    assert "from pipeline.deck import reach" in code
    assert '**reach(res["diluent"], [0, 1, 2, 3, 4, 5, 6, 7])' in code
    assert 'reach(res["dilution_plate"]' not in code


# --- the Claude repair backend ---

class FakeCLI:
    def __init__(self, stdout, returncode=0, stderr=""):
        self.stdout, self.returncode, self.stderr = stdout, returncode, stderr
        self.calls = []

    def __call__(self, cmd, **kwargs):
        self.calls.append((cmd, kwargs))
        return subprocess.CompletedProcess(cmd, self.returncode, self.stdout, self.stderr)


@pytest.fixture
def cli(monkeypatch):
    def install(result, **kwargs):
        fake = FakeCLI(json.dumps(result) if isinstance(result, dict) else result, **kwargs)
        monkeypatch.setattr(subprocess, "run", fake)
        monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/claude")
        return fake
    return install


def test_claude_is_the_default_healer_on_haiku():
    backend = make_backend()
    assert isinstance(backend, ClaudeBackend) and backend.model == "claude-haiku-5-5" == self_heal.CLAUDE_MODEL
    assert make_backend("claude", "claude-sonnet-5-5").model == "claude-sonnet-5-5"
    assert isinstance(make_backend("ollama"), OllamaBackend)
    with pytest.raises(ValueError):
        make_backend("gpt")


def test_claude_backend_parses_edits_and_tracks_cost(cli):
    edits = {"reasoning": "load more", "edits": [{"op": "set_initial_volume", "labware": "diluent", "volume_ul": 4800}]}
    fake = cli({"is_error": False, "total_cost_usd": 0.004, "result": "```json\n" + json.dumps(edits) + "\n```"})
    backend = ClaudeBackend()
    assert backend.propose_edits("system text", "prompt text") == edits
    assert backend.propose_edits("system text", "prompt text") == edits
    assert backend.cost_usd == pytest.approx(0.008)
    cmd, kwargs = fake.calls[0]
    assert cmd[cmd.index("--model") + 1] == "claude-haiku-5-5" and "-p" in cmd
    assert "Bash" in cmd[cmd.index("--disallowedTools") + 1]  # the model answers; it does not act
    assert "system text" in kwargs["input"] and '"edits"' in kwargs["input"]  # the schema rides in the prompt
    assert Path(kwargs["cwd"]) != ROOT  # run outside the project


def test_a_reply_that_is_not_json_counts_as_a_round_with_no_edits(cli):
    cli({"is_error": False, "result": "I cannot fix this."})
    reply = ClaudeBackend().propose_edits("s", "p")
    assert reply["edits"] == [] and "not the JSON asked for" in reply["reasoning"]


def test_claude_cli_failures_are_reported(cli, monkeypatch):
    cli({"is_error": True, "result": "Credit balance is too low"})
    with pytest.raises(RuntimeError, match="Credit balance"):
        ClaudeBackend().propose_edits("s", "p")
    cli("not json at all", returncode=1, stderr="boom")
    with pytest.raises(RuntimeError, match="boom"):
        ClaudeBackend().propose_edits("s", "p")
    monkeypatch.setattr("shutil.which", lambda name: None)
    monkeypatch.setattr("pipeline.stage0_drafter.CLAUDE_BIN", "claude-not-installed")
    with pytest.raises(RuntimeError, match="--healer ollama"):
        ClaudeBackend().propose_edits("s", "p")


# --- the design review ---

def test_the_review_reports_reagents_and_dilutions(protocol, deck_config):
    r = design_review.review(protocol, deck_config)
    reagents = {g["labware"]: g for g in r["reagents"]}
    assert reagents["diluent"]["loaded_ul"] == 4800
    assert reagents["diluent"]["drawn_ul"] == pytest.approx(6 * 8 * 90)
    assert reagents["diluent"]["left_ul"] == pytest.approx(4800 - 4320)
    assert reagents["diluent"]["capacity_ul"] == pytest.approx(63000)
    assert reagents["culture"]["drawn_ul"] == pytest.approx(80)

    culture = protocol["reagents"]["culture"]
    by_column = {w["column"]: w for w in r["wells"] if w["plate"] == "dilution_plate"}
    assert sorted(by_column) == [1, 2, 3, 4, 5, 6]
    for k in range(1, 7):
        assert by_column[k]["contents"][culture]["dilution"] == pytest.approx(10 ** k, rel=0.01)
        assert by_column[k]["rows"] == "ABCDEFGH" and not by_column[k]["flags"]
    assert by_column[6]["volume_ul"] == pytest.approx(100)
    assert by_column[1]["volume_ul"] == pytest.approx(90)  # 10 uL went on to column 2

    chosen = {item["name"]: item for item in r["labware"]}
    assert chosen["dilution_plate"]["type"] == "Cos_96_PCR" and "rail 1" in chosen["dilution_plate"]["where"]
    assert r["tips"]["used"] == 72 and r["channels"] == 8
    text = design_review.render(r, [])
    assert "Suggestions: none." in text and "1:1e+06" in text


def test_the_review_flags_a_well_filled_past_its_limit(protocol, deck_config):
    over = copy.deepcopy(protocol)
    for s in over["steps"]:
        if s["action"] == "dispense" and s["labware"] == "dilution_plate" and s["volume_ul"] == 90:
            s["volume_ul"] = 280
    flags = [f for w in design_review.review(over, deck_config)["wells"] for f in w["flags"]]
    assert any("fill limit" in f for f in flags)


def test_suggestions_are_improvements_the_simulator_does_not_ask_for(protocol, deck_config):
    hints = {h["id"]: h for h in design_review.suggestions(protocol, deck_config)}
    assert "liquid_too_shallow" in hints and "'culture'" in hints["liquid_too_shallow"]["title"]
    assert "channels_one_at_a_time" not in hints  # every trough step already uses all 8 channels
    assert all(h["request"] and h["detail"] for h in hints.values())


def test_single_channel_runs_into_a_trough_are_suggested_as_one_move(protocol, deck_config):
    split = copy.deepcopy(protocol)
    first = next(i for i, s in enumerate(split["steps"]) if s["action"] == "aspirate" and s["labware"] == "diluent")
    one = split["steps"][first]
    split["steps"][first:first + 1] = [{**one, "channels": [ch]} for ch in range(8)]
    for n, s in enumerate(split["steps"], 1):
        s["step"] = n
    hint = next(h for h in design_review.suggestions(split, deck_config) if h["id"] == "channels_one_at_a_time")
    assert len(hint["steps"]) == 8 and "8 channels at once" in hint["title"]
    assert "[0, 1, 2, 3, 4, 5, 6, 7]" in hint["request"]


def test_an_overloaded_reagent_is_suggested_down(protocol, deck_config):
    heavy = copy.deepcopy(protocol)
    heavy["initial_volumes_ul"]["diluent"] = 40000
    hint = next(h for h in design_review.suggestions(heavy, deck_config) if h["id"] == "reagent_overloaded")
    assert "40000 uL" in hint["title"] and "5200 uL" in hint["request"]  # 4320 uL drawn, plus 20%, to the next 50


# --- the hand-off to AHC ---

AHC = {"tracks": {"min": 1, "max": 30},
       "carriers": ["TIP_CAR_480_A00", "PLT_CAR_L5_DWP", "RGT_CAR_5R60_A00"],
       "labware": ["hamilton_96_tiprack_300uL_filter", "Cor_96_wellplate_360ul_Fb", "hamilton_1_trough_60mL_Vb"],
       "equivalents": {"RGT_CONT_50ml_A00": {"type": "hamilton_1_trough_60mL_Vb", "note": "same trough"},
                       "Cos_96_PCR": {"type": "Cor_96_wellplate_360ul_Fb", "note": "nearest plate"}}}


def test_the_whole_deck_goes_to_ahc(protocol, deck_config):
    layout, problems, warnings = ahc_export.to_ahc_layout(deck_config, AHC, protocol["initial_volumes_ul"])
    assert problems == []
    carriers = {c["type"]: c for c in layout["carriers"]}
    assert set(carriers) == {"TIP_CAR_480_A00", "PLT_CAR_L5_DWP", "RGT_CAR_5R60_A00"}
    placed = {s["name"]: s["type"] for c in layout["carriers"] for s in c["sites"].values()}
    assert placed["dilution_plate"] == "Cor_96_wellplate_360ul_Fb"
    assert placed["diluent"] == placed["culture"] == "hamilton_1_trough_60mL_Vb"
    assert placed["tips"] == "hamilton_96_tiprack_300uL_filter"
    assert layout["liquids"] == {"diluent": 4800, "culture": 200}
    assert any("dilution_plate" in w and "nearest plate" in w for w in warnings)  # the difference is stated


def test_labware_ahc_has_no_type_for_is_reported_not_renamed(protocol, deck_config):
    no_equivalents = {**AHC, "equivalents": {}}
    layout, problems, _ = ahc_export.to_ahc_layout(deck_config, no_equivalents, protocol["initial_volumes_ul"])
    assert any("dilution_plate (Cos_96_PCR)" in p for p in problems)
    assert any("4800 uL loaded in diluent" in p for p in problems)
    assert "liquids" not in layout


def test_the_repo_copy_of_ahc_types_takes_the_real_deck(protocol, deck_config, tmp_path):
    ahc = ahc_export.load_ahc_types(ROOT, plugins=tmp_path)  # no AHC installed here: the copy in config/
    assert ahc["source"] == ahc_export.AHC_TYPES
    assert ahc_export.to_ahc_layout(deck_config, ahc, protocol["initial_volumes_ul"])[1] == []


def test_the_installed_ahc_list_wins_over_the_copy(tmp_path):
    described = tmp_path / "marketplaces" / "x" / "src" / "ahc" / "devices" / "hamilton"
    described.mkdir(parents=True)
    (described / "starlet.md").write_text(
        "---\nmodel: hamilton.starlet\nlayout:\n  kind: tracks\n  tracks: {min: 1, max: 30}\n"
        "  carriers: [NEW_CARRIER]\n  labware:\n    plates: [new_plate]\n    troughs: [new_trough]\n---\n# text\n")
    ahc = ahc_export.load_ahc_types(ROOT, plugins=tmp_path)
    assert ahc["carriers"] == ["NEW_CARRIER"] and ahc["labware"] == ["new_plate", "new_trough"]
    assert ahc["source"].endswith("starlet.md") and "Cos_96_PCR" in ahc["equivalents"]
    (described / "starlet.md").write_text("no front matter")
    assert ahc_export.installed_ahc_types(tmp_path) is None
