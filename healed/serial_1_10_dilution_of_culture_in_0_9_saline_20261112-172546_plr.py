"""Compiled from protocol: Serial 1:10 dilution of culture in 0.9% saline. Do not edit; recompile from the IR."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # repo root, for pipeline.deck


async def run_protocol(lh, res):
    # step 1: Pick up tip column 1 for saline prefill
    await lh.pick_up_tips([res["tips"].get_item("A1"), res["tips"].get_item("B1"), res["tips"].get_item("C1"), res["tips"].get_item("D1"), res["tips"].get_item("E1"), res["tips"].get_item("F1"), res["tips"].get_item("G1"), res["tips"].get_item("H1")], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 2: Aspirate 180 uL diluent with channel 0 only (single channel to respect 9 mm spacing in the diluent container)
    await lh.aspirate([res["diluent"]] * 1, vols=[180.0], use_channels=[0])
    # step 3: Aspirate 180 uL diluent with channel 1 only (single channel to respect 9 mm spacing in the diluent container)
    await lh.aspirate([res["diluent"]] * 1, vols=[180.0], use_channels=[1])
    # step 4: Aspirate 180 uL diluent with channel 2 only (single channel to respect 9 mm spacing in the diluent container)
    await lh.aspirate([res["diluent"]] * 1, vols=[180.0], use_channels=[2])
    # step 5: Aspirate 180 uL diluent with channel 3 only (single channel to respect 9 mm spacing in the diluent container)
    await lh.aspirate([res["diluent"]] * 1, vols=[180.0], use_channels=[3])
    # step 6: Aspirate 180 uL diluent with channel 4 only (single channel to respect 9 mm spacing in the diluent container)
    await lh.aspirate([res["diluent"]] * 1, vols=[180.0], use_channels=[4])
    # step 7: Aspirate 180 uL diluent with channel 5 only (single channel to respect 9 mm spacing in the diluent container)
    await lh.aspirate([res["diluent"]] * 1, vols=[180.0], use_channels=[5])
    # step 8: Aspirate 180 uL diluent with channel 6 only (single channel to respect 9 mm spacing in the diluent container)
    await lh.aspirate([res["diluent"]] * 1, vols=[180.0], use_channels=[6])
    # step 9: Aspirate 180 uL diluent with channel 7 only (single channel to respect 9 mm spacing in the diluent container)
    await lh.aspirate([res["diluent"]] * 1, vols=[180.0], use_channels=[7])
    # step 10: Dispense 90 uL saline into column 1
    await lh.dispense([res["dilution_plate"].get_item("A1"), res["dilution_plate"].get_item("B1"), res["dilution_plate"].get_item("C1"), res["dilution_plate"].get_item("D1"), res["dilution_plate"].get_item("E1"), res["dilution_plate"].get_item("F1"), res["dilution_plate"].get_item("G1"), res["dilution_plate"].get_item("H1")], vols=[90.0, 90.0, 90.0, 90.0, 90.0, 90.0, 90.0, 90.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 11: Dispense 90 uL saline into column 2
    await lh.dispense([res["dilution_plate"].get_item("A2"), res["dilution_plate"].get_item("B2"), res["dilution_plate"].get_item("C2"), res["dilution_plate"].get_item("D2"), res["dilution_plate"].get_item("E2"), res["dilution_plate"].get_item("F2"), res["dilution_plate"].get_item("G2"), res["dilution_plate"].get_item("H2")], vols=[90.0, 90.0, 90.0, 90.0, 90.0, 90.0, 90.0, 90.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 12: Aspirate 180 uL diluent with channel 0 (single channel, fits 9 mm container)
    await lh.aspirate([res["diluent"]] * 1, vols=[180.0], use_channels=[0])
    # step 13: Aspirate 180 uL diluent with channel 1 (single channel, fits 9 mm container)
    await lh.aspirate([res["diluent"]] * 1, vols=[180.0], use_channels=[1])
    # step 14: Aspirate 180 uL diluent with channel 2 (single channel, fits 9 mm container)
    await lh.aspirate([res["diluent"]] * 1, vols=[180.0], use_channels=[2])
    # step 15: Aspirate 180 uL diluent with channel 3 (single channel, fits 9 mm container)
    await lh.aspirate([res["diluent"]] * 1, vols=[180.0], use_channels=[3])
    # step 16: Aspirate 180 uL diluent with channel 4 (single channel, fits 9 mm container)
    await lh.aspirate([res["diluent"]] * 1, vols=[180.0], use_channels=[4])
    # step 17: Aspirate 180 uL diluent with channel 5 (single channel, fits 9 mm container)
    await lh.aspirate([res["diluent"]] * 1, vols=[180.0], use_channels=[5])
    # step 18: Aspirate 180 uL diluent with channel 6 (single channel, fits 9 mm container)
    await lh.aspirate([res["diluent"]] * 1, vols=[180.0], use_channels=[6])
    # step 19: Aspirate 180 uL diluent with channel 7 (single channel, fits 9 mm container)
    await lh.aspirate([res["diluent"]] * 1, vols=[180.0], use_channels=[7])
    # step 20: Dispense 90 uL saline into column 3
    await lh.dispense([res["dilution_plate"].get_item("A3"), res["dilution_plate"].get_item("B3"), res["dilution_plate"].get_item("C3"), res["dilution_plate"].get_item("D3"), res["dilution_plate"].get_item("E3"), res["dilution_plate"].get_item("F3"), res["dilution_plate"].get_item("G3"), res["dilution_plate"].get_item("H3")], vols=[90.0, 90.0, 90.0, 90.0, 90.0, 90.0, 90.0, 90.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 21: Dispense 90 uL saline into column 4
    await lh.dispense([res["dilution_plate"].get_item("A4"), res["dilution_plate"].get_item("B4"), res["dilution_plate"].get_item("C4"), res["dilution_plate"].get_item("D4"), res["dilution_plate"].get_item("E4"), res["dilution_plate"].get_item("F4"), res["dilution_plate"].get_item("G4"), res["dilution_plate"].get_item("H4")], vols=[90.0, 90.0, 90.0, 90.0, 90.0, 90.0, 90.0, 90.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 22: Aspirate diluent with channel 0 only (reservoir too narrow for 8 channels)
    await lh.aspirate([res["diluent"]] * 1, vols=[180.0], use_channels=[0])
    # step 23: Aspirate diluent with channel 1 only (reservoir too narrow for 8 channels)
    await lh.aspirate([res["diluent"]] * 1, vols=[180.0], use_channels=[1])
    # step 24: Aspirate diluent with channel 2 only (reservoir too narrow for 8 channels)
    await lh.aspirate([res["diluent"]] * 1, vols=[180.0], use_channels=[2])
    # step 25: Aspirate diluent with channel 3 only (reservoir too narrow for 8 channels)
    await lh.aspirate([res["diluent"]] * 1, vols=[180.0], use_channels=[3])
    # step 26: Aspirate diluent with channel 4 only (reservoir too narrow for 8 channels)
    await lh.aspirate([res["diluent"]] * 1, vols=[180.0], use_channels=[4])
    # step 27: Aspirate diluent with channel 5 only (reservoir too narrow for 8 channels)
    await lh.aspirate([res["diluent"]] * 1, vols=[180.0], use_channels=[5])
    # step 28: Aspirate diluent with channel 6 only (reservoir too narrow for 8 channels)
    await lh.aspirate([res["diluent"]] * 1, vols=[180.0], use_channels=[6])
    # step 29: Aspirate diluent with channel 7 only (reservoir too narrow for 8 channels)
    await lh.aspirate([res["diluent"]] * 1, vols=[180.0], use_channels=[7])
    # step 30: Dispense 90 uL saline into column 5
    await lh.dispense([res["dilution_plate"].get_item("A5"), res["dilution_plate"].get_item("B5"), res["dilution_plate"].get_item("C5"), res["dilution_plate"].get_item("D5"), res["dilution_plate"].get_item("E5"), res["dilution_plate"].get_item("F5"), res["dilution_plate"].get_item("G5"), res["dilution_plate"].get_item("H5")], vols=[90.0, 90.0, 90.0, 90.0, 90.0, 90.0, 90.0, 90.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 31: Dispense 90 uL saline into column 6
    await lh.dispense([res["dilution_plate"].get_item("A6"), res["dilution_plate"].get_item("B6"), res["dilution_plate"].get_item("C6"), res["dilution_plate"].get_item("D6"), res["dilution_plate"].get_item("E6"), res["dilution_plate"].get_item("F6"), res["dilution_plate"].get_item("G6"), res["dilution_plate"].get_item("H6")], vols=[90.0, 90.0, 90.0, 90.0, 90.0, 90.0, 90.0, 90.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 32: Drop saline tips into waste
    await lh.discard_tips()
    # step 33: Pick up tip column 2 for the culture inoculum
    await lh.pick_up_tips([res["tips"].get_item("A2"), res["tips"].get_item("B2"), res["tips"].get_item("C2"), res["tips"].get_item("D2"), res["tips"].get_item("E2"), res["tips"].get_item("F2"), res["tips"].get_item("G2"), res["tips"].get_item("H2")], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 34: Aspirate 10 uL culture with channel 0 (single channel: culture container too narrow for 8 channels at once)
    await lh.aspirate([res["culture"]] * 1, vols=[10.0], use_channels=[0])
    # step 35: Aspirate 10 uL culture with channel 1 (single channel)
    await lh.aspirate([res["culture"]] * 1, vols=[10.0], use_channels=[1])
    # step 36: Aspirate 10 uL culture with channel 2 (single channel)
    await lh.aspirate([res["culture"]] * 1, vols=[10.0], use_channels=[2])
    # step 37: Aspirate 10 uL culture with channel 3 (single channel)
    await lh.aspirate([res["culture"]] * 1, vols=[10.0], use_channels=[3])
    # step 38: Aspirate 10 uL culture with channel 4 (single channel)
    await lh.aspirate([res["culture"]] * 1, vols=[10.0], use_channels=[4])
    # step 39: Aspirate 10 uL culture with channel 5 (single channel)
    await lh.aspirate([res["culture"]] * 1, vols=[10.0], use_channels=[5])
    # step 40: Aspirate 10 uL culture with channel 6 (single channel)
    await lh.aspirate([res["culture"]] * 1, vols=[10.0], use_channels=[6])
    # step 41: Aspirate 10 uL culture with channel 7 (single channel)
    await lh.aspirate([res["culture"]] * 1, vols=[10.0], use_channels=[7])
    # step 42: Add culture to column 1 (10^-1 well)
    await lh.dispense([res["dilution_plate"].get_item("A1"), res["dilution_plate"].get_item("B1"), res["dilution_plate"].get_item("C1"), res["dilution_plate"].get_item("D1"), res["dilution_plate"].get_item("E1"), res["dilution_plate"].get_item("F1"), res["dilution_plate"].get_item("G1"), res["dilution_plate"].get_item("H1")], vols=[10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 43: Mix column 1: aspirate 50 uL
    await lh.aspirate([res["dilution_plate"].get_item("A1"), res["dilution_plate"].get_item("B1"), res["dilution_plate"].get_item("C1"), res["dilution_plate"].get_item("D1"), res["dilution_plate"].get_item("E1"), res["dilution_plate"].get_item("F1"), res["dilution_plate"].get_item("G1"), res["dilution_plate"].get_item("H1")], vols=[50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 44: Mix column 1: dispense 50 uL back
    await lh.dispense([res["dilution_plate"].get_item("A1"), res["dilution_plate"].get_item("B1"), res["dilution_plate"].get_item("C1"), res["dilution_plate"].get_item("D1"), res["dilution_plate"].get_item("E1"), res["dilution_plate"].get_item("F1"), res["dilution_plate"].get_item("G1"), res["dilution_plate"].get_item("H1")], vols=[50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 45: Take 10 uL transfer from column 1
    await lh.aspirate([res["dilution_plate"].get_item("A1"), res["dilution_plate"].get_item("B1"), res["dilution_plate"].get_item("C1"), res["dilution_plate"].get_item("D1"), res["dilution_plate"].get_item("E1"), res["dilution_plate"].get_item("F1"), res["dilution_plate"].get_item("G1"), res["dilution_plate"].get_item("H1")], vols=[10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 46: Transfer 10 uL into column 2 (10^-2 well)
    await lh.dispense([res["dilution_plate"].get_item("A2"), res["dilution_plate"].get_item("B2"), res["dilution_plate"].get_item("C2"), res["dilution_plate"].get_item("D2"), res["dilution_plate"].get_item("E2"), res["dilution_plate"].get_item("F2"), res["dilution_plate"].get_item("G2"), res["dilution_plate"].get_item("H2")], vols=[10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 47: Drop tips into waste
    await lh.discard_tips()
    # step 48: Pick up tip column 3 for transfer 2 to 3
    await lh.pick_up_tips([res["tips"].get_item("A3"), res["tips"].get_item("B3"), res["tips"].get_item("C3"), res["tips"].get_item("D3"), res["tips"].get_item("E3"), res["tips"].get_item("F3"), res["tips"].get_item("G3"), res["tips"].get_item("H3")], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 49: Mix column 2: aspirate 50 uL
    await lh.aspirate([res["dilution_plate"].get_item("A2"), res["dilution_plate"].get_item("B2"), res["dilution_plate"].get_item("C2"), res["dilution_plate"].get_item("D2"), res["dilution_plate"].get_item("E2"), res["dilution_plate"].get_item("F2"), res["dilution_plate"].get_item("G2"), res["dilution_plate"].get_item("H2")], vols=[50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 50: Mix column 2: dispense 50 uL back
    await lh.dispense([res["dilution_plate"].get_item("A2"), res["dilution_plate"].get_item("B2"), res["dilution_plate"].get_item("C2"), res["dilution_plate"].get_item("D2"), res["dilution_plate"].get_item("E2"), res["dilution_plate"].get_item("F2"), res["dilution_plate"].get_item("G2"), res["dilution_plate"].get_item("H2")], vols=[50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 51: Take 10 uL transfer from column 2
    await lh.aspirate([res["dilution_plate"].get_item("A2"), res["dilution_plate"].get_item("B2"), res["dilution_plate"].get_item("C2"), res["dilution_plate"].get_item("D2"), res["dilution_plate"].get_item("E2"), res["dilution_plate"].get_item("F2"), res["dilution_plate"].get_item("G2"), res["dilution_plate"].get_item("H2")], vols=[10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 52: Transfer 10 uL into column 3 (10^-3 well)
    await lh.dispense([res["dilution_plate"].get_item("A3"), res["dilution_plate"].get_item("B3"), res["dilution_plate"].get_item("C3"), res["dilution_plate"].get_item("D3"), res["dilution_plate"].get_item("E3"), res["dilution_plate"].get_item("F3"), res["dilution_plate"].get_item("G3"), res["dilution_plate"].get_item("H3")], vols=[10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 53: Drop tips into waste
    await lh.discard_tips()
    # step 54: Pick up tip column 4 for transfer 3 to 4
    await lh.pick_up_tips([res["tips"].get_item("A4"), res["tips"].get_item("B4"), res["tips"].get_item("C4"), res["tips"].get_item("D4"), res["tips"].get_item("E4"), res["tips"].get_item("F4"), res["tips"].get_item("G4"), res["tips"].get_item("H4")], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 55: Mix column 3: aspirate 50 uL
    await lh.aspirate([res["dilution_plate"].get_item("A3"), res["dilution_plate"].get_item("B3"), res["dilution_plate"].get_item("C3"), res["dilution_plate"].get_item("D3"), res["dilution_plate"].get_item("E3"), res["dilution_plate"].get_item("F3"), res["dilution_plate"].get_item("G3"), res["dilution_plate"].get_item("H3")], vols=[50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 56: Mix column 3: dispense 50 uL back
    await lh.dispense([res["dilution_plate"].get_item("A3"), res["dilution_plate"].get_item("B3"), res["dilution_plate"].get_item("C3"), res["dilution_plate"].get_item("D3"), res["dilution_plate"].get_item("E3"), res["dilution_plate"].get_item("F3"), res["dilution_plate"].get_item("G3"), res["dilution_plate"].get_item("H3")], vols=[50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 57: Take 10 uL transfer from column 3
    await lh.aspirate([res["dilution_plate"].get_item("A3"), res["dilution_plate"].get_item("B3"), res["dilution_plate"].get_item("C3"), res["dilution_plate"].get_item("D3"), res["dilution_plate"].get_item("E3"), res["dilution_plate"].get_item("F3"), res["dilution_plate"].get_item("G3"), res["dilution_plate"].get_item("H3")], vols=[10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 58: Transfer 10 uL into column 4 (10^-4 well)
    await lh.dispense([res["dilution_plate"].get_item("A4"), res["dilution_plate"].get_item("B4"), res["dilution_plate"].get_item("C4"), res["dilution_plate"].get_item("D4"), res["dilution_plate"].get_item("E4"), res["dilution_plate"].get_item("F4"), res["dilution_plate"].get_item("G4"), res["dilution_plate"].get_item("H4")], vols=[10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 59: Drop tips into waste
    await lh.discard_tips()
    # step 60: Pick up tip column 5 for transfer 4 to 5
    await lh.pick_up_tips([res["tips"].get_item("A5"), res["tips"].get_item("B5"), res["tips"].get_item("C5"), res["tips"].get_item("D5"), res["tips"].get_item("E5"), res["tips"].get_item("F5"), res["tips"].get_item("G5"), res["tips"].get_item("H5")], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 61: Mix column 4: aspirate 50 uL
    await lh.aspirate([res["dilution_plate"].get_item("A4"), res["dilution_plate"].get_item("B4"), res["dilution_plate"].get_item("C4"), res["dilution_plate"].get_item("D4"), res["dilution_plate"].get_item("E4"), res["dilution_plate"].get_item("F4"), res["dilution_plate"].get_item("G4"), res["dilution_plate"].get_item("H4")], vols=[50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 62: Mix column 4: dispense 50 uL back
    await lh.dispense([res["dilution_plate"].get_item("A4"), res["dilution_plate"].get_item("B4"), res["dilution_plate"].get_item("C4"), res["dilution_plate"].get_item("D4"), res["dilution_plate"].get_item("E4"), res["dilution_plate"].get_item("F4"), res["dilution_plate"].get_item("G4"), res["dilution_plate"].get_item("H4")], vols=[50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 63: Take 10 uL transfer from column 4
    await lh.aspirate([res["dilution_plate"].get_item("A4"), res["dilution_plate"].get_item("B4"), res["dilution_plate"].get_item("C4"), res["dilution_plate"].get_item("D4"), res["dilution_plate"].get_item("E4"), res["dilution_plate"].get_item("F4"), res["dilution_plate"].get_item("G4"), res["dilution_plate"].get_item("H4")], vols=[10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 64: Transfer 10 uL into column 5 (10^-5 well)
    await lh.dispense([res["dilution_plate"].get_item("A5"), res["dilution_plate"].get_item("B5"), res["dilution_plate"].get_item("C5"), res["dilution_plate"].get_item("D5"), res["dilution_plate"].get_item("E5"), res["dilution_plate"].get_item("F5"), res["dilution_plate"].get_item("G5"), res["dilution_plate"].get_item("H5")], vols=[10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 65: Drop tips into waste
    await lh.discard_tips()
    # step 66: Pick up tip column 6 for transfer 5 to 6
    await lh.pick_up_tips([res["tips"].get_item("A6"), res["tips"].get_item("B6"), res["tips"].get_item("C6"), res["tips"].get_item("D6"), res["tips"].get_item("E6"), res["tips"].get_item("F6"), res["tips"].get_item("G6"), res["tips"].get_item("H6")], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 67: Mix column 5: aspirate 50 uL
    await lh.aspirate([res["dilution_plate"].get_item("A5"), res["dilution_plate"].get_item("B5"), res["dilution_plate"].get_item("C5"), res["dilution_plate"].get_item("D5"), res["dilution_plate"].get_item("E5"), res["dilution_plate"].get_item("F5"), res["dilution_plate"].get_item("G5"), res["dilution_plate"].get_item("H5")], vols=[50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 68: Mix column 5: dispense 50 uL back
    await lh.dispense([res["dilution_plate"].get_item("A5"), res["dilution_plate"].get_item("B5"), res["dilution_plate"].get_item("C5"), res["dilution_plate"].get_item("D5"), res["dilution_plate"].get_item("E5"), res["dilution_plate"].get_item("F5"), res["dilution_plate"].get_item("G5"), res["dilution_plate"].get_item("H5")], vols=[50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 69: Take 10 uL transfer from column 5
    await lh.aspirate([res["dilution_plate"].get_item("A5"), res["dilution_plate"].get_item("B5"), res["dilution_plate"].get_item("C5"), res["dilution_plate"].get_item("D5"), res["dilution_plate"].get_item("E5"), res["dilution_plate"].get_item("F5"), res["dilution_plate"].get_item("G5"), res["dilution_plate"].get_item("H5")], vols=[10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 70: Transfer 10 uL into column 6 (10^-6 well)
    await lh.dispense([res["dilution_plate"].get_item("A6"), res["dilution_plate"].get_item("B6"), res["dilution_plate"].get_item("C6"), res["dilution_plate"].get_item("D6"), res["dilution_plate"].get_item("E6"), res["dilution_plate"].get_item("F6"), res["dilution_plate"].get_item("G6"), res["dilution_plate"].get_item("H6")], vols=[10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 71: Drop tips into waste
    await lh.discard_tips()
    # step 72: Pick up fresh tip column 7 to mix the last well
    await lh.pick_up_tips([res["tips"].get_item("A7"), res["tips"].get_item("B7"), res["tips"].get_item("C7"), res["tips"].get_item("D7"), res["tips"].get_item("E7"), res["tips"].get_item("F7"), res["tips"].get_item("G7"), res["tips"].get_item("H7")], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 73: Mix column 6: aspirate 50 uL
    await lh.aspirate([res["dilution_plate"].get_item("A6"), res["dilution_plate"].get_item("B6"), res["dilution_plate"].get_item("C6"), res["dilution_plate"].get_item("D6"), res["dilution_plate"].get_item("E6"), res["dilution_plate"].get_item("F6"), res["dilution_plate"].get_item("G6"), res["dilution_plate"].get_item("H6")], vols=[50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 74: Mix column 6: dispense 50 uL back
    await lh.dispense([res["dilution_plate"].get_item("A6"), res["dilution_plate"].get_item("B6"), res["dilution_plate"].get_item("C6"), res["dilution_plate"].get_item("D6"), res["dilution_plate"].get_item("E6"), res["dilution_plate"].get_item("F6"), res["dilution_plate"].get_item("G6"), res["dilution_plate"].get_item("H6")], vols=[50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 75: Drop tips into waste
    await lh.discard_tips()


# --- Standalone runner: python healed/serial_1_10_dilution_of_culture_in_0_9_saline_20261112-172546_plr.py --backend chatterbox|star ---
DECK_CONFIG = 'decks/serial_1_10_dilution_of_culture_in_0_9_saline_20261112-172546.json'
INITIAL_VOLUMES_UL = {'diluent': 5000, 'culture': 1000}


async def _main(backend_name):
    from pylabrobot.legacy.liquid_handling import LiquidHandler
    from pylabrobot.legacy.liquid_handling.backends import LiquidHandlerChatterboxBackend, STARBackend
    from pylabrobot.resources import set_tip_tracking, set_volume_tracking
    from pipeline.deck import build_deck, load_deck_config, machines
    from pipeline.instrument import simulation_backend

    set_tip_tracking(True)
    set_volume_tracking(True)
    deck_config = load_deck_config(str(Path(__file__).resolve().parents[1] / DECK_CONFIG))
    deck, res = build_deck(deck_config, INITIAL_VOLUMES_UL)
    backend = STARBackend() if backend_name == "star" else simulation_backend(deck_config)
    lh = LiquidHandler(backend=backend, deck=deck)
    await lh.setup()
    for machine in machines(res):
        await machine.setup()
    try:
        await run_protocol(lh, res)
    finally:
        for machine in machines(res):
            await machine.stop()
        await lh.stop()


if __name__ == "__main__":
    import argparse
    import asyncio

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=["chatterbox", "star"], default="chatterbox")
    args = parser.parse_args()
    if args.backend == "star":
        from pipeline.deck import is_reference, load_deck_config
        if is_reference(load_deck_config(str(Path(__file__).resolve().parents[1] / DECK_CONFIG))):
            sys.exit("Not run: this protocol is on " + DECK_CONFIG + ", a reference simulation deck, not the deck "
                     "on the STARlet. Re-draft it on the instrument's deck (python pipeline.py ...) first.")
        answer = input("Run on the real STARlet? The deck must match the setup checklist "
                       "(demo/server.py -> Execute). Type 'run' to continue: ")
        if answer.strip().lower() != "run":
            sys.exit("Not run.")
    asyncio.run(_main(args.backend))
