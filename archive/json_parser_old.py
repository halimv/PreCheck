import json
from typing import Dict, Any

class ProtocolParser:
    def __init__(self, labware_path: str, protocol_path: str):
        with open(labware_path, "r") as f:
            self.labware_lib = json.load(f)
        with open(protocol_path, "r") as f:
            self.protocol = json.load(f)
            
    def get_resolved_config(self) -> Dict[str, Any]:
        """Resolves labware_references to physical specs from labware_config.json"""
        refs = self.protocol["labware_references"]
        
        # Look up plate specs
        plate_ref = refs["plate"]
        plate_spec = self.labware_lib["plates"].get(plate_ref)
        if not plate_spec:
            raise ValueError(f"Plate reference '{plate_ref}' not found in labware_config.json")
            
        # Look up tip specs
        tip_ref = refs["tips_serial_transfer"]
        tip_spec = self.labware_lib["tips"].get(tip_ref)
        if not tip_spec:
            raise ValueError(f"Tip reference '{tip_ref}' not found in labware_config.json")

        return {
            "parameters": self.protocol["dilution_parameters"],
            "plate_spec": plate_spec,
            "tip_spec": tip_spec,
            "tip_management": self.protocol["liquid_handling"]["tip_management"],
            "deck_layout": self.protocol["deck_configuration"]["deck_layout"]
        }