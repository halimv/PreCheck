# PyLabRobot Serial Dilution Protocol - Configuration-Driven Edition

## Overview

This is a production-ready, configuration-driven serial dilution protocol for Hamilton liquid handlers using PyLabRobot. All hardware specifications (Corning plates, Hamilton tips) and experimental parameters are managed through external configuration files, enabling:

✅ **Hardware specifications** from technical datasheets (Corning 96-well plates, Hamilton RoboTip®)  
✅ **Zero Python modifications** - all customization via config files  
✅ **Reproducibility** - version-control your configurations  
✅ **Flexibility** - easily swap hardware, adjust dilution parameters  
✅ **Validation** - built-in configuration checking  
✅ **Both JSON & YAML** formats supported  

## Files Included

| File | Purpose |
|------|---------|
| `serial_dilution_pylabrobot_v2.py` | Main protocol script (configuration-driven) |
| `config.json` | Default configuration (JSON format) |
| `config.yaml` | Alternative configuration (YAML format) |
| `CONFIG_GUIDE.md` | Detailed configuration documentation |
| `Serial_Dilution_Experimental_Plan.txt` | Experimental parameters reference |
| `PYLABROBOT_USAGE_GUIDE.md` | Usage guide (original version) |
| `README_CONFIG_DRIVEN.md` | This file |

## Quick Start

### 1. Install Dependencies

```bash
pip install pylabrobot pyyaml
```

### 2. Run with Default Configuration

```bash
python serial_dilution_pylabrobot_v2.py
```

This runs the simulator with `config.json`.

### 3. Run with YAML Configuration

```bash
python serial_dilution_pylabrobot_v2.py --config config.yaml
```

### 4. Validate Configuration

```bash
python serial_dilution_pylabrobot_v2.py --config config.json --validate-only
```

### 5. Run on Real Hardware

```bash
python serial_dilution_pylabrobot_v2.py --hw
```

## Configuration File Format

### Using JSON (Default)

```json
{
  "dilution_parameters": {
    "stock_concentration_um": 1000,
    "dilution_factor": 2,
    "num_columns": 12
  }
}
```

**Advantages:**
- Strict validation
- Wide tool support
- Compact format

### Using YAML (Recommended for humans)

```yaml
dilution_parameters:
  stock_concentration_um: 1000
  dilution_factor: 2
  num_columns: 12
```

**Advantages:**
- More readable
- Comments supported
- Natural language structure

### Converting Between Formats

**JSON to YAML:**
```bash
python -c "import json, yaml; print(yaml.dump(json.load(open('config.json'))))" > config.yaml
```

**YAML to JSON:**
```bash
python -c "import json, yaml; print(json.dumps(yaml.safe_load(open('config.yaml'))))" > config.json
```

## Hardware Specifications Included

### Corning 96-Well Plates

Technical specifications from Corning datasheets:

**Corning #3595 (Flat Bottom)** - DEFAULT
- Capacity: 360 µL per well
- Material: Polystyrene, TC-treated
- Dimensions: 127 × 85 × 10.67 mm
- Well spacing: 9 mm
- Surface: Clear, optimal for assays
- Use cases: ELISA, general assays, cell culture

Alternative plate types available in config:
- **#3603**: Black Round-Bottom (fluorescence assays)
- **#3610**: V-Bottom (cell culture)
- **#3650**: Ultra-Low Attachment (spheroid culture)

### Hamilton RoboTip® Tips

Technical specifications from Hamilton datasheets:

**RoboTip® 200 µL** - DEFAULT
- Capacity: 200 µL
- Accuracy: ±2% CV at 50-200 µL
- Material: Polypropylene with Ultra-Slip coating
- Sterile: Pre-sterilized, pyrogen-free
- Packaging: 96 tips per rack
- Compatible with: MICROLAB STAR, VANTAGE, STARlet®, NIMBUS

Alternative tip types available:
- **RoboTip® 1000 µL**: For large volumes
- **RoboTip® with Filter**: For PCR/sensitive work
- **RoboTip® LpB**: Low-protein binding for biologics

## Creating Custom Configurations

### Example 1: Quick 3-Fold Dilution

Save as `config_3fold.json`:

```json
{
  "dilution_parameters": {
    "stock_concentration_um": 2000,
    "dilution_factor": 3,
    "num_columns": 10,
    "transfer_volume_ul": 33,
    "diluent_volume_ul": 67
  }
}
```

Run:
```bash
python serial_dilution_pylabrobot_v2.py --config config_3fold.json
```

### Example 2: Fluorescence Assay (Black Plate)

Save as `config_fluorescence.json`:

```json
{
  "plate_specifications": {
    "product_code": "3603",
    "product_name": "Corning® 96-well Black Round Bottom"
  },
  "dilution_parameters": {
    "stock_concentration_um": 100
  }
}
```

### Example 3: Protein Handling (Low-Binding Tips)

Save as `config_protein.json`:

```json
{
  "hamilton_tips": {
    "product_line": "RoboTip® LpB"
  },
  "liquid_handling": {
    "pipetting_parameters": {
      "liquid_class": "Protein",
      "pre_wet": true,
      "mix_after_dispense": false
    }
  }
}
```

### Example 4: High-Throughput (Reduced Mixing)

Save as `config_highthroughput.json`:

```json
{
  "liquid_handling": {
    "pipetting_parameters": {
      "mix_cycles": 1,
      "aspiration_speed_ul_s": 50,
      "dispensing_speed_ul_s": 50
    }
  }
}
```

## Configuration Priority & Inheritance

The protocol loads configurations in this order:

1. **Hardcoded defaults** (lowest priority)
2. **config.json or config.yaml**
3. **Command-line arguments** (highest priority)

### Partial Configuration Example

You can create minimal configs that override only specific parameters:

```json
{
  "dilution_parameters": {
    "stock_concentration_um": 5000
  }
}
```

All other parameters will use values from `config.json` or defaults.

## Understanding the Configuration Structure

### Dilution Parameters

```json
{
  "dilution_parameters": {
    "stock_concentration_um": 1000,    // Starting concentration
    "dilution_factor": 2,              // Fold dilution per step
    "num_columns": 12,                 // Dilution points (1-12)
    "num_rows": 8,                     // Replicates per concentration
    "final_volume_ul": 100,            // Total volume per well
    "transfer_volume_ul": 50,          // Volume from previous column
    "diluent_volume_ul": 50            // Diluent volume added
  }
}
```

**Constraint:** `transfer_volume + diluent_volume = final_volume`

### Plate Specifications

Corning technical data included for:
- Geometry (dimensions, well spacing)
- Well specifications (volume range, material, optical properties)
- Surface treatments (TC, ultra-low attachment)
- Storage conditions

### Hamilton Tips

Hamilton technical data included for:
- Capacity and accuracy specifications
- Physical dimensions
- Surface coatings (Ultra-Slip, LpB)
- Compatibility information
- Packaging and storage

### Liquid Handling Parameters

Controls pipetting behavior:
- **Aspiration/dispensing speeds**: 25 µL/s (adjustable)
- **Mixing**: 3 cycles of 40 µL (configurable)
- **Air gaps**: 5 µL (reduces droplet formation)
- **Delays**: Between operations for liquid stabilization

### Deck Configuration

Specifies Hamilton deck layout:
- Position coordinates for each labware
- Container types and capacities
- Descriptions for reference

## Configuration Validation

The protocol validates:

✓ All required sections present  
✓ All required dilution parameters set  
✓ Mathematical consistency (volumes add up)  
✓ Parameter ranges (positive values, realistic)  
✓ File format (valid JSON/YAML)  

Run validation:
```bash
python serial_dilution_pylabrobot_v2.py --validate-only
```

## Output & Logging

### Console Output

The protocol prints:
- System information (plate, tips, version)
- Dilution scheme with all concentrations
- Reagent volume requirements
- Protocol execution status
- Final verification summary

### Log File

Detailed timestamped log saved to `serial_dilution_protocol_log.txt`:

```
[2024-01-15 10:23:45] Labware setup complete - deck configured
[2024-01-15 10:23:46] Pre-Dilution Setup complete - 50 µL diluent dispensed
[2024-01-15 10:23:52] Transfer step 1: Column 1 → Column 2
[2024-01-15 10:23:58] Transfer step 2: Column 2 → Column 3
...
```

### Customizing Output

Modify in config:
```json
{
  "logging": {
    "log_file": "my_experiment_log.txt",
    "log_level": "INFO",
    "include_in_log": ["timestamp", "operation_name", "volume_ul", "status"]
  }
}
```

## Reproducible Experimental Workflows

### Step 1: Create Experiment-Specific Config

```bash
cp config.json experiments/experiment_2024_01_15.json
# Edit with your parameters
```

### Step 2: Version Control Configuration

```bash
git add experiments/experiment_2024_01_15.json
git commit -m "Serial dilution config for IC50 determination - compound X"
```

### Step 3: Run Protocol

```bash
python serial_dilution_pylabrobot_v2.py --config experiments/experiment_2024_01_15.json
```

### Step 4: Archive Results

```bash
mkdir results/experiment_2024_01_15
cp serial_dilution_protocol_log.txt results/experiment_2024_01_15/
cp experiments/experiment_2024_01_15.json results/experiment_2024_01_15/
```

## Troubleshooting

### Configuration Won't Load

```
FileNotFoundError: Configuration file not found: config.json
```

**Solution:** Ensure config file is in the same directory as the script, or provide full path:
```bash
python serial_dilution_pylabrobot_v2.py --config /path/to/config.json
```

### Validation Fails

```
Configuration validation errors:
  ✗ Missing dilution parameter: stock_concentration_um
```

**Solution:** Add missing parameter to config:
```json
{
  "dilution_parameters": {
    "stock_concentration_um": 1000
  }
}
```

### Volumes Don't Add Up

```
transfer_volume_ul (50) + diluent_volume_ul (50) ≠ final_volume_ul (100)
```

**Solution:** Ensure arithmetic is correct:
- For 2-fold: 50 + 50 = 100 ✓
- For 3-fold: 33 + 67 = 100 ✓

### Tips Not Picking Up

Check:
- Tip rack position in `deck_configuration`
- Tip capacity matches transfer volumes
- Tip rack is loaded and accessible

## Advanced Usage

### Programmatic Configuration

Load and modify config in Python:

```python
import json
from serial_dilution_pylabrobot_v2 import ConfigurationManager, SerialDilutionProtocol

# Load config
config_mgr = ConfigurationManager('config.json')
config = config_mgr.load_config()

# Modify parameters
config['dilution_parameters']['stock_concentration_um'] = 5000

# Validate
config_mgr.config = config
if config_mgr.validate_config():
    print("Modified config is valid")
```

### Batch Processing Multiple Experiments

```bash
for conc in 100 500 1000 5000; do
  config_file="config_stock_${conc}.json"
  cat config.json | sed "s/\"stock_concentration_um\": [0-9]*/\"stock_concentration_um\": $conc/" > $config_file
  python serial_dilution_pylabrobot_v2.py --config $config_file
done
```

### Integration with Data Analysis

```python
from serial_dilution_pylabrobot_v2 import SerialDilutionProtocol
import json

# Load config and protocol
with open('config.json') as f:
    config = json.load(f)

protocol = SerialDilutionProtocol(None, config)
concentrations = protocol.calculate_concentrations()

# Pass to analysis pipeline
analyze_dose_response(concentrations)
```

## Best Practices

1. **Version control your configs**
   ```bash
   git add config_*.json
   git commit -m "Configuration for experiment series"
   ```

2. **Use descriptive filenames**
   ```
   config_fluorescence_hts.json
   config_protein_binding.json
   config_validation_run.json
   ```

3. **Document deviations**
   ```json
   {
     "notes": "Modified mix_volume_ul from 40 to 30 for viscous solutions"
   }
   ```

4. **Archive configurations with results**
   ```bash
   mkdir results/2024_01_15_experiment
   cp config.json results/2024_01_15_experiment/
   cp *.log results/2024_01_15_experiment/
   ```

5. **Test with simulator first**
   ```bash
   python serial_dilution_pylabrobot_v2.py --validate-only
   python serial_dilution_pylabrobot_v2.py  # Simulator mode
   # Then:
   python serial_dilution_pylabrobot_v2.py --hw  # Real hardware
   ```

## Supported Hardware Platforms

The configuration supports these Hamilton platforms:
- MICROLAB STAR
- VANTAGE
- STARlet®
- INTERPRETER™
- NIMBUS

Modify in config:
```json
{
  "deck_configuration": {
    "platform": "Hamilton VANTAGE"
  }
}
```

## Documentation References

### Technical Datasheets

- **Corning 96-well plates**: https://www.corning.com/products/microplates
- **Hamilton RoboTip®**: https://www.hamiltoncompany.com/liquids-handling
- **PyLabRobot**: https://docs.pylabrobot.org

### Configuration Schema

The configuration follows a hierarchical structure:
```
protocol/
├── dilution_parameters/
├── plate_specifications/
│   ├── geometry/
│   └── well_specifications/
├── hamilton_tips/
│   ├── specifications/
│   └── physical_specifications/
├── deck_configuration/
├── liquid_handling/
├── reagent_requirements/
├── quality_control/
├── experimental_design/
└── logging/
```

## Support & Troubleshooting

For issues:
1. Check `CONFIG_GUIDE.md` for detailed parameter descriptions
2. Validate configuration: `--validate-only`
3. Review console output for specific errors
4. Consult PyLabRobot documentation: https://docs.pylabrobot.org
5. Check Hamilton device documentation

## License & Attribution

This protocol uses:
- **PyLabRobot**: Open-source liquid handling framework
- **Corning Specifications**: From Corning technical datasheets
- **Hamilton Specifications**: From Hamilton technical documentation

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2024-01-15 | Initial release - configuration-driven architecture |
| 0.9 | 2024-01-10 | Beta - HSL version |

## Future Enhancements

Planned features:
- YAML schema validation
- Interactive configuration wizard
- Configuration merging from multiple files
- Database integration for parameter logging
- Web UI for configuration management

## Contact & Contributing

For questions or contributions, please refer to the PyLabRobot community at https://pylabrobot.org

---

**Last Updated**: 2024-01-15  
**Maintained By**: PyLabRobot Protocol Generator  
**Status**: Production Ready ✓
