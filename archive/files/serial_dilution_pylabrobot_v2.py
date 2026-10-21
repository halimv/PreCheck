"""
Serial Dilution Protocol using PyLabRobot with Configuration File
==================================================================

Description: Automated 2-fold serial dilution protocol that reads all parameters
             from a configuration file (config.json). Supports Corning 96-well plates
             and Hamilton RoboTip liquid handling.

Platform: Hamilton MICROLAB STAR or VANTAGE (via PyLabRobot)
Author: Generated for Serial Dilution Experiment
Date: 2024

Requirements:
    - pylabrobot
    - json
    - pyyaml (optional)

Configuration:
    - config.json: Main configuration file with all parameters
"""

import sys
import json
import os
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path

try:
    from pylabrobot.liquid_handling import LiquidHandler
    from pylabrobot.resources import (
        Plate96Well,
        Reservoir,
        TipRack96,
        Container,
    )
except ImportError:
    print("Error: PyLabRobot not installed. Install with: pip install pylabrobot")
    sys.exit(1)


# ============================================================================
# CONFIGURATION MANAGER
# ============================================================================

class ConfigurationManager:
    """
    Manages loading and validation of the serial dilution configuration.
    """

    def __init__(self, config_file: str = "config.json"):
        """
        Initialize configuration manager.

        Args:
            config_file: Path to JSON configuration file
        """
        self.config_file = config_file
        self.config = None
        self.validation_errors = []

    def load_config(self) -> Dict[str, Any]:
        """
        Load and parse JSON configuration file.

        Returns:
            Dictionary containing configuration parameters

        Raises:
            FileNotFoundError: If config file not found
            json.JSONDecodeError: If JSON is malformed
        """
        try:
            config_path = Path(self.config_file)

            if not config_path.exists():
                raise FileNotFoundError(f"Configuration file not found: {self.config_file}")

            with open(config_path, 'r') as f:
                self.config = json.load(f)

            print(f"✓ Configuration loaded from: {self.config_file}")
            return self.config

        except json.JSONDecodeError as e:
            print(f"✗ JSON parsing error in {self.config_file}: {str(e)}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"✗ Error loading configuration: {str(e)}", file=sys.stderr)
            sys.exit(1)

    def validate_config(self) -> bool:
        """
        Validate configuration for required parameters.

        Returns:
            True if valid, False otherwise
        """
        if not self.config:
            self.validation_errors.append("Configuration not loaded")
            return False

        required_sections = [
            "dilution_parameters",
            "plate_specifications",
            "hamilton_tips",
            "deck_configuration"
        ]

        for section in required_sections:
            if section not in self.config:
                self.validation_errors.append(f"Missing required section: {section}")

        # Validate dilution parameters
        dil_params = self.config.get("dilution_parameters", {})
        required_params = [
            "stock_concentration_um",
            "dilution_factor",
            "num_columns",
            "num_rows",
            "final_volume_ul",
            "transfer_volume_ul",
            "diluent_volume_ul"
        ]

        for param in required_params:
            if param not in dil_params:
                self.validation_errors.append(
                    f"Missing dilution parameter: {param}"
                )

        if self.validation_errors:
            print("Configuration validation errors:")
            for error in self.validation_errors:
                print(f"  ✗ {error}")
            return False

        print("✓ Configuration validation passed")
        return True

    def get_section(self, section: str) -> Dict[str, Any]:
        """Get a configuration section."""
        return self.config.get(section, {})

    def get_value(self, path: str, default: Any = None) -> Any:
        """
        Get a nested configuration value using dot notation.

        Args:
            path: Dot-separated path (e.g., 'dilution_parameters.stock_concentration_um')
            default: Default value if not found

        Returns:
            Configuration value or default
        """
        keys = path.split('.')
        value = self.config

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default

        return value


# ============================================================================
# CLASS: SerialDilutionProtocol
# ============================================================================

class SerialDilutionProtocol:
    """
    Manages the complete serial dilution workflow using configuration-driven parameters.
    """

    def __init__(self, lh: LiquidHandler, config: Dict[str, Any]):
        """
        Initialize the serial dilution protocol with configuration.

        Args:
            lh: PyLabRobot LiquidHandler instance
            config: Configuration dictionary
        """
        self.lh = lh
        self.config = config
        self.plate = None
        self.tip_rack_1 = None
        self.tip_rack_2 = None
        self.stock_tube = None
        self.diluent_reservoir = None
        self.concentrations = []
        self.log_entries = []

        # Extract configuration parameters
        self.dil_params = config.get("dilution_parameters", {})
        self.plate_specs = config.get("plate_specifications", {})
        self.tip_specs = config.get("hamilton_tips", {})
        self.deck_config = config.get("deck_configuration", {})
        self.liquid_params = config.get("liquid_handling", {})

        # Set constants from config
        self.STOCK_CONCENTRATION = self.dil_params.get("stock_concentration_um", 1000)
        self.DILUTION_FACTOR = self.dil_params.get("dilution_factor", 2)
        self.NUM_COLUMNS = self.dil_params.get("num_columns", 12)
        self.NUM_ROWS = self.dil_params.get("num_rows", 8)
        self.FINAL_VOLUME = self.dil_params.get("final_volume_ul", 100)
        self.TRANSFER_VOLUME = self.dil_params.get("transfer_volume_ul", 50)
        self.DILUENT_VOLUME = self.dil_params.get("diluent_volume_ul", 50)

    def setup_labware(self) -> None:
        """
        Define and assign all required labware to the liquid handler deck
        based on configuration specifications.
        """
        print("\nSetting up labware...")
        self._log("Configuring Hamilton deck with Corning plates and Hamilton tips")

        # Display plate information
        plate_name = self.plate_specs.get("product_name", "Corning 96-well Plate")
        plate_code = self.plate_specs.get("product_code", "3595")
        print(f"  Plate: {plate_name} ({plate_code})")
        self._log(f"Plate: {plate_name} - {plate_code}")

        # Display tip information
        tip_capacity = self.tip_specs.get("specifications", {}).get("capacity_ul", 200)
        tip_product = self.tip_specs.get("product_line", "RoboTip®")
        print(f"  Tips: Hamilton {tip_product} {tip_capacity} µL")
        self._log(f"Tips: Hamilton {tip_product} {tip_capacity} µL")

        # Define 96-well plate (Corning specifications)
        plate_name_var = self.config.get("plate_specifications", {}).get("product_code", "corning_3595")
        self.plate = Plate96Well(name=f"plate_{plate_name_var}")
        self.lh.deck.assign_child_resource(self.plate, location=(0, 0))

        # Define tip racks (Hamilton RoboTip 96-tip format)
        self.tip_rack_1 = TipRack96(name="tip_rack_serial_transfer")
        self.lh.deck.assign_child_resource(self.tip_rack_1, location=(1, 0))

        self.tip_rack_2 = TipRack96(name="tip_rack_diluent")
        self.lh.deck.assign_child_resource(self.tip_rack_2, location=(2, 0))

        # Define stock solution tube
        stock_tube_config = self.config.get("reagent_containers", {}).get("stock_tube", {})
        stock_volume = stock_tube_config.get("volume_ul", 15000)
        self.stock_tube = Container(
            name="stock_solution",
            volume_ul=stock_volume,
            is_tip_compatible=False
        )
        self.lh.deck.assign_child_resource(self.stock_tube, location=(3, 0))

        # Define diluent reservoir
        diluent_config = self.config.get("reagent_containers", {}).get("diluent_reservoir", {})
        diluent_volume = diluent_config.get("volume_ul", 50000)
        self.diluent_reservoir = Reservoir(
            name="diluent_buffer",
            volume_ul=diluent_volume,
            is_tip_compatible=False
        )
        self.lh.deck.assign_child_resource(self.diluent_reservoir, location=(4, 0))

        print("✓ Labware setup complete")
        self._log("Labware setup complete - deck configured")

    def pre_dilution_setup(self) -> None:
        """
        Dispense diluent into columns 2-N based on configuration.
        """
        print("\nStarting Pre-Dilution Setup...")
        print(f"Dispensing {self.DILUENT_VOLUME} µL diluent into columns 2-{self.NUM_COLUMNS}...")

        # Pick up tips for diluent dispensing
        channels = list(range(self.NUM_ROWS))  # Channels 0-7
        self.lh.pick_up_tips(self.tip_rack_2, channels=channels)

        # Dispense diluent into columns 2-N
        for col in range(2, self.NUM_COLUMNS + 1):
            for row in range(self.NUM_ROWS):
                well = self.plate.get_well(row, col - 1)

                # Aspirate from reservoir
                self.lh.aspirate(
                    resource=self.diluent_reservoir,
                    volume=self.DILUENT_VOLUME,
                    channel=row
                )

                # Dispense into target well
                self.lh.dispense(
                    resource=well,
                    volume=self.DILUENT_VOLUME,
                    channel=row
                )

        # Drop tips
        self.lh.drop_tips(self.tip_rack_2, channels=channels)

        print("✓ Pre-Dilution Setup complete")
        self._log(
            f"Pre-Dilution Setup complete - "
            f"{self.DILUENT_VOLUME} µL diluent dispensed to columns 2-{self.NUM_COLUMNS}"
        )

    def serial_transfer(self) -> None:
        """
        Perform serial transfers from column N to column N+1
        based on configuration parameters.
        """
        print("\nStarting Serial Transfer Sequence...")
        self._log("Serial transfer sequence initiated")

        channels = list(range(self.NUM_ROWS))

        # Perform N-1 transfer steps
        for step in range(1, self.NUM_COLUMNS):
            source_col = step
            dest_col = step + 1

            print(f"  Transfer step {step}: Column {source_col} → Column {dest_col}")

            # Pick up tips from tip rack 1
            self.lh.pick_up_tips(self.tip_rack_1, channels=channels)

            # Transfer from source to destination column
            for row in range(self.NUM_ROWS):
                source_well = self.plate.get_well(row, source_col - 1)
                dest_well = self.plate.get_well(row, dest_col - 1)

                # Aspirate from source well
                self.lh.aspirate(
                    resource=source_well,
                    volume=self.TRANSFER_VOLUME,
                    channel=row
                )

                # Delay for liquid stabilization
                self.lh.wait(200)

                # Dispense into destination well
                self.lh.dispense(
                    resource=dest_well,
                    volume=self.TRANSFER_VOLUME,
                    channel=row
                )

                # Mix destination well if configured
                if self.config.get("liquid_handling", {}).get("pipetting_parameters", {}).get("mix_after_dispense", True):
                    self._mix_well(dest_well, row)

            # Drop tips
            self.lh.drop_tips(self.tip_rack_1, channels=channels)

            self._log(f"Transfer step {step}: Column {source_col} → Column {dest_col}")

        print("✓ Serial Transfer complete")
        self._log("Serial transfer sequence complete")

    def _mix_well(self, well: Container, channel: int) -> None:
        """
        Mix a well based on liquid handling parameters.

        Args:
            well: The well to mix
            channel: The channel to use
        """
        liquid_params = self.config.get("liquid_handling", {}).get("pipetting_parameters", {})
        mix_volume = liquid_params.get("mix_volume_ul", 40)
        mix_cycles = liquid_params.get("mix_cycles", 3)
        mix_delay = liquid_params.get("mix_delay_ms", 200)

        for _ in range(mix_cycles):
            self.lh.aspirate(resource=well, volume=mix_volume, channel=channel)
            self.lh.wait(mix_delay)
            self.lh.dispense(resource=well, volume=mix_volume, channel=channel)

    def calculate_concentrations(self) -> List[float]:
        """
        Calculate expected concentrations for each column.

        Returns:
            List of concentrations (µM) for each column
        """
        concentrations = []
        current_conc = self.STOCK_CONCENTRATION

        for col in range(self.NUM_COLUMNS):
            concentrations.append(current_conc)
            current_conc = current_conc / self.DILUTION_FACTOR

        self.concentrations = concentrations
        return concentrations

    def log_system_information(self) -> None:
        """Log system and configuration information."""
        print("\n" + "=" * 80)
        print("SYSTEM INFORMATION")
        print("=" * 80)

        protocol_info = self.config.get("protocol", {})
        print(f"Protocol: {protocol_info.get('name', 'Serial Dilution')}")
        print(f"Version: {protocol_info.get('version', '1.0')}")

        plate_info = self.plate_specs
        print(f"\nPlate Information:")
        print(f"  Manufacturer: {plate_info.get('manufacturer', 'Corning')}")
        print(f"  Product: {plate_info.get('product_name', 'N/A')}")
        print(f"  Product Code: {plate_info.get('product_code', 'N/A')}")
        print(f"  Format: {plate_info.get('geometry', {}).get('format', '96-well')}")
        print(f"  Material: {plate_info.get('well_specifications', {}).get('material', 'Polystyrene')}")
        print(f"  Max Well Volume: {plate_info.get('well_specifications', {}).get('well_volume_range', {}).get('max_ul', 360)} µL")
        print(f"  Surface Coating: {plate_info.get('surface_coating', 'TC treated')}")

        tip_info = self.tip_specs
        print(f"\nTip Information:")
        print(f"  Manufacturer: {tip_info.get('manufacturer', 'Hamilton')}")
        print(f"  Product Line: {tip_info.get('product_line', 'RoboTip®')}")
        print(f"  Capacity: {tip_info.get('specifications', {}).get('capacity_ul', 200)} µL")
        print(f"  Material: {tip_info.get('physical_specifications', {}).get('material', 'Polypropylene')}")
        print(f"  Coating: {tip_info.get('physical_specifications', {}).get('surface_coating', 'Ultra-Slip')}")

        print("=" * 80)

    def log_dilution_scheme(self) -> None:
        """Print and log the complete dilution scheme."""
        print("\n" + "=" * 80)
        print("DILUTION SCHEME & EXPECTED CONCENTRATIONS")
        print("=" * 80)
        print(f"{'Col':<5} {'Well':<12} {'Dilution':<15} {'Concentration':<20}")
        print("-" * 80)

        concentrations = self.calculate_concentrations()

        for col in range(self.NUM_COLUMNS):
            col_num = col + 1
            well_range = f"A{col_num}-H{col_num}"
            dilution = f"{self.DILUTION_FACTOR ** col}x"
            conc = f"{concentrations[col]:.6f} µM"

            print(f"{col_num:<5} {well_range:<12} {dilution:<15} {conc:<20}")
            self._log(f"Column {col_num}: {conc} (Dilution: {dilution})")

        print("=" * 80)

    def log_reagent_summary(self) -> None:
        """Print and log reagent requirements."""
        print("\n" + "=" * 80)
        print("REAGENT VOLUMES SUMMARY")
        print("=" * 80)

        reagent_info = self.config.get("reagent_requirements", {})
        stock_info = reagent_info.get("stock_solution", {})
        diluent_info = reagent_info.get("diluent", {})

        print(f"Stock Solution ({self.STOCK_CONCENTRATION} µM):")
        print(f"  Required: {stock_info.get('volume_required_ul', 400)} µL")
        print(f"  Recommended: {stock_info.get('volume_recommended_ul', 600)} µL")
        print(f"  Storage: {stock_info.get('storage_temperature', '2-8°C')}")

        print(f"\nDiluent/Buffer:")
        print(f"  Type: {diluent_info.get('type', 'PBS')}")
        print(f"  Required: {diluent_info.get('volume_required_ul', 4400)} µL")
        print(f"  Recommended: {diluent_info.get('volume_recommended_ul', 5500)} µL")
        print(f"  pH: {diluent_info.get('pH', 7.4)}")
        print(f"  Endotoxin Level: <{diluent_info.get('endotoxin_level_eu_ml', 0.05)} EU/mL")

        print(f"\nTransfer Scheme:")
        print(f"  Transfer volume per well: {self.TRANSFER_VOLUME} µL")
        print(f"  Final volume per well: {self.FINAL_VOLUME} µL")
        print(f"  Dilution ratio: 1:{self.DILUTION_FACTOR}")
        print(f"  Total wells: {self.NUM_COLUMNS * self.NUM_ROWS}")

        print("=" * 80)

    def verification_summary(self) -> None:
        """Generate and log a verification summary."""
        print("\n" + "=" * 80)
        print("PROTOCOL VERIFICATION SUMMARY")
        print("=" * 80)
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Protocol Type: {self.DILUTION_FACTOR}-Fold Serial Dilution")
        print(f"Number of Columns: {self.NUM_COLUMNS}")
        print(f"Number of Rows (Replicates): {self.NUM_ROWS}")
        print(f"Total Wells: {self.NUM_COLUMNS * self.NUM_ROWS}")
        print(f"\nConcentration Range: {self.STOCK_CONCENTRATION} µM → {self.concentrations[-1]:.6f} µM")
        print(f"Dilution Factor: {self.DILUTION_FACTOR}x per step")
        print(f"Total Dilution Range: {self.DILUTION_FACTOR ** (self.NUM_COLUMNS - 1)}x")
        print("=" * 80)

        self._log("Protocol verification summary generated")

    def _log(self, message: str) -> None:
        """Add an entry to the protocol log."""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"[{timestamp}] {message}"
        self.log_entries.append(log_entry)

    def get_log(self) -> List[str]:
        """Retrieve the complete protocol log."""
        return self.log_entries

    def save_log(self, filename: str = None) -> None:
        """Save the protocol log to a file."""
        if not filename:
            filename = self.config.get("logging", {}).get("log_file", "serial_dilution_protocol_log.txt")

        with open(filename, 'w') as f:
            f.write("Serial Dilution Protocol Log\n")
            f.write("=" * 80 + "\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 80 + "\n\n")

            for entry in self.log_entries:
                f.write(entry + "\n")

        print(f"\n✓ Log saved to {filename}")


# ============================================================================
# MAIN EXECUTION FUNCTION
# ============================================================================

def run_serial_dilution_protocol(
    config_file: str = "config.json",
    simulator: bool = True
) -> None:
    """
    Execute the complete serial dilution protocol using configuration file.

    Args:
        config_file: Path to JSON configuration file
        simulator: If True, use simulator backend; if False, use real hardware
    """
    print("=" * 80)
    print("SERIAL DILUTION PROTOCOL - PYLABROBOT (Configuration-Driven)")
    print("=" * 80)
    print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    try:
        # Load and validate configuration
        config_mgr = ConfigurationManager(config_file)
        config = config_mgr.load_config()

        if not config_mgr.validate_config():
            print("\n✗ Configuration validation failed. Exiting.")
            sys.exit(1)

        # Initialize liquid handler
        if simulator:
            print("Using SIMULATOR backend...")
            from pylabrobot.liquid_handling.backends.simulator import Simulator
            backend = Simulator()
        else:
            print("Using HAMILTON backend (ensure device is connected)...")
            from pylabrobot.liquid_handling.backends import Hamilton
            backend = Hamilton()

        # Create liquid handler instance
        lh = LiquidHandler(backend=backend)
        lh.connect()

        # Initialize protocol with configuration
        protocol = SerialDilutionProtocol(lh, config)

        # Execute protocol steps
        print("\n" + "-" * 80)
        protocol.log_system_information()

        print("\n" + "-" * 80)
        protocol.setup_labware()

        print("\n" + "-" * 80)
        protocol.log_reagent_summary()

        print("\n" + "-" * 80)
        protocol.log_dilution_scheme()

        print("\n" + "-" * 80)
        protocol.pre_dilution_setup()

        print("\n" + "-" * 80)
        protocol.serial_transfer()

        print("\n" + "-" * 80)
        protocol.verification_summary()

        # Save log
        protocol.save_log()

        # Disconnect
        lh.disconnect()

        print("\n" + "=" * 80)
        print("✓ PROTOCOL COMPLETED SUCCESSFULLY")
        print("=" * 80)

    except Exception as e:
        print(f"\n✗ ERROR: {str(e)}", file=sys.stderr)
        print("Protocol execution failed. Check error details above.")
        import traceback
        traceback.print_exc()
        sys.exit(1)


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    """
    Main entry point for the configuration-driven serial dilution protocol.

    Usage:
        python serial_dilution_pylabrobot_v2.py                    # Default config
        python serial_dilution_pylabrobot_v2.py --config custom.json
        python serial_dilution_pylabrobot_v2.py --hw               # Real hardware
    """

    import argparse

    parser = argparse.ArgumentParser(
        description="PyLabRobot Serial Dilution Protocol (Configuration-Driven)"
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config.json",
        help="Path to configuration file (default: config.json)"
    )
    parser.add_argument(
        "--hw",
        action="store_true",
        help="Run with real Hamilton hardware (default is simulator)"
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate configuration and exit without running protocol"
    )

    args = parser.parse_args()

    # Validate configuration if requested
    if args.validate_only:
        config_mgr = ConfigurationManager(args.config)
        config_mgr.load_config()
        if config_mgr.validate_config():
            print("\n✓ Configuration is valid")
            sys.exit(0)
        else:
            sys.exit(1)

    # Run protocol
    run_serial_dilution_protocol(
        config_file=args.config,
        simulator=not args.hw
    )

# ============================================================================
# END OF PROTOCOL
# ============================================================================
