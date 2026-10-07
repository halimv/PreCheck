import pytest
import json
import yaml
import os
from precheck.verifier import Verifier, SafetyGateError


@pytest.fixture
def precheck_dir():
    """Return path to precheck directory."""
    return os.path.join(os.path.dirname(__file__))


@pytest.fixture
def labware_config_path(precheck_dir):
    return os.path.join(precheck_dir, "labware_config.json")


@pytest.fixture
def protocol_config_path(precheck_dir):
    return os.path.join(precheck_dir, "protocol_config.json")


@pytest.fixture
def protocol_plan_path(precheck_dir):
    return os.path.join(precheck_dir, "protocol_plan.yaml")


@pytest.fixture
def verifier(labware_config_path, protocol_plan_path, protocol_config_path):
    """Create a verifier instance."""
    return Verifier(labware_config_path, protocol_plan_path, protocol_config_path)


class TestVolumeVerification:
    """Test edge cases for volume verification (dead volume enforcement: 30-330µL)."""

    def test_volume_below_minimum_aspirate_fails(self, precheck_dir, labware_config_path):
        """Aspirate that would leave <30µL dead volume should fail."""
        protocol = {
            "steps": [
                {"step": 1, "action": "tips_on", "labware": "hamilton_tiprack_96", "column": 1, "channels": [0]},
                # Start with 35µL (just above dead volume)
                {"step": 2, "action": "dispense", "labware": "corning_3595", "column": 1, "volume_ul": 35.0, "channels": [0]},
                # Try to aspirate 10µL, which would leave 25µL < 30µL minimum
                {"step": 3, "action": "aspirate", "labware": "corning_3595", "column": 1, "volume_ul": 10.0, "channels": [0]},
            ]
        }

        verifier = Verifier(labware_config_path, _write_temp_protocol(precheck_dir, protocol))
        result = verifier.run_verification()

        assert result["status"] == "FAILED"
        assert result["error_code"] == "DRY_ASPIRATE"

    def test_volume_at_minimum_boundary_ok(self, precheck_dir, labware_config_path):
        """Aspirate leaving exactly 30µL should pass."""
        protocol = {
            "steps": [
                {"step": 1, "action": "tips_on", "labware": "hamilton_tiprack_96", "column": 1, "channels": [0]},
                # Dispense to 40µL
                {"step": 2, "action": "dispense", "labware": "corning_3595", "column": 1, "volume_ul": 40.0, "channels": [0]},
                # Aspirate 10µL, leaving exactly 30µL
                {"step": 3, "action": "aspirate", "labware": "corning_3595", "column": 1, "volume_ul": 10.0, "channels": [0]},
                {"step": 4, "action": "tips_off", "labware": "waste"},
            ]
        }

        verifier = Verifier(labware_config_path, _write_temp_protocol(precheck_dir, protocol))
        result = verifier.run_verification()

        assert result["status"] == "PASSED"

    def test_volume_exceeds_maximum_dispense_fails(self, precheck_dir, labware_config_path):
        """Dispense that would exceed 330µL maximum should fail."""
        protocol = {
            "steps": [
                {"step": 1, "action": "tips_on", "labware": "hamilton_tiprack_96", "column": 1, "channels": [0]},
                # Dispense to 300µL
                {"step": 2, "action": "dispense", "labware": "corning_3595", "column": 1, "volume_ul": 300.0, "channels": [0]},
                # Try to dispense 35µL, which would total 335µL > 330µL max
                {"step": 3, "action": "dispense", "labware": "corning_3595", "column": 1, "volume_ul": 35.0, "channels": [0]},
            ]
        }

        verifier = Verifier(labware_config_path, _write_temp_protocol(precheck_dir, protocol))
        result = verifier.run_verification()

        assert result["status"] == "FAILED"
        assert result["error_code"] == "VOLUMETRIC_OVERFLOW"

    def test_volume_at_maximum_boundary_ok(self, precheck_dir, labware_config_path):
        """Dispense to exactly 330µL should pass."""
        protocol = {
            "steps": [
                {"step": 1, "action": "tips_on", "labware": "hamilton_tiprack_96", "column": 1, "channels": [0]},
                # Dispense 330µL total
                {"step": 2, "action": "dispense", "labware": "corning_3595", "column": 1, "volume_ul": 330.0, "channels": [0]},
                {"step": 3, "action": "tips_off", "labware": "waste"},
            ]
        }

        verifier = Verifier(labware_config_path, _write_temp_protocol(precheck_dir, protocol))
        result = verifier.run_verification()

        assert result["status"] == "PASSED"


class TestContaminationTracking:
    """Test smart contamination prevention (allow reuse from same source, block different sources)."""

    def test_aspirate_same_source_allowed(self, precheck_dir, labware_config_path):
        """Aspirate from same source well multiple times should be allowed."""
        protocol = {
            "steps": [
                # Setup: populate column 1 with 100µL
                {"step": 1, "action": "tips_on", "labware": "hamilton_tiprack_96", "column": 1, "channels": [0]},
                {"step": 2, "action": "dispense", "labware": "corning_3595", "column": 1, "volume_ul": 100.0, "channels": [0]},
                {"step": 3, "action": "tips_off", "labware": "waste"},
                # Test: aspirate from same source multiple times
                {"step": 4, "action": "tips_on", "labware": "hamilton_tiprack_96", "column": 2, "channels": [0]},
                # First aspirate from A1 (100µL → 50µL)
                {"step": 5, "action": "aspirate", "labware": "corning_3595", "column": 1, "volume_ul": 50.0, "channels": [0]},
                # Dispense to B1
                {"step": 6, "action": "dispense", "labware": "corning_3595", "column": 2, "volume_ul": 50.0, "channels": [0]},
                # Aspirate from A1 again (same source, should be OK: 50µL → 30µL, at minimum)
                {"step": 7, "action": "aspirate", "labware": "corning_3595", "column": 1, "volume_ul": 20.0, "channels": [0]},
                {"step": 8, "action": "tips_off", "labware": "waste"},
            ]
        }

        verifier = Verifier(labware_config_path, _write_temp_protocol(precheck_dir, protocol))
        result = verifier.run_verification()

        assert result["status"] == "PASSED"

    def test_aspirate_different_source_without_tips_off_fails(self, precheck_dir, labware_config_path):
        """Aspirate from different source well without tips_off should fail."""
        protocol = {
            "steps": [
                {"step": 1, "action": "tips_on", "labware": "hamilton_tiprack_96", "column": 1, "channels": [0]},
                # Set up column 1 with liquid
                {"step": 2, "action": "dispense", "labware": "corning_3595", "column": 1, "volume_ul": 100.0, "channels": [0]},
                # Aspirate from column 1
                {"step": 3, "action": "aspirate", "labware": "corning_3595", "column": 1, "volume_ul": 50.0, "channels": [0]},
                # Try to aspirate from column 2 without tips_off (contamination risk)
                {"step": 4, "action": "aspirate", "labware": "corning_3595", "column": 2, "volume_ul": 50.0, "channels": [0]},
            ]
        }

        verifier = Verifier(labware_config_path, _write_temp_protocol(precheck_dir, protocol))
        result = verifier.run_verification()

        assert result["status"] == "FAILED"
        assert result["error_code"] == "CONTAMINATED_TIP"

    def test_tips_off_resets_source_tracking(self, precheck_dir, labware_config_path):
        """After tips_off, tips can be reused on different source wells."""
        protocol = {
            "steps": [
                # First pickup: aspirate from column 1
                {"step": 1, "action": "tips_on", "labware": "hamilton_tiprack_96", "column": 1, "channels": [0]},
                {"step": 2, "action": "dispense", "labware": "corning_3595", "column": 1, "volume_ul": 100.0, "channels": [0]},
                {"step": 3, "action": "aspirate", "labware": "corning_3595", "column": 1, "volume_ul": 50.0, "channels": [0]},
                # Discard tips
                {"step": 4, "action": "tips_off", "labware": "waste"},
                # New pickup: can now aspirate from column 2
                {"step": 5, "action": "tips_on", "labware": "hamilton_tiprack_96", "column": 2, "channels": [0]},
                {"step": 6, "action": "dispense", "labware": "corning_3595", "column": 2, "volume_ul": 100.0, "channels": [0]},
                {"step": 7, "action": "aspirate", "labware": "corning_3595", "column": 2, "volume_ul": 50.0, "channels": [0]},
                {"step": 8, "action": "tips_off", "labware": "waste"},
            ]
        }

        verifier = Verifier(labware_config_path, _write_temp_protocol(precheck_dir, protocol))
        result = verifier.run_verification()

        assert result["status"] == "PASSED"

    def test_multichannel_contamination_tracking(self, precheck_dir, labware_config_path):
        """Each channel tracks its own contamination source independently."""
        protocol = {
            "steps": [
                # Setup: populate columns 1 and 2 with liquid (300µL each for plenty of volume)
                {"step": 1, "action": "tips_on", "labware": "hamilton_tiprack_96", "column": 1, "channels": [0, 1, 2, 3]},
                {"step": 2, "action": "dispense", "labware": "corning_3595", "column": 1, "volume_ul": 300.0, "channels": [0, 1, 2, 3]},
                {"step": 3, "action": "dispense", "labware": "corning_3595", "column": 2, "volume_ul": 300.0, "channels": [0, 1, 2, 3]},
                {"step": 4, "action": "tips_off", "labware": "waste"},
                # Test: independent contamination tracking per channel
                {"step": 5, "action": "tips_on", "labware": "hamilton_tiprack_96", "column": 2, "channels": [0, 1, 2, 3]},
                # Channel 0: aspirate from column 1
                {"step": 6, "action": "aspirate", "labware": "corning_3595", "column": 1, "volume_ul": 50.0, "channels": [0]},
                # Channel 1: aspirate from column 2 (different source, same tip batch)
                {"step": 7, "action": "aspirate", "labware": "corning_3595", "column": 2, "volume_ul": 50.0, "channels": [1]},
                # Channel 0 can aspirate from column 1 again (still on same source)
                {"step": 8, "action": "aspirate", "labware": "corning_3595", "column": 1, "volume_ul": 50.0, "channels": [0]},
                # Channel 1 can aspirate from column 2 again (still on same source)
                {"step": 9, "action": "aspirate", "labware": "corning_3595", "column": 2, "volume_ul": 50.0, "channels": [1]},
                # But channel 0 cannot aspirate from column 2 (contaminated with column 1 source)
                {"step": 10, "action": "aspirate", "labware": "corning_3595", "column": 2, "volume_ul": 50.0, "channels": [0]},
            ]
        }

        verifier = Verifier(labware_config_path, _write_temp_protocol(precheck_dir, protocol))
        result = verifier.run_verification()

        assert result["status"] == "FAILED"
        assert result["error_code"] == "CONTAMINATED_TIP"


class TestTipTracking:
    """Test tip rack inventory and depletion."""

    def test_tip_pickup_depletion(self, precheck_dir, labware_config_path):
        """Tips should be depleted from rack after pickup."""
        protocol = {
            "steps": [
                # Pickup from column 1 (depletes 8 tips: row 0-7, col 1)
                {"step": 1, "action": "tips_on", "labware": "hamilton_tiprack_96", "column": 1, "channels": [0, 1, 2, 3, 4, 5, 6, 7]},
                {"step": 2, "action": "tips_off", "labware": "waste"},
                # Try to pickup from same column again (should fail)
                {"step": 3, "action": "tips_on", "labware": "hamilton_tiprack_96", "column": 1, "channels": [0]},
            ]
        }

        verifier = Verifier(labware_config_path, _write_temp_protocol(precheck_dir, protocol))
        result = verifier.run_verification()

        assert result["status"] == "FAILED"
        assert result["error_code"] == "TIP_DEPLETED"

    def test_tip_pickup_different_columns_ok(self, precheck_dir, labware_config_path):
        """Tips can be picked from different columns sequentially."""
        protocol = {
            "steps": [
                # Pickup from column 1
                {"step": 1, "action": "tips_on", "labware": "hamilton_tiprack_96", "column": 1, "channels": [0]},
                {"step": 2, "action": "tips_off", "labware": "waste"},
                # Pickup from column 2 (different location)
                {"step": 3, "action": "tips_on", "labware": "hamilton_tiprack_96", "column": 2, "channels": [0]},
                {"step": 4, "action": "tips_off", "labware": "waste"},
            ]
        }

        verifier = Verifier(labware_config_path, _write_temp_protocol(precheck_dir, protocol))
        result = verifier.run_verification()

        assert result["status"] == "PASSED"


class TestReferenceProtocol:
    """Test that the reference serial dilution protocol passes verification."""

    def test_reference_protocol_passes(self, protocol_plan_path, labware_config_path):
        """Reference protocol should pass with dead volume enforcement."""
        verifier = Verifier(labware_config_path, protocol_plan_path)
        result = verifier.run_verification()

        # With current parameters, this should pass
        assert result["status"] == "PASSED"


# Helper function to write temporary protocol files
def _write_temp_protocol(precheck_dir, protocol_dict):
    """Write protocol dict to temp file and return path."""
    temp_path = os.path.join(precheck_dir, "test_protocol_temp.yaml")
    with open(temp_path, "w") as f:
        yaml.dump(protocol_dict, f)
    return temp_path
