"""Compiled from protocol: Serial 1:10 dilution of culture in 0.9% saline. Do not edit; recompile from the IR."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # repo root, for pipeline.deck


async def run_protocol(lh, res):
    # step 1: Pick up tip column 1 for saline fill
    await lh.pick_up_tips([res["hamilton_tiprack_96"].get_item("A1"), res["hamilton_tiprack_96"].get_item("B1"), res["hamilton_tiprack_96"].get_item("C1"), res["hamilton_tiprack_96"].get_item("D1"), res["hamilton_tiprack_96"].get_item("E1"), res["hamilton_tiprack_96"].get_item("F1"), res["hamilton_tiprack_96"].get_item("G1"), res["hamilton_tiprack_96"].get_item("H1")], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 2: Aspirate 90 uL saline
    await lh.aspirate([res["reservoir_50ml"]] * 8, vols=[90.0, 90.0, 90.0, 90.0, 90.0, 90.0, 90.0, 90.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 3: Dispense saline into column 1
    await lh.dispense([res["corning_3595"].get_item("A1"), res["corning_3595"].get_item("B1"), res["corning_3595"].get_item("C1"), res["corning_3595"].get_item("D1"), res["corning_3595"].get_item("E1"), res["corning_3595"].get_item("F1"), res["corning_3595"].get_item("G1"), res["corning_3595"].get_item("H1")], vols=[90.0, 90.0, 90.0, 90.0, 90.0, 90.0, 90.0, 90.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 4: Aspirate 90 uL saline
    await lh.aspirate([res["reservoir_50ml"]] * 8, vols=[90.0, 90.0, 90.0, 90.0, 90.0, 90.0, 90.0, 90.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 5: Dispense saline into column 2
    await lh.dispense([res["corning_3595"].get_item("A2"), res["corning_3595"].get_item("B2"), res["corning_3595"].get_item("C2"), res["corning_3595"].get_item("D2"), res["corning_3595"].get_item("E2"), res["corning_3595"].get_item("F2"), res["corning_3595"].get_item("G2"), res["corning_3595"].get_item("H2")], vols=[90.0, 90.0, 90.0, 90.0, 90.0, 90.0, 90.0, 90.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 6: Aspirate 90 uL saline
    await lh.aspirate([res["reservoir_50ml"]] * 8, vols=[90.0, 90.0, 90.0, 90.0, 90.0, 90.0, 90.0, 90.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 7: Dispense saline into column 3
    await lh.dispense([res["corning_3595"].get_item("A3"), res["corning_3595"].get_item("B3"), res["corning_3595"].get_item("C3"), res["corning_3595"].get_item("D3"), res["corning_3595"].get_item("E3"), res["corning_3595"].get_item("F3"), res["corning_3595"].get_item("G3"), res["corning_3595"].get_item("H3")], vols=[90.0, 90.0, 90.0, 90.0, 90.0, 90.0, 90.0, 90.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 8: Aspirate 90 uL saline
    await lh.aspirate([res["reservoir_50ml"]] * 8, vols=[90.0, 90.0, 90.0, 90.0, 90.0, 90.0, 90.0, 90.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 9: Dispense saline into column 4
    await lh.dispense([res["corning_3595"].get_item("A4"), res["corning_3595"].get_item("B4"), res["corning_3595"].get_item("C4"), res["corning_3595"].get_item("D4"), res["corning_3595"].get_item("E4"), res["corning_3595"].get_item("F4"), res["corning_3595"].get_item("G4"), res["corning_3595"].get_item("H4")], vols=[90.0, 90.0, 90.0, 90.0, 90.0, 90.0, 90.0, 90.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 10: Aspirate 90 uL saline
    await lh.aspirate([res["reservoir_50ml"]] * 8, vols=[90.0, 90.0, 90.0, 90.0, 90.0, 90.0, 90.0, 90.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 11: Dispense saline into column 5
    await lh.dispense([res["corning_3595"].get_item("A5"), res["corning_3595"].get_item("B5"), res["corning_3595"].get_item("C5"), res["corning_3595"].get_item("D5"), res["corning_3595"].get_item("E5"), res["corning_3595"].get_item("F5"), res["corning_3595"].get_item("G5"), res["corning_3595"].get_item("H5")], vols=[90.0, 90.0, 90.0, 90.0, 90.0, 90.0, 90.0, 90.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 12: Aspirate 90 uL saline
    await lh.aspirate([res["reservoir_50ml"]] * 8, vols=[90.0, 90.0, 90.0, 90.0, 90.0, 90.0, 90.0, 90.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 13: Dispense saline into column 6
    await lh.dispense([res["corning_3595"].get_item("A6"), res["corning_3595"].get_item("B6"), res["corning_3595"].get_item("C6"), res["corning_3595"].get_item("D6"), res["corning_3595"].get_item("E6"), res["corning_3595"].get_item("F6"), res["corning_3595"].get_item("G6"), res["corning_3595"].get_item("H6")], vols=[90.0, 90.0, 90.0, 90.0, 90.0, 90.0, 90.0, 90.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 14: Aspirate 90 uL saline
    await lh.aspirate([res["reservoir_50ml"]] * 8, vols=[90.0, 90.0, 90.0, 90.0, 90.0, 90.0, 90.0, 90.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 15: Dispense saline into column 7
    await lh.dispense([res["corning_3595"].get_item("A7"), res["corning_3595"].get_item("B7"), res["corning_3595"].get_item("C7"), res["corning_3595"].get_item("D7"), res["corning_3595"].get_item("E7"), res["corning_3595"].get_item("F7"), res["corning_3595"].get_item("G7"), res["corning_3595"].get_item("H7")], vols=[90.0, 90.0, 90.0, 90.0, 90.0, 90.0, 90.0, 90.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 16: Aspirate 90 uL saline
    await lh.aspirate([res["reservoir_50ml"]] * 8, vols=[90.0, 90.0, 90.0, 90.0, 90.0, 90.0, 90.0, 90.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 17: Dispense saline into column 8
    await lh.dispense([res["corning_3595"].get_item("A8"), res["corning_3595"].get_item("B8"), res["corning_3595"].get_item("C8"), res["corning_3595"].get_item("D8"), res["corning_3595"].get_item("E8"), res["corning_3595"].get_item("F8"), res["corning_3595"].get_item("G8"), res["corning_3595"].get_item("H8")], vols=[90.0, 90.0, 90.0, 90.0, 90.0, 90.0, 90.0, 90.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 18: Discard saline-fill tips
    await lh.discard_tips()
    # step 19: Pick up tip column 2 for culture addition
    await lh.pick_up_tips([res["hamilton_tiprack_96"].get_item("A2"), res["hamilton_tiprack_96"].get_item("B2"), res["hamilton_tiprack_96"].get_item("C2"), res["hamilton_tiprack_96"].get_item("D2"), res["hamilton_tiprack_96"].get_item("E2"), res["hamilton_tiprack_96"].get_item("F2"), res["hamilton_tiprack_96"].get_item("G2"), res["hamilton_tiprack_96"].get_item("H2")], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 20: Aspirate 10 uL from tube_15ml using channel 0
    await lh.aspirate([res["tube_15ml"]] * 1, vols=[10.0], use_channels=[0])
    # step 21: Aspirate 10 uL from tube_15ml using channel 1
    await lh.aspirate([res["tube_15ml"]] * 1, vols=[10.0], use_channels=[1])
    # step 22: Aspirate 10 uL from tube_15ml using channel 2
    await lh.aspirate([res["tube_15ml"]] * 1, vols=[10.0], use_channels=[2])
    # step 23: Aspirate 10 uL from tube_15ml using channel 3
    await lh.aspirate([res["tube_15ml"]] * 1, vols=[10.0], use_channels=[3])
    # step 24: Aspirate 10 uL from tube_15ml using channel 4
    await lh.aspirate([res["tube_15ml"]] * 1, vols=[10.0], use_channels=[4])
    # step 25: Aspirate 10 uL from tube_15ml using channel 5
    await lh.aspirate([res["tube_15ml"]] * 1, vols=[10.0], use_channels=[5])
    # step 26: Aspirate 10 uL from tube_15ml using channel 6
    await lh.aspirate([res["tube_15ml"]] * 1, vols=[10.0], use_channels=[6])
    # step 27: Aspirate 10 uL from tube_15ml using channel 7
    await lh.aspirate([res["tube_15ml"]] * 1, vols=[10.0], use_channels=[7])
    # step 28: Dispense culture into column 1 (10^-1)
    await lh.dispense([res["corning_3595"].get_item("A1"), res["corning_3595"].get_item("B1"), res["corning_3595"].get_item("C1"), res["corning_3595"].get_item("D1"), res["corning_3595"].get_item("E1"), res["corning_3595"].get_item("F1"), res["corning_3595"].get_item("G1"), res["corning_3595"].get_item("H1")], vols=[10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 29: Discard culture tips
    await lh.discard_tips()
    # step 30: Tip column 3 for mixing column 1
    await lh.pick_up_tips([res["hamilton_tiprack_96"].get_item("A3"), res["hamilton_tiprack_96"].get_item("B3"), res["hamilton_tiprack_96"].get_item("C3"), res["hamilton_tiprack_96"].get_item("D3"), res["hamilton_tiprack_96"].get_item("E3"), res["hamilton_tiprack_96"].get_item("F3"), res["hamilton_tiprack_96"].get_item("G3"), res["hamilton_tiprack_96"].get_item("H3")], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 31: Mix column 1: aspirate 50 uL
    await lh.aspirate([res["corning_3595"].get_item("A1"), res["corning_3595"].get_item("B1"), res["corning_3595"].get_item("C1"), res["corning_3595"].get_item("D1"), res["corning_3595"].get_item("E1"), res["corning_3595"].get_item("F1"), res["corning_3595"].get_item("G1"), res["corning_3595"].get_item("H1")], vols=[50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 32: Mix column 1: dispense 50 uL back
    await lh.dispense([res["corning_3595"].get_item("A1"), res["corning_3595"].get_item("B1"), res["corning_3595"].get_item("C1"), res["corning_3595"].get_item("D1"), res["corning_3595"].get_item("E1"), res["corning_3595"].get_item("F1"), res["corning_3595"].get_item("G1"), res["corning_3595"].get_item("H1")], vols=[50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 33: Aspirate 10 uL from column 1 for transfer
    await lh.aspirate([res["corning_3595"].get_item("A1"), res["corning_3595"].get_item("B1"), res["corning_3595"].get_item("C1"), res["corning_3595"].get_item("D1"), res["corning_3595"].get_item("E1"), res["corning_3595"].get_item("F1"), res["corning_3595"].get_item("G1"), res["corning_3595"].get_item("H1")], vols=[10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 34: Transfer to column 2 (10^-2)
    await lh.dispense([res["corning_3595"].get_item("A2"), res["corning_3595"].get_item("B2"), res["corning_3595"].get_item("C2"), res["corning_3595"].get_item("D2"), res["corning_3595"].get_item("E2"), res["corning_3595"].get_item("F2"), res["corning_3595"].get_item("G2"), res["corning_3595"].get_item("H2")], vols=[10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 35: Discard tips
    await lh.discard_tips()
    # step 36: Tip column 4 for mixing column 2
    await lh.pick_up_tips([res["hamilton_tiprack_96"].get_item("A4"), res["hamilton_tiprack_96"].get_item("B4"), res["hamilton_tiprack_96"].get_item("C4"), res["hamilton_tiprack_96"].get_item("D4"), res["hamilton_tiprack_96"].get_item("E4"), res["hamilton_tiprack_96"].get_item("F4"), res["hamilton_tiprack_96"].get_item("G4"), res["hamilton_tiprack_96"].get_item("H4")], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 37: Mix column 2: aspirate 50 uL
    await lh.aspirate([res["corning_3595"].get_item("A2"), res["corning_3595"].get_item("B2"), res["corning_3595"].get_item("C2"), res["corning_3595"].get_item("D2"), res["corning_3595"].get_item("E2"), res["corning_3595"].get_item("F2"), res["corning_3595"].get_item("G2"), res["corning_3595"].get_item("H2")], vols=[50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 38: Mix column 2: dispense 50 uL back
    await lh.dispense([res["corning_3595"].get_item("A2"), res["corning_3595"].get_item("B2"), res["corning_3595"].get_item("C2"), res["corning_3595"].get_item("D2"), res["corning_3595"].get_item("E2"), res["corning_3595"].get_item("F2"), res["corning_3595"].get_item("G2"), res["corning_3595"].get_item("H2")], vols=[50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 39: Aspirate 10 uL from column 2
    await lh.aspirate([res["corning_3595"].get_item("A2"), res["corning_3595"].get_item("B2"), res["corning_3595"].get_item("C2"), res["corning_3595"].get_item("D2"), res["corning_3595"].get_item("E2"), res["corning_3595"].get_item("F2"), res["corning_3595"].get_item("G2"), res["corning_3595"].get_item("H2")], vols=[10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 40: Transfer to column 3 (10^-3)
    await lh.dispense([res["corning_3595"].get_item("A3"), res["corning_3595"].get_item("B3"), res["corning_3595"].get_item("C3"), res["corning_3595"].get_item("D3"), res["corning_3595"].get_item("E3"), res["corning_3595"].get_item("F3"), res["corning_3595"].get_item("G3"), res["corning_3595"].get_item("H3")], vols=[10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 41: Discard tips
    await lh.discard_tips()
    # step 42: Tip column 5 for mixing column 3
    await lh.pick_up_tips([res["hamilton_tiprack_96"].get_item("A5"), res["hamilton_tiprack_96"].get_item("B5"), res["hamilton_tiprack_96"].get_item("C5"), res["hamilton_tiprack_96"].get_item("D5"), res["hamilton_tiprack_96"].get_item("E5"), res["hamilton_tiprack_96"].get_item("F5"), res["hamilton_tiprack_96"].get_item("G5"), res["hamilton_tiprack_96"].get_item("H5")], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 43: Mix column 3: aspirate 50 uL
    await lh.aspirate([res["corning_3595"].get_item("A3"), res["corning_3595"].get_item("B3"), res["corning_3595"].get_item("C3"), res["corning_3595"].get_item("D3"), res["corning_3595"].get_item("E3"), res["corning_3595"].get_item("F3"), res["corning_3595"].get_item("G3"), res["corning_3595"].get_item("H3")], vols=[50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 44: Mix column 3: dispense 50 uL back
    await lh.dispense([res["corning_3595"].get_item("A3"), res["corning_3595"].get_item("B3"), res["corning_3595"].get_item("C3"), res["corning_3595"].get_item("D3"), res["corning_3595"].get_item("E3"), res["corning_3595"].get_item("F3"), res["corning_3595"].get_item("G3"), res["corning_3595"].get_item("H3")], vols=[50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 45: Aspirate 10 uL from column 3
    await lh.aspirate([res["corning_3595"].get_item("A3"), res["corning_3595"].get_item("B3"), res["corning_3595"].get_item("C3"), res["corning_3595"].get_item("D3"), res["corning_3595"].get_item("E3"), res["corning_3595"].get_item("F3"), res["corning_3595"].get_item("G3"), res["corning_3595"].get_item("H3")], vols=[10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 46: Transfer to column 4 (10^-4)
    await lh.dispense([res["corning_3595"].get_item("A4"), res["corning_3595"].get_item("B4"), res["corning_3595"].get_item("C4"), res["corning_3595"].get_item("D4"), res["corning_3595"].get_item("E4"), res["corning_3595"].get_item("F4"), res["corning_3595"].get_item("G4"), res["corning_3595"].get_item("H4")], vols=[10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 47: Discard tips
    await lh.discard_tips()
    # step 48: Tip column 6 for mixing column 4
    await lh.pick_up_tips([res["hamilton_tiprack_96"].get_item("A6"), res["hamilton_tiprack_96"].get_item("B6"), res["hamilton_tiprack_96"].get_item("C6"), res["hamilton_tiprack_96"].get_item("D6"), res["hamilton_tiprack_96"].get_item("E6"), res["hamilton_tiprack_96"].get_item("F6"), res["hamilton_tiprack_96"].get_item("G6"), res["hamilton_tiprack_96"].get_item("H6")], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 49: Mix column 4: aspirate 50 uL
    await lh.aspirate([res["corning_3595"].get_item("A4"), res["corning_3595"].get_item("B4"), res["corning_3595"].get_item("C4"), res["corning_3595"].get_item("D4"), res["corning_3595"].get_item("E4"), res["corning_3595"].get_item("F4"), res["corning_3595"].get_item("G4"), res["corning_3595"].get_item("H4")], vols=[50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 50: Mix column 4: dispense 50 uL back
    await lh.dispense([res["corning_3595"].get_item("A4"), res["corning_3595"].get_item("B4"), res["corning_3595"].get_item("C4"), res["corning_3595"].get_item("D4"), res["corning_3595"].get_item("E4"), res["corning_3595"].get_item("F4"), res["corning_3595"].get_item("G4"), res["corning_3595"].get_item("H4")], vols=[50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 51: Aspirate 10 uL from column 4
    await lh.aspirate([res["corning_3595"].get_item("A4"), res["corning_3595"].get_item("B4"), res["corning_3595"].get_item("C4"), res["corning_3595"].get_item("D4"), res["corning_3595"].get_item("E4"), res["corning_3595"].get_item("F4"), res["corning_3595"].get_item("G4"), res["corning_3595"].get_item("H4")], vols=[10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 52: Transfer to column 5 (10^-5)
    await lh.dispense([res["corning_3595"].get_item("A5"), res["corning_3595"].get_item("B5"), res["corning_3595"].get_item("C5"), res["corning_3595"].get_item("D5"), res["corning_3595"].get_item("E5"), res["corning_3595"].get_item("F5"), res["corning_3595"].get_item("G5"), res["corning_3595"].get_item("H5")], vols=[10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 53: Discard tips
    await lh.discard_tips()
    # step 54: Tip column 7 for mixing column 5
    await lh.pick_up_tips([res["hamilton_tiprack_96"].get_item("A7"), res["hamilton_tiprack_96"].get_item("B7"), res["hamilton_tiprack_96"].get_item("C7"), res["hamilton_tiprack_96"].get_item("D7"), res["hamilton_tiprack_96"].get_item("E7"), res["hamilton_tiprack_96"].get_item("F7"), res["hamilton_tiprack_96"].get_item("G7"), res["hamilton_tiprack_96"].get_item("H7")], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 55: Mix column 5: aspirate 50 uL
    await lh.aspirate([res["corning_3595"].get_item("A5"), res["corning_3595"].get_item("B5"), res["corning_3595"].get_item("C5"), res["corning_3595"].get_item("D5"), res["corning_3595"].get_item("E5"), res["corning_3595"].get_item("F5"), res["corning_3595"].get_item("G5"), res["corning_3595"].get_item("H5")], vols=[50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 56: Mix column 5: dispense 50 uL back
    await lh.dispense([res["corning_3595"].get_item("A5"), res["corning_3595"].get_item("B5"), res["corning_3595"].get_item("C5"), res["corning_3595"].get_item("D5"), res["corning_3595"].get_item("E5"), res["corning_3595"].get_item("F5"), res["corning_3595"].get_item("G5"), res["corning_3595"].get_item("H5")], vols=[50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 57: Aspirate 10 uL from column 5
    await lh.aspirate([res["corning_3595"].get_item("A5"), res["corning_3595"].get_item("B5"), res["corning_3595"].get_item("C5"), res["corning_3595"].get_item("D5"), res["corning_3595"].get_item("E5"), res["corning_3595"].get_item("F5"), res["corning_3595"].get_item("G5"), res["corning_3595"].get_item("H5")], vols=[10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 58: Transfer to column 6 (10^-6)
    await lh.dispense([res["corning_3595"].get_item("A6"), res["corning_3595"].get_item("B6"), res["corning_3595"].get_item("C6"), res["corning_3595"].get_item("D6"), res["corning_3595"].get_item("E6"), res["corning_3595"].get_item("F6"), res["corning_3595"].get_item("G6"), res["corning_3595"].get_item("H6")], vols=[10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 59: Discard tips
    await lh.discard_tips()
    # step 60: Tip column 8 for mixing column 6
    await lh.pick_up_tips([res["hamilton_tiprack_96"].get_item("A8"), res["hamilton_tiprack_96"].get_item("B8"), res["hamilton_tiprack_96"].get_item("C8"), res["hamilton_tiprack_96"].get_item("D8"), res["hamilton_tiprack_96"].get_item("E8"), res["hamilton_tiprack_96"].get_item("F8"), res["hamilton_tiprack_96"].get_item("G8"), res["hamilton_tiprack_96"].get_item("H8")], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 61: Mix column 6: aspirate 50 uL
    await lh.aspirate([res["corning_3595"].get_item("A6"), res["corning_3595"].get_item("B6"), res["corning_3595"].get_item("C6"), res["corning_3595"].get_item("D6"), res["corning_3595"].get_item("E6"), res["corning_3595"].get_item("F6"), res["corning_3595"].get_item("G6"), res["corning_3595"].get_item("H6")], vols=[50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 62: Mix column 6: dispense 50 uL back
    await lh.dispense([res["corning_3595"].get_item("A6"), res["corning_3595"].get_item("B6"), res["corning_3595"].get_item("C6"), res["corning_3595"].get_item("D6"), res["corning_3595"].get_item("E6"), res["corning_3595"].get_item("F6"), res["corning_3595"].get_item("G6"), res["corning_3595"].get_item("H6")], vols=[50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 63: Aspirate 10 uL from column 6
    await lh.aspirate([res["corning_3595"].get_item("A6"), res["corning_3595"].get_item("B6"), res["corning_3595"].get_item("C6"), res["corning_3595"].get_item("D6"), res["corning_3595"].get_item("E6"), res["corning_3595"].get_item("F6"), res["corning_3595"].get_item("G6"), res["corning_3595"].get_item("H6")], vols=[10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 64: Transfer to column 7 (10^-7)
    await lh.dispense([res["corning_3595"].get_item("A7"), res["corning_3595"].get_item("B7"), res["corning_3595"].get_item("C7"), res["corning_3595"].get_item("D7"), res["corning_3595"].get_item("E7"), res["corning_3595"].get_item("F7"), res["corning_3595"].get_item("G7"), res["corning_3595"].get_item("H7")], vols=[10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 65: Discard tips
    await lh.discard_tips()
    # step 66: Tip column 9 for mixing column 7
    await lh.pick_up_tips([res["hamilton_tiprack_96"].get_item("A9"), res["hamilton_tiprack_96"].get_item("B9"), res["hamilton_tiprack_96"].get_item("C9"), res["hamilton_tiprack_96"].get_item("D9"), res["hamilton_tiprack_96"].get_item("E9"), res["hamilton_tiprack_96"].get_item("F9"), res["hamilton_tiprack_96"].get_item("G9"), res["hamilton_tiprack_96"].get_item("H9")], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 67: Mix column 7: aspirate 50 uL
    await lh.aspirate([res["corning_3595"].get_item("A7"), res["corning_3595"].get_item("B7"), res["corning_3595"].get_item("C7"), res["corning_3595"].get_item("D7"), res["corning_3595"].get_item("E7"), res["corning_3595"].get_item("F7"), res["corning_3595"].get_item("G7"), res["corning_3595"].get_item("H7")], vols=[50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 68: Mix column 7: dispense 50 uL back
    await lh.dispense([res["corning_3595"].get_item("A7"), res["corning_3595"].get_item("B7"), res["corning_3595"].get_item("C7"), res["corning_3595"].get_item("D7"), res["corning_3595"].get_item("E7"), res["corning_3595"].get_item("F7"), res["corning_3595"].get_item("G7"), res["corning_3595"].get_item("H7")], vols=[50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 69: Aspirate 10 uL from column 7
    await lh.aspirate([res["corning_3595"].get_item("A7"), res["corning_3595"].get_item("B7"), res["corning_3595"].get_item("C7"), res["corning_3595"].get_item("D7"), res["corning_3595"].get_item("E7"), res["corning_3595"].get_item("F7"), res["corning_3595"].get_item("G7"), res["corning_3595"].get_item("H7")], vols=[10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 70: Transfer to column 8 (10^-8)
    await lh.dispense([res["corning_3595"].get_item("A8"), res["corning_3595"].get_item("B8"), res["corning_3595"].get_item("C8"), res["corning_3595"].get_item("D8"), res["corning_3595"].get_item("E8"), res["corning_3595"].get_item("F8"), res["corning_3595"].get_item("G8"), res["corning_3595"].get_item("H8")], vols=[10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 71: Discard tips
    await lh.discard_tips()
    # step 72: Tip column 10 for mixing final column 8
    await lh.pick_up_tips([res["hamilton_tiprack_96"].get_item("A10"), res["hamilton_tiprack_96"].get_item("B10"), res["hamilton_tiprack_96"].get_item("C10"), res["hamilton_tiprack_96"].get_item("D10"), res["hamilton_tiprack_96"].get_item("E10"), res["hamilton_tiprack_96"].get_item("F10"), res["hamilton_tiprack_96"].get_item("G10"), res["hamilton_tiprack_96"].get_item("H10")], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 73: Mix column 8: aspirate 50 uL
    await lh.aspirate([res["corning_3595"].get_item("A8"), res["corning_3595"].get_item("B8"), res["corning_3595"].get_item("C8"), res["corning_3595"].get_item("D8"), res["corning_3595"].get_item("E8"), res["corning_3595"].get_item("F8"), res["corning_3595"].get_item("G8"), res["corning_3595"].get_item("H8")], vols=[50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 74: Mix column 8: dispense 50 uL back
    await lh.dispense([res["corning_3595"].get_item("A8"), res["corning_3595"].get_item("B8"), res["corning_3595"].get_item("C8"), res["corning_3595"].get_item("D8"), res["corning_3595"].get_item("E8"), res["corning_3595"].get_item("F8"), res["corning_3595"].get_item("G8"), res["corning_3595"].get_item("H8")], vols=[50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 75: Discard tips; dilution series complete
    await lh.discard_tips()


# --- Standalone runner: python healed/serial_1_10_dilution_of_culture_in_0_9_saline_20261106-132529_plr.py --backend chatterbox|star ---
DECK_CONFIG = 'config/reference/plr_deck.json'
INITIAL_VOLUMES_UL = {'reservoir_50ml': 8000, 'tube_15ml': 5000}


async def _main(backend_name):
    from pylabrobot.legacy.liquid_handling import LiquidHandler
    from pylabrobot.legacy.liquid_handling.backends import LiquidHandlerChatterboxBackend, STARBackend
    from pylabrobot.resources import set_tip_tracking, set_volume_tracking
    from pipeline.deck import build_deck, load_deck_config, machines

    set_tip_tracking(True)
    set_volume_tracking(True)
    deck, res = build_deck(load_deck_config(str(Path(__file__).resolve().parents[1] / DECK_CONFIG)), INITIAL_VOLUMES_UL)
    backend = STARBackend() if backend_name == "star" else LiquidHandlerChatterboxBackend(num_channels=8)
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
        answer = input("Run on the real STARlet? The deck must match the setup checklist "
                       "(demo/server.py -> Execute). Type 'run' to continue: ")
        if answer.strip().lower() != "run":
            sys.exit("Not run.")
    asyncio.run(_main(args.backend))
