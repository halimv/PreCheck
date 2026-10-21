# Configuration Guide - PyLabRobot Serial Dilution Protocol

## Overview

The updated PyLabRobot serial dilution protocol uses a JSON configuration file (`config.json`) to manage all protocol parameters, hardware specifications, and experimental settings. This approach provides:

- **Hardware-agnostic flexibility** - easily switch between different plates, tips, and reservoirs
- **Reproducible experiments** - all parameters documented in version-controlled config files
- **Easy customization** - modify parameters without editing Python code
- **Validation** - built-in configuration validation

## Configuration File Structure

### 1. Protocol Information

```json
{
  "protocol": {
    "name": "Serial Dilution Protocol",
    "description": "Automated 2-fold serial dilution",
    "version": "1.0",
    "author": "PyLabRobot Protocol Generator"
  }
}
```

### 2. Dilution Parameters

Core parameters for the dilution experiment:

```json
{
  "dilution_parameters": {
    "stock_concentration_um": 1000,      // Starting concentration in µM
    "dilution_factor": 2,                 // 2-fold, 3-fold, etc.
    "num_columns": 12,                    // Number of dilution steps
    "num_rows": 8,                        // Replicates per concentration
    "final_volume_ul": 100,               // Final volume per well
    "transfer_volume_ul": 50,             // Volume transferred between columns
    "diluent_volume_ul": 50               // Diluent volume per well
  }
}
```

**Common Configurations:**

#### 2-Fold Serial Dilution (Default)
```json
"dilution_factor": 2,
"transfer_volume_ul": 50,
"diluent_volume_ul": 50,
"final_volume_ul": 100
```
Creates 1:1 ratio in each step (50+50=100 µL)

#### 3-Fold Serial Dilution
```json
"dilution_factor": 3,
"transfer_volume_ul": 33,
"diluent_volume_ul": 67,
"final_volume_ul": 100
```
Creates 1:2 ratio (33 µL sample + 67 µL diluent)

#### 4-Fold Serial Dilution
```json
"dilution_factor": 4,
"transfer_volume_ul": 25,
"diluent_volume_ul": 75,
"final_volume_ul": 100
```

### 3. Plate Specifications (Corning 96-Well)

Technical data for **Corning® 96-well Flat Bottom Microplate (Product #3595)**:

```json
{
  "plate_specifications": {
    "manufacturer": "Corning",
    "product_name": "Corning® 96-well Flat Bottom Microplate",
    "product_code": "3595",
    "well_format": "96-well",
    "surface_coating": "TC treated polystyrene",
    "geometry": {
      "format": "8 rows × 12 columns",
      "row_count": 8,
      "column_count": 12,
      "well_spacing_mm": 9,
      "plate_width_mm": 127,
      "plate_length_mm": 85,
      "plate_height_mm": 10.67
    },
    "well_specifications": {
      "well_diameter_mm": 6.86,
      "well_depth_mm": 10.67,
      "well_volume_range": {
        "min_ul": 5,
        "max_ul": 360,
        "working_volume_ul": 340,
        "assay_volume_ul": 100
      },
      "bottom_type": "Flat",
      "material": "Polystyrene",
      "optical_properties": "Clear/Transparent"
    }
  }
}
```

#### Alternative Corning Plates

**Corning #3603 - Black Round-bottom**
```json
"product_code": "3603",
"product_name": "Corning® 96-well Black Round Bottom",
"well_specifications": {
  "bottom_type": "Round",
  "optical_properties": "Black (good for fluorescence)"
}
```

**Corning #3610 - V-bottom**
```json
"product_code": "3610",
"product_name": "Corning® 96-well V-Bottom Microplate",
"well_specifications": {
  "bottom_type": "V-shaped",
  "optical_properties": "Clear (good for cell culture)"
}
```

### 4. Hamilton Tips Specifications

Technical data for **Hamilton RoboTip® 200 µL Tips**:

```json
{
  "hamilton_tips": {
    "tip_type": "Standard Volume Multi-Channel Tips",
    "manufacturer": "Hamilton",
    "product_line": "RoboTip®",
    "specifications": {
      "capacity_ul": 200,
      "minimum_volume_ul": 2,
      "maximum_volume_ul": 200,
      "accuracy_range": "10-200 µL",
      "volume_ranges": [
        {
          "range_ul": "2-10",
          "cv_percent": "7.5"
        },
        {
          "range_ul": "10-50",
          "cv_percent": "4.0"
        },
        {
          "range_ul": "50-200",
          "cv_percent": "2.0"
        }
      ]
    },
    "physical_specifications": {
      "length_mm": 59.3,
      "outer_diameter_mm": 2.4,
      "inner_diameter_mm": 1.6,
      "material": "Polypropylene",
      "surface_coating": "Ultra-Slip",
      "tip_color": "Clear/Natural"
    },
    "compatibility": {
      "hamilton_models": [
        "MICROLAB STAR",
        "VANTAGE",
        "INTERPRETER™",
        "STARlet®",
        "NIMBUS"
      ],
      "head_type": "8-channel or 96-channel"
    }
  }
}
```

#### Alternative Hamilton Tips

**RoboTip® 1000 µL** - For larger volumes
```json
"product_line": "RoboTip® 1000",
"specifications": {
  "capacity_ul": 1000,
  "minimum_volume_ul": 10,
  "maximum_volume_ul": 1000
}
```

**RoboTip® with Filter** - For sensitive applications
```json
"product_line": "RoboTip® 200 with Filter",
"physical_specifications": {
  "filter_type": "Aerosol barrier filter"
}
```

**RoboTip® LpB (Low Protein Binding)**
```json
"product_line": "RoboTip® LpB",
"physical_specifications": {
  "coating": "Low protein binding surface"
}
```

### 5. Deck Configuration

Specifies the layout of labware on the Hamilton deck:

```json
{
  "deck_configuration": {
    "platform": "Hamilton MICROLAB STAR",
    "deck_layout": [
      {
        "position": [0, 0],
        "labware": "target_plate",
        "type": "Corning 96-well Plate"
      },
      {
        "position": [1, 0],
        "labware": "tip_rack_1",
        "type": "Hamilton 96-tip Rack"
      },
      {
        "position": [2, 0],
        "labware": "tip_rack_2",
        "type": "Hamilton 96-tip Rack"
      },
      {
        "position": [3, 0],
        "labware": "stock_tube",
        "type": "15 mL Screw-cap Tube"
      },
      {
        "position": [4, 0],
        "labware": "diluent_reservoir",
        "type": "50 mL Deep-well Reservoir"
      }
    ]
  }
}
```

### 6. Liquid Handling Parameters

Controls pipetting behavior and tip management:

```json
{
  "liquid_handling": {
    "pipetting_parameters": {
      "liquid_class": "Water",
      "aspiration_speed_ul_s": 25,
      "dispensing_speed_ul_s": 25,
      "mix_cycles": 3,
      "mix_volume_ul": 40,
      "air_gap_ul": 5,
      "pre_wet": false,
      "mix_after_dispense": true
    },
    "tip_management": {
      "tip_reuse": false,
      "air_gap_after_aspirate_ul": 5,
      "drip_delay_ms": 100,
      "tip_touch": false
    },
    "delays": {
      "aspirate_settling_ms": 200,
      "dispense_settling_ms": 200,
      "inter_tip_delay_ms": 100,
      "mix_delay_ms": 200
    }
  }
}
```

### 7. Reagent Requirements

Specifies volumes and properties of reagents:

```json
{
  "reagent_requirements": {
    "stock_solution": {
      "concentration_um": 1000,
      "volume_required_ul": 400,
      "volume_recommended_ul": 600,
      "storage_temperature": "2-8°C",
      "stability_days": 30
    },
    "diluent": {
      "type": "PBS or equivalent buffer",
      "volume_required_ul": 4400,
      "volume_recommended_ul": 5500,
      "pH": 7.4,
      "osmolarity_mosm_l": 310,
      "sterile": true,
      "endotoxin_level_eu_ml": "<0.05"
    }
  }
}
```

## Running the Protocol with Configuration

### Basic Usage

```bash
# Run with default config.json
python serial_dilution_pylabrobot_v2.py

# Run with custom configuration
python serial_dilution_pylabrobot_v2.py --config my_custom_config.json

# Run on real hardware
python serial_dilution_pylabrobot_v2.py --hw

# Validate configuration only
python serial_dilution_pylabrobot_v2.py --validate-only
```

### Configuration Priority

1. Command-line arguments (highest priority)
2. Configuration file values
3. Hardcoded defaults (lowest priority)

## Creating Custom Configurations

### Example 1: Different Plate Type (Black Round-Bottom)

Start with `config.json` and modify:

```json
{
  "plate_specifications": {
    "product_code": "3603",
    "product_name": "Corning® 96-well Black Round Bottom",
    "well_specifications": {
      "bottom_type": "Round",
      "optical_properties": "Black"
    }
  }
}
```

Save as `config_fluorescence.json` and run:
```bash
python serial_dilution_pylabrobot_v2.py --config config_fluorescence.json
```

### Example 2: 3-Fold Dilution with 10 Points

```json
{
  "dilution_parameters": {
    "stock_concentration_um": 2000,
    "dilution_factor": 3,
    "num_columns": 10,
    "num_rows": 8,
    "final_volume_ul": 100,
    "transfer_volume_ul": 33,
    "diluent_volume_ul": 67
  }
}
```

### Example 3: Higher Concentration Starting Point

```json
{
  "dilution_parameters": {
    "stock_concentration_um": 10000,
    "dilution_factor": 2,
    "num_columns": 12,
    "num_rows": 8,
    "final_volume_ul": 100,
    "transfer_volume_ul": 50,
    "diluent_volume_ul": 50
  }
}
```

### Example 4: Protein Handling (Low-Binding Tips)

```json
{
  "hamilton_tips": {
    "product_line": "RoboTip® LpB",
    "physical_specifications": {
      "coating": "Low protein binding surface"
    }
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

## Configuration Validation

The protocol includes built-in validation:

```bash
python serial_dilution_pylabrobot_v2.py --validate-only
```

Checks for:
- ✓ Required configuration sections
- ✓ Required dilution parameters
- ✓ Valid numerical values
- ✓ Logical parameter relationships (e.g., transfer_volume < final_volume)

## Corning Plate Technical Specifications Reference

### Corning #3595 (Flat Bottom) - DEFAULT
- **Use Cases**: ELISA, general assays, cell culture
- **Max Volume**: 360 µL
- **Bottom**: Flat
- **Surface**: TC treated polystyrene
- **Assay Volume**: 100 µL (our default)

### Corning #3603 (Black Round-Bottom)
- **Use Cases**: Fluorescence, luminescence assays
- **Max Volume**: 360 µL
- **Bottom**: Round
- **Color**: Black opaque
- **Advantage**: Minimizes crosstalk between wells

### Corning #3610 (V-Bottom)
- **Use Cases**: Cell culture, immunoassays
- **Max Volume**: 300 µL
- **Bottom**: V-shaped
- **Advantage**: Better for cell pellet management
- **Note**: Not suitable for plate readers

### Corning #3650 (Ultra-Low Attachment)
- **Use Cases**: Spheroid/organoid culture
- **Max Volume**: 360 µL
- **Bottom**: Flat
- **Surface**: Ultra-low protein binding
- **Advantage**: Prevents cell attachment

## Hamilton Tip Technical Specifications Reference

### RoboTip® 200 µL - STANDARD
- **Capacity**: 200 µL
- **Accuracy**: ±2% at 50-200 µL (CV 2.0%)
- **Material**: Polypropylene
- **Coating**: Ultra-Slip
- **Pack Size**: 96 tips/rack

### RoboTip® 1000 µL
- **Capacity**: 1000 µL
- **Accuracy**: ±2% at 500-1000 µL
- **Use**: Large volume transfers, reservoir handling
- **Best for**: Stock solution preparation

### RoboTip® 200 µL with Filter
- **Capacity**: 200 µL
- **Filter**: Aerosol barrier (0.2 µm)
- **Use**: PCR, sensitive biologics
- **Advantage**: Prevents aerosol contamination

### RoboTip® LpB (Low Protein Binding)
- **Capacity**: 200 µL
- **Material**: Polypropylene with special coating
- **Use**: Antibodies, recombinant proteins, enzymes
- **Advantage**: Minimizes protein loss (typically <5%)

## Troubleshooting Configuration Issues

### Error: "Configuration validation failed"

Check:
- File is valid JSON (use online JSON validator)
- All required sections present
- No typos in section names

### Error: "ModuleNotFoundError: No module named 'pylabrobot'"

```bash
pip install pylabrobot
```

### Tips not available for transfer

Check `deck_configuration`:
- Tip rack positions must be consistent with physical setup
- Verify tip capacity matches transfer volumes
- Ensure sufficient tips for all transfers

### Incorrect concentration calculations

Verify in config:
```
transfer_volume_ul + diluent_volume_ul = final_volume_ul
```

For 2-fold: 50 + 50 = 100 ✓

## Performance Tips

1. **Use correct liquid class** - affects speed and accuracy
   - Water/Buffer: standard speed
   - Protein: slower, pre-wet enabled
   - Viscous: slower with mixing

2. **Optimize mixing** - balance thoroughness with speed
   - Default: 3 cycles of 40 µL
   - Increase for: viscous, concentrated solutions
   - Decrease for: fast, high-throughput runs

3. **Tip selection** - match application needs
   - Standard: most applications
   - Filtered: sterile/sensitive work
   - Low-binding: protein/antibody work

## Configuration File Distribution

For reproducible science:
1. Version control `config.json` alongside protocol
2. Include in supplementary materials
3. Document any deviations from defaults
4. Archive experiment-specific configurations

## Additional Resources

- [Corning Application Notes](https://www.corning.com/worldwide/en/products/life-sciences/products/microplates.html)
- [Hamilton Robotics Documentation](https://www.hamiltoncompany.com)
- [PyLabRobot Documentation](https://docs.pylabrobot.org)

---

**Version**: 1.0  
**Last Updated**: 2024-01-15  
**Configuration Schema**: JSON
