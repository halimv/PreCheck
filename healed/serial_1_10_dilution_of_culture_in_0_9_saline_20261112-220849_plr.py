"""Compiled from protocol: Serial 1:10 dilution of culture in 0.9% saline. Do not edit; recompile from the IR."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # repo root, for pipeline.deck

from pipeline.deck import reach
from pipeline.pipetting import aspirate, dispense, tips_off, tips_on

async def run_protocol(lh, res):
    # step 1: Pick up saline tips (column 1)
    await tips_on(lh, [res["tips"].get_item("A1"), res["tips"].get_item("B1"), res["tips"].get_item("C1"), res["tips"].get_item("D1"), res["tips"].get_item("E1"), res["tips"].get_item("F1"), res["tips"].get_item("G1"), res["tips"].get_item("H1")], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 2: Aspirate 90 uL saline
    await aspirate(lh, [res["diluent"]] * 8, vols=[90.0, 90.0, 90.0, 90.0, 90.0, 90.0, 90.0, 90.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7], **reach(res["diluent"], [0, 1, 2, 3, 4, 5, 6, 7]))
    # step 3: Dispense saline into column 1
    await dispense(lh, [res["dilution_plate"].get_item("A1"), res["dilution_plate"].get_item("B1"), res["dilution_plate"].get_item("C1"), res["dilution_plate"].get_item("D1"), res["dilution_plate"].get_item("E1"), res["dilution_plate"].get_item("F1"), res["dilution_plate"].get_item("G1"), res["dilution_plate"].get_item("H1")], vols=[90.0, 90.0, 90.0, 90.0, 90.0, 90.0, 90.0, 90.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 4: Aspirate 90 uL saline
    await aspirate(lh, [res["diluent"]] * 8, vols=[90.0, 90.0, 90.0, 90.0, 90.0, 90.0, 90.0, 90.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7], **reach(res["diluent"], [0, 1, 2, 3, 4, 5, 6, 7]))
    # step 5: Dispense saline into column 2
    await dispense(lh, [res["dilution_plate"].get_item("A2"), res["dilution_plate"].get_item("B2"), res["dilution_plate"].get_item("C2"), res["dilution_plate"].get_item("D2"), res["dilution_plate"].get_item("E2"), res["dilution_plate"].get_item("F2"), res["dilution_plate"].get_item("G2"), res["dilution_plate"].get_item("H2")], vols=[90.0, 90.0, 90.0, 90.0, 90.0, 90.0, 90.0, 90.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 6: Aspirate 90 uL saline
    await aspirate(lh, [res["diluent"]] * 8, vols=[90.0, 90.0, 90.0, 90.0, 90.0, 90.0, 90.0, 90.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7], **reach(res["diluent"], [0, 1, 2, 3, 4, 5, 6, 7]))
    # step 7: Dispense saline into column 3
    await dispense(lh, [res["dilution_plate"].get_item("A3"), res["dilution_plate"].get_item("B3"), res["dilution_plate"].get_item("C3"), res["dilution_plate"].get_item("D3"), res["dilution_plate"].get_item("E3"), res["dilution_plate"].get_item("F3"), res["dilution_plate"].get_item("G3"), res["dilution_plate"].get_item("H3")], vols=[90.0, 90.0, 90.0, 90.0, 90.0, 90.0, 90.0, 90.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 8: Aspirate 90 uL saline
    await aspirate(lh, [res["diluent"]] * 8, vols=[90.0, 90.0, 90.0, 90.0, 90.0, 90.0, 90.0, 90.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7], **reach(res["diluent"], [0, 1, 2, 3, 4, 5, 6, 7]))
    # step 9: Dispense saline into column 4
    await dispense(lh, [res["dilution_plate"].get_item("A4"), res["dilution_plate"].get_item("B4"), res["dilution_plate"].get_item("C4"), res["dilution_plate"].get_item("D4"), res["dilution_plate"].get_item("E4"), res["dilution_plate"].get_item("F4"), res["dilution_plate"].get_item("G4"), res["dilution_plate"].get_item("H4")], vols=[90.0, 90.0, 90.0, 90.0, 90.0, 90.0, 90.0, 90.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 10: Aspirate 90 uL saline
    await aspirate(lh, [res["diluent"]] * 8, vols=[90.0, 90.0, 90.0, 90.0, 90.0, 90.0, 90.0, 90.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7], **reach(res["diluent"], [0, 1, 2, 3, 4, 5, 6, 7]))
    # step 11: Dispense saline into column 5
    await dispense(lh, [res["dilution_plate"].get_item("A5"), res["dilution_plate"].get_item("B5"), res["dilution_plate"].get_item("C5"), res["dilution_plate"].get_item("D5"), res["dilution_plate"].get_item("E5"), res["dilution_plate"].get_item("F5"), res["dilution_plate"].get_item("G5"), res["dilution_plate"].get_item("H5")], vols=[90.0, 90.0, 90.0, 90.0, 90.0, 90.0, 90.0, 90.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 12: Aspirate 90 uL saline
    await aspirate(lh, [res["diluent"]] * 8, vols=[90.0, 90.0, 90.0, 90.0, 90.0, 90.0, 90.0, 90.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7], **reach(res["diluent"], [0, 1, 2, 3, 4, 5, 6, 7]))
    # step 13: Dispense saline into column 6
    await dispense(lh, [res["dilution_plate"].get_item("A6"), res["dilution_plate"].get_item("B6"), res["dilution_plate"].get_item("C6"), res["dilution_plate"].get_item("D6"), res["dilution_plate"].get_item("E6"), res["dilution_plate"].get_item("F6"), res["dilution_plate"].get_item("G6"), res["dilution_plate"].get_item("H6")], vols=[90.0, 90.0, 90.0, 90.0, 90.0, 90.0, 90.0, 90.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 14: Drop saline tips to waste
    await tips_off(lh)
    # step 15: Pick up tips (column 2) for culture addition and first transfer
    await tips_on(lh, [res["tips"].get_item("A2"), res["tips"].get_item("B2"), res["tips"].get_item("C2"), res["tips"].get_item("D2"), res["tips"].get_item("E2"), res["tips"].get_item("F2"), res["tips"].get_item("G2"), res["tips"].get_item("H2")], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 16: Aspirate 10 uL culture
    await aspirate(lh, [res["culture"]] * 8, vols=[10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7], **reach(res["culture"], [0, 1, 2, 3, 4, 5, 6, 7]))
    # step 17: Add culture to column 1 (10^-1)
    await dispense(lh, [res["dilution_plate"].get_item("A1"), res["dilution_plate"].get_item("B1"), res["dilution_plate"].get_item("C1"), res["dilution_plate"].get_item("D1"), res["dilution_plate"].get_item("E1"), res["dilution_plate"].get_item("F1"), res["dilution_plate"].get_item("G1"), res["dilution_plate"].get_item("H1")], vols=[10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 18: Mix column 1: aspirate 50 uL
    await aspirate(lh, [res["dilution_plate"].get_item("A1"), res["dilution_plate"].get_item("B1"), res["dilution_plate"].get_item("C1"), res["dilution_plate"].get_item("D1"), res["dilution_plate"].get_item("E1"), res["dilution_plate"].get_item("F1"), res["dilution_plate"].get_item("G1"), res["dilution_plate"].get_item("H1")], vols=[50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 19: Mix column 1: dispense 50 uL back
    await dispense(lh, [res["dilution_plate"].get_item("A1"), res["dilution_plate"].get_item("B1"), res["dilution_plate"].get_item("C1"), res["dilution_plate"].get_item("D1"), res["dilution_plate"].get_item("E1"), res["dilution_plate"].get_item("F1"), res["dilution_plate"].get_item("G1"), res["dilution_plate"].get_item("H1")], vols=[50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 20: Take 10 uL from column 1 for transfer
    await aspirate(lh, [res["dilution_plate"].get_item("A1"), res["dilution_plate"].get_item("B1"), res["dilution_plate"].get_item("C1"), res["dilution_plate"].get_item("D1"), res["dilution_plate"].get_item("E1"), res["dilution_plate"].get_item("F1"), res["dilution_plate"].get_item("G1"), res["dilution_plate"].get_item("H1")], vols=[10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 21: Transfer into column 2 (10^-2)
    await dispense(lh, [res["dilution_plate"].get_item("A2"), res["dilution_plate"].get_item("B2"), res["dilution_plate"].get_item("C2"), res["dilution_plate"].get_item("D2"), res["dilution_plate"].get_item("E2"), res["dilution_plate"].get_item("F2"), res["dilution_plate"].get_item("G2"), res["dilution_plate"].get_item("H2")], vols=[10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 22: Drop tips to waste
    await tips_off(lh)
    # step 23: Pick up tips (column 3) for transfer 2
    await tips_on(lh, [res["tips"].get_item("A3"), res["tips"].get_item("B3"), res["tips"].get_item("C3"), res["tips"].get_item("D3"), res["tips"].get_item("E3"), res["tips"].get_item("F3"), res["tips"].get_item("G3"), res["tips"].get_item("H3")], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 24: Mix column 2: aspirate 50 uL
    await aspirate(lh, [res["dilution_plate"].get_item("A2"), res["dilution_plate"].get_item("B2"), res["dilution_plate"].get_item("C2"), res["dilution_plate"].get_item("D2"), res["dilution_plate"].get_item("E2"), res["dilution_plate"].get_item("F2"), res["dilution_plate"].get_item("G2"), res["dilution_plate"].get_item("H2")], vols=[50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 25: Mix column 2: dispense 50 uL back
    await dispense(lh, [res["dilution_plate"].get_item("A2"), res["dilution_plate"].get_item("B2"), res["dilution_plate"].get_item("C2"), res["dilution_plate"].get_item("D2"), res["dilution_plate"].get_item("E2"), res["dilution_plate"].get_item("F2"), res["dilution_plate"].get_item("G2"), res["dilution_plate"].get_item("H2")], vols=[50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 26: Take 10 uL from column 2 for transfer
    await aspirate(lh, [res["dilution_plate"].get_item("A2"), res["dilution_plate"].get_item("B2"), res["dilution_plate"].get_item("C2"), res["dilution_plate"].get_item("D2"), res["dilution_plate"].get_item("E2"), res["dilution_plate"].get_item("F2"), res["dilution_plate"].get_item("G2"), res["dilution_plate"].get_item("H2")], vols=[10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 27: Transfer into column 3 (10^-3)
    await dispense(lh, [res["dilution_plate"].get_item("A3"), res["dilution_plate"].get_item("B3"), res["dilution_plate"].get_item("C3"), res["dilution_plate"].get_item("D3"), res["dilution_plate"].get_item("E3"), res["dilution_plate"].get_item("F3"), res["dilution_plate"].get_item("G3"), res["dilution_plate"].get_item("H3")], vols=[10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 28: Drop tips to waste
    await tips_off(lh)
    # step 29: Pick up tips (column 4) for transfer 3
    await tips_on(lh, [res["tips"].get_item("A4"), res["tips"].get_item("B4"), res["tips"].get_item("C4"), res["tips"].get_item("D4"), res["tips"].get_item("E4"), res["tips"].get_item("F4"), res["tips"].get_item("G4"), res["tips"].get_item("H4")], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 30: Mix column 3: aspirate 50 uL
    await aspirate(lh, [res["dilution_plate"].get_item("A3"), res["dilution_plate"].get_item("B3"), res["dilution_plate"].get_item("C3"), res["dilution_plate"].get_item("D3"), res["dilution_plate"].get_item("E3"), res["dilution_plate"].get_item("F3"), res["dilution_plate"].get_item("G3"), res["dilution_plate"].get_item("H3")], vols=[50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 31: Mix column 3: dispense 50 uL back
    await dispense(lh, [res["dilution_plate"].get_item("A3"), res["dilution_plate"].get_item("B3"), res["dilution_plate"].get_item("C3"), res["dilution_plate"].get_item("D3"), res["dilution_plate"].get_item("E3"), res["dilution_plate"].get_item("F3"), res["dilution_plate"].get_item("G3"), res["dilution_plate"].get_item("H3")], vols=[50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 32: Take 10 uL from column 3 for transfer
    await aspirate(lh, [res["dilution_plate"].get_item("A3"), res["dilution_plate"].get_item("B3"), res["dilution_plate"].get_item("C3"), res["dilution_plate"].get_item("D3"), res["dilution_plate"].get_item("E3"), res["dilution_plate"].get_item("F3"), res["dilution_plate"].get_item("G3"), res["dilution_plate"].get_item("H3")], vols=[10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 33: Transfer into column 4 (10^-4)
    await dispense(lh, [res["dilution_plate"].get_item("A4"), res["dilution_plate"].get_item("B4"), res["dilution_plate"].get_item("C4"), res["dilution_plate"].get_item("D4"), res["dilution_plate"].get_item("E4"), res["dilution_plate"].get_item("F4"), res["dilution_plate"].get_item("G4"), res["dilution_plate"].get_item("H4")], vols=[10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 34: Drop tips to waste
    await tips_off(lh)
    # step 35: Pick up tips (column 5) for transfer 4
    await tips_on(lh, [res["tips"].get_item("A5"), res["tips"].get_item("B5"), res["tips"].get_item("C5"), res["tips"].get_item("D5"), res["tips"].get_item("E5"), res["tips"].get_item("F5"), res["tips"].get_item("G5"), res["tips"].get_item("H5")], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 36: Mix column 4: aspirate 50 uL
    await aspirate(lh, [res["dilution_plate"].get_item("A4"), res["dilution_plate"].get_item("B4"), res["dilution_plate"].get_item("C4"), res["dilution_plate"].get_item("D4"), res["dilution_plate"].get_item("E4"), res["dilution_plate"].get_item("F4"), res["dilution_plate"].get_item("G4"), res["dilution_plate"].get_item("H4")], vols=[50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 37: Mix column 4: dispense 50 uL back
    await dispense(lh, [res["dilution_plate"].get_item("A4"), res["dilution_plate"].get_item("B4"), res["dilution_plate"].get_item("C4"), res["dilution_plate"].get_item("D4"), res["dilution_plate"].get_item("E4"), res["dilution_plate"].get_item("F4"), res["dilution_plate"].get_item("G4"), res["dilution_plate"].get_item("H4")], vols=[50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 38: Take 10 uL from column 4 for transfer
    await aspirate(lh, [res["dilution_plate"].get_item("A4"), res["dilution_plate"].get_item("B4"), res["dilution_plate"].get_item("C4"), res["dilution_plate"].get_item("D4"), res["dilution_plate"].get_item("E4"), res["dilution_plate"].get_item("F4"), res["dilution_plate"].get_item("G4"), res["dilution_plate"].get_item("H4")], vols=[10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 39: Transfer into column 5 (10^-5)
    await dispense(lh, [res["dilution_plate"].get_item("A5"), res["dilution_plate"].get_item("B5"), res["dilution_plate"].get_item("C5"), res["dilution_plate"].get_item("D5"), res["dilution_plate"].get_item("E5"), res["dilution_plate"].get_item("F5"), res["dilution_plate"].get_item("G5"), res["dilution_plate"].get_item("H5")], vols=[10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 40: Drop tips to waste
    await tips_off(lh)
    # step 41: Pick up tips (column 6) for transfer 5
    await tips_on(lh, [res["tips"].get_item("A6"), res["tips"].get_item("B6"), res["tips"].get_item("C6"), res["tips"].get_item("D6"), res["tips"].get_item("E6"), res["tips"].get_item("F6"), res["tips"].get_item("G6"), res["tips"].get_item("H6")], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 42: Mix column 5: aspirate 50 uL
    await aspirate(lh, [res["dilution_plate"].get_item("A5"), res["dilution_plate"].get_item("B5"), res["dilution_plate"].get_item("C5"), res["dilution_plate"].get_item("D5"), res["dilution_plate"].get_item("E5"), res["dilution_plate"].get_item("F5"), res["dilution_plate"].get_item("G5"), res["dilution_plate"].get_item("H5")], vols=[50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 43: Mix column 5: dispense 50 uL back
    await dispense(lh, [res["dilution_plate"].get_item("A5"), res["dilution_plate"].get_item("B5"), res["dilution_plate"].get_item("C5"), res["dilution_plate"].get_item("D5"), res["dilution_plate"].get_item("E5"), res["dilution_plate"].get_item("F5"), res["dilution_plate"].get_item("G5"), res["dilution_plate"].get_item("H5")], vols=[50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 44: Take 10 uL from column 5 for transfer
    await aspirate(lh, [res["dilution_plate"].get_item("A5"), res["dilution_plate"].get_item("B5"), res["dilution_plate"].get_item("C5"), res["dilution_plate"].get_item("D5"), res["dilution_plate"].get_item("E5"), res["dilution_plate"].get_item("F5"), res["dilution_plate"].get_item("G5"), res["dilution_plate"].get_item("H5")], vols=[10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 45: Transfer into column 6 (10^-6)
    await dispense(lh, [res["dilution_plate"].get_item("A6"), res["dilution_plate"].get_item("B6"), res["dilution_plate"].get_item("C6"), res["dilution_plate"].get_item("D6"), res["dilution_plate"].get_item("E6"), res["dilution_plate"].get_item("F6"), res["dilution_plate"].get_item("G6"), res["dilution_plate"].get_item("H6")], vols=[10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 46: Drop tips to waste
    await tips_off(lh)
    # step 47: Pick up fresh tips (column 7) for final mix
    await tips_on(lh, [res["tips"].get_item("A7"), res["tips"].get_item("B7"), res["tips"].get_item("C7"), res["tips"].get_item("D7"), res["tips"].get_item("E7"), res["tips"].get_item("F7"), res["tips"].get_item("G7"), res["tips"].get_item("H7")], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 48: Mix column 6 (final dilution): aspirate 50 uL
    await aspirate(lh, [res["dilution_plate"].get_item("A6"), res["dilution_plate"].get_item("B6"), res["dilution_plate"].get_item("C6"), res["dilution_plate"].get_item("D6"), res["dilution_plate"].get_item("E6"), res["dilution_plate"].get_item("F6"), res["dilution_plate"].get_item("G6"), res["dilution_plate"].get_item("H6")], vols=[50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 49: Mix column 6: dispense 50 uL back
    await dispense(lh, [res["dilution_plate"].get_item("A6"), res["dilution_plate"].get_item("B6"), res["dilution_plate"].get_item("C6"), res["dilution_plate"].get_item("D6"), res["dilution_plate"].get_item("E6"), res["dilution_plate"].get_item("F6"), res["dilution_plate"].get_item("G6"), res["dilution_plate"].get_item("H6")], vols=[50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 50: Drop tips to waste; dilution series complete
    await tips_off(lh)


# --- Standalone runner: python healed/serial_1_10_dilution_of_culture_in_0_9_saline_20261112-220849_plr.py --backend chatterbox|star ---
DECK_CONFIG = 'decks/serial_1_10_dilution_of_culture_in_0_9_saline_20261112-220849.json'
INITIAL_VOLUMES_UL = {'diluent': 5000, 'culture': 400}


async def _main(backend_name):
    from pylabrobot.resources import set_tip_tracking, set_volume_tracking
    from pipeline.deck import build_deck, load_deck_config, machines
    from pipeline.instrument import firmware_configuration
    from pipeline.pipetting import close_device, open_device

    set_tip_tracking(True)
    set_volume_tracking(True)
    deck_config = load_deck_config(str(Path(__file__).resolve().parents[1] / DECK_CONFIG))
    deck, res = build_deck(deck_config, INITIAL_VOLUMES_UL)
    lh = await open_device(deck, backend_name, firmware_configuration(deck_config))
    for machine in machines(res):
        await machine.setup()
    try:
        await run_protocol(lh, res)
    finally:
        for machine in machines(res):
            await machine.stop()
        await close_device(lh)


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
