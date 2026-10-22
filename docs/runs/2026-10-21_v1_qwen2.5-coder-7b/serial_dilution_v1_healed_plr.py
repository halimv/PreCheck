"""Compiled from protocol: 2-Fold Serial Dilution Protocol (12 columns, 1000 uM to 0.488 uM). Do not edit; recompile from the IR."""


async def run_protocol(lh, res):
    # step 1: Pick up 8 tips, rack 1 column 1, for stock fill
    await lh.pick_up_tips([res["hamilton_tiprack_96"].get_item("A1"), res["hamilton_tiprack_96"].get_item("B1"), res["hamilton_tiprack_96"].get_item("C1"), res["hamilton_tiprack_96"].get_item("D1"), res["hamilton_tiprack_96"].get_item("E1"), res["hamilton_tiprack_96"].get_item("F1"), res["hamilton_tiprack_96"].get_item("G1"), res["hamilton_tiprack_96"].get_item("H1")], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 2: Aspirate 100 uL from tube_15ml using channel 0
    await lh.aspirate([res["tube_15ml"]] * 1, vols=[100.0], use_channels=[0])
    # step 3: Aspirate 100 uL from tube_15ml using channel 1
    await lh.aspirate([res["tube_15ml"]] * 1, vols=[100.0], use_channels=[1])
    # step 4: Aspirate 100 uL from tube_15ml using channel 2
    await lh.aspirate([res["tube_15ml"]] * 1, vols=[100.0], use_channels=[2])
    # step 5: Aspirate 100 uL from tube_15ml using channel 3
    await lh.aspirate([res["tube_15ml"]] * 1, vols=[100.0], use_channels=[3])
    # step 6: Aspirate 100 uL from tube_15ml using channel 4
    await lh.aspirate([res["tube_15ml"]] * 1, vols=[100.0], use_channels=[4])
    # step 7: Aspirate 100 uL from tube_15ml using channel 5
    await lh.aspirate([res["tube_15ml"]] * 1, vols=[100.0], use_channels=[5])
    # step 8: Aspirate 100 uL from tube_15ml using channel 6
    await lh.aspirate([res["tube_15ml"]] * 1, vols=[100.0], use_channels=[6])
    # step 9: Aspirate 100 uL from tube_15ml using channel 7
    await lh.aspirate([res["tube_15ml"]] * 1, vols=[100.0], use_channels=[7])
    # step 10: Dispense 100 uL stock into plate column 1 (1000 uM)
    await lh.dispense([res["corning_3595"].get_item("A1"), res["corning_3595"].get_item("B1"), res["corning_3595"].get_item("C1"), res["corning_3595"].get_item("D1"), res["corning_3595"].get_item("E1"), res["corning_3595"].get_item("F1"), res["corning_3595"].get_item("G1"), res["corning_3595"].get_item("H1")], vols=[100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 11: Eject stock tips to waste
    await lh.discard_tips()
    # step 12: Pick up 8 tips, rack 1 column 2, for diluent
    await lh.pick_up_tips([res["hamilton_tiprack_96"].get_item("A2"), res["hamilton_tiprack_96"].get_item("B2"), res["hamilton_tiprack_96"].get_item("C2"), res["hamilton_tiprack_96"].get_item("D2"), res["hamilton_tiprack_96"].get_item("E2"), res["hamilton_tiprack_96"].get_item("F2"), res["hamilton_tiprack_96"].get_item("G2"), res["hamilton_tiprack_96"].get_item("H2")], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 13: Aspirate 200 uL diluent from reservoir for columns 2-5
    await lh.aspirate([res["reservoir_50ml"]] * 8, vols=[200.0, 200.0, 200.0, 200.0, 200.0, 200.0, 200.0, 200.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 14: Dispense 50 uL diluent into plate column 2
    await lh.dispense([res["corning_3595"].get_item("A2"), res["corning_3595"].get_item("B2"), res["corning_3595"].get_item("C2"), res["corning_3595"].get_item("D2"), res["corning_3595"].get_item("E2"), res["corning_3595"].get_item("F2"), res["corning_3595"].get_item("G2"), res["corning_3595"].get_item("H2")], vols=[50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 15: Dispense 50 uL diluent into plate column 3
    await lh.dispense([res["corning_3595"].get_item("A3"), res["corning_3595"].get_item("B3"), res["corning_3595"].get_item("C3"), res["corning_3595"].get_item("D3"), res["corning_3595"].get_item("E3"), res["corning_3595"].get_item("F3"), res["corning_3595"].get_item("G3"), res["corning_3595"].get_item("H3")], vols=[50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 16: Dispense 50 uL diluent into plate column 4
    await lh.dispense([res["corning_3595"].get_item("A4"), res["corning_3595"].get_item("B4"), res["corning_3595"].get_item("C4"), res["corning_3595"].get_item("D4"), res["corning_3595"].get_item("E4"), res["corning_3595"].get_item("F4"), res["corning_3595"].get_item("G4"), res["corning_3595"].get_item("H4")], vols=[50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 17: Dispense 50 uL diluent into plate column 5
    await lh.dispense([res["corning_3595"].get_item("A5"), res["corning_3595"].get_item("B5"), res["corning_3595"].get_item("C5"), res["corning_3595"].get_item("D5"), res["corning_3595"].get_item("E5"), res["corning_3595"].get_item("F5"), res["corning_3595"].get_item("G5"), res["corning_3595"].get_item("H5")], vols=[50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 18: Aspirate 200 uL diluent from reservoir for columns 6-9
    await lh.aspirate([res["reservoir_50ml"]] * 8, vols=[200.0, 200.0, 200.0, 200.0, 200.0, 200.0, 200.0, 200.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 19: Dispense 50 uL diluent into plate column 6
    await lh.dispense([res["corning_3595"].get_item("A6"), res["corning_3595"].get_item("B6"), res["corning_3595"].get_item("C6"), res["corning_3595"].get_item("D6"), res["corning_3595"].get_item("E6"), res["corning_3595"].get_item("F6"), res["corning_3595"].get_item("G6"), res["corning_3595"].get_item("H6")], vols=[50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 20: Dispense 50 uL diluent into plate column 7
    await lh.dispense([res["corning_3595"].get_item("A7"), res["corning_3595"].get_item("B7"), res["corning_3595"].get_item("C7"), res["corning_3595"].get_item("D7"), res["corning_3595"].get_item("E7"), res["corning_3595"].get_item("F7"), res["corning_3595"].get_item("G7"), res["corning_3595"].get_item("H7")], vols=[50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 21: Dispense 50 uL diluent into plate column 8
    await lh.dispense([res["corning_3595"].get_item("A8"), res["corning_3595"].get_item("B8"), res["corning_3595"].get_item("C8"), res["corning_3595"].get_item("D8"), res["corning_3595"].get_item("E8"), res["corning_3595"].get_item("F8"), res["corning_3595"].get_item("G8"), res["corning_3595"].get_item("H8")], vols=[50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 22: Dispense 50 uL diluent into plate column 9
    await lh.dispense([res["corning_3595"].get_item("A9"), res["corning_3595"].get_item("B9"), res["corning_3595"].get_item("C9"), res["corning_3595"].get_item("D9"), res["corning_3595"].get_item("E9"), res["corning_3595"].get_item("F9"), res["corning_3595"].get_item("G9"), res["corning_3595"].get_item("H9")], vols=[50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 23: Aspirate 150 uL diluent from reservoir for columns 10-12
    await lh.aspirate([res["reservoir_50ml"]] * 8, vols=[150.0, 150.0, 150.0, 150.0, 150.0, 150.0, 150.0, 150.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 24: Dispense 50 uL diluent into plate column 10
    await lh.dispense([res["corning_3595"].get_item("A10"), res["corning_3595"].get_item("B10"), res["corning_3595"].get_item("C10"), res["corning_3595"].get_item("D10"), res["corning_3595"].get_item("E10"), res["corning_3595"].get_item("F10"), res["corning_3595"].get_item("G10"), res["corning_3595"].get_item("H10")], vols=[50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 25: Dispense 50 uL diluent into plate column 11
    await lh.dispense([res["corning_3595"].get_item("A11"), res["corning_3595"].get_item("B11"), res["corning_3595"].get_item("C11"), res["corning_3595"].get_item("D11"), res["corning_3595"].get_item("E11"), res["corning_3595"].get_item("F11"), res["corning_3595"].get_item("G11"), res["corning_3595"].get_item("H11")], vols=[50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 26: Dispense 50 uL diluent into plate column 12
    await lh.dispense([res["corning_3595"].get_item("A12"), res["corning_3595"].get_item("B12"), res["corning_3595"].get_item("C12"), res["corning_3595"].get_item("D12"), res["corning_3595"].get_item("E12"), res["corning_3595"].get_item("F12"), res["corning_3595"].get_item("G12"), res["corning_3595"].get_item("H12")], vols=[50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 27: Eject diluent tips to waste
    await lh.discard_tips()
    # step 28: Pick up 8 tips, rack 2 column 1, for transfer 1 to 2
    await lh.pick_up_tips([res["hamilton_tiprack_96_b"].get_item("A1"), res["hamilton_tiprack_96_b"].get_item("B1"), res["hamilton_tiprack_96_b"].get_item("C1"), res["hamilton_tiprack_96_b"].get_item("D1"), res["hamilton_tiprack_96_b"].get_item("E1"), res["hamilton_tiprack_96_b"].get_item("F1"), res["hamilton_tiprack_96_b"].get_item("G1"), res["hamilton_tiprack_96_b"].get_item("H1")], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 29: Aspirate 50 uL from plate column 1 (mixed 1000 uM)
    await lh.aspirate([res["corning_3595"].get_item("A1"), res["corning_3595"].get_item("B1"), res["corning_3595"].get_item("C1"), res["corning_3595"].get_item("D1"), res["corning_3595"].get_item("E1"), res["corning_3595"].get_item("F1"), res["corning_3595"].get_item("G1"), res["corning_3595"].get_item("H1")], vols=[50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 30: Dispense 50 uL into plate column 2 (now 500 uM)
    await lh.dispense([res["corning_3595"].get_item("A2"), res["corning_3595"].get_item("B2"), res["corning_3595"].get_item("C2"), res["corning_3595"].get_item("D2"), res["corning_3595"].get_item("E2"), res["corning_3595"].get_item("F2"), res["corning_3595"].get_item("G2"), res["corning_3595"].get_item("H2")], vols=[50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 31: Eject transfer 1 tips to waste
    await lh.discard_tips()
    # step 32: Pick up 8 tips, rack 2 column 2, for transfer 2 to 3
    await lh.pick_up_tips([res["hamilton_tiprack_96_b"].get_item("A2"), res["hamilton_tiprack_96_b"].get_item("B2"), res["hamilton_tiprack_96_b"].get_item("C2"), res["hamilton_tiprack_96_b"].get_item("D2"), res["hamilton_tiprack_96_b"].get_item("E2"), res["hamilton_tiprack_96_b"].get_item("F2"), res["hamilton_tiprack_96_b"].get_item("G2"), res["hamilton_tiprack_96_b"].get_item("H2")], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 33: Aspirate 50 uL from plate column 2 (mixed 500 uM)
    await lh.aspirate([res["corning_3595"].get_item("A2"), res["corning_3595"].get_item("B2"), res["corning_3595"].get_item("C2"), res["corning_3595"].get_item("D2"), res["corning_3595"].get_item("E2"), res["corning_3595"].get_item("F2"), res["corning_3595"].get_item("G2"), res["corning_3595"].get_item("H2")], vols=[50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 34: Dispense 50 uL into plate column 3 (now 250 uM)
    await lh.dispense([res["corning_3595"].get_item("A3"), res["corning_3595"].get_item("B3"), res["corning_3595"].get_item("C3"), res["corning_3595"].get_item("D3"), res["corning_3595"].get_item("E3"), res["corning_3595"].get_item("F3"), res["corning_3595"].get_item("G3"), res["corning_3595"].get_item("H3")], vols=[50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 35: Eject transfer 2 tips to waste
    await lh.discard_tips()
    # step 36: Pick up 8 tips, rack 2 column 3, for transfer 3 to 4
    await lh.pick_up_tips([res["hamilton_tiprack_96_b"].get_item("A3"), res["hamilton_tiprack_96_b"].get_item("B3"), res["hamilton_tiprack_96_b"].get_item("C3"), res["hamilton_tiprack_96_b"].get_item("D3"), res["hamilton_tiprack_96_b"].get_item("E3"), res["hamilton_tiprack_96_b"].get_item("F3"), res["hamilton_tiprack_96_b"].get_item("G3"), res["hamilton_tiprack_96_b"].get_item("H3")], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 37: Aspirate 50 uL from plate column 3 (mixed 250 uM)
    await lh.aspirate([res["corning_3595"].get_item("A3"), res["corning_3595"].get_item("B3"), res["corning_3595"].get_item("C3"), res["corning_3595"].get_item("D3"), res["corning_3595"].get_item("E3"), res["corning_3595"].get_item("F3"), res["corning_3595"].get_item("G3"), res["corning_3595"].get_item("H3")], vols=[50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 38: Dispense 50 uL into plate column 4 (now 125 uM)
    await lh.dispense([res["corning_3595"].get_item("A4"), res["corning_3595"].get_item("B4"), res["corning_3595"].get_item("C4"), res["corning_3595"].get_item("D4"), res["corning_3595"].get_item("E4"), res["corning_3595"].get_item("F4"), res["corning_3595"].get_item("G4"), res["corning_3595"].get_item("H4")], vols=[50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 39: Eject transfer 3 tips to waste
    await lh.discard_tips()
    # step 40: Pick up 8 tips, rack 2 column 4, for transfer 4 to 5
    await lh.pick_up_tips([res["hamilton_tiprack_96_b"].get_item("A4"), res["hamilton_tiprack_96_b"].get_item("B4"), res["hamilton_tiprack_96_b"].get_item("C4"), res["hamilton_tiprack_96_b"].get_item("D4"), res["hamilton_tiprack_96_b"].get_item("E4"), res["hamilton_tiprack_96_b"].get_item("F4"), res["hamilton_tiprack_96_b"].get_item("G4"), res["hamilton_tiprack_96_b"].get_item("H4")], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 41: Aspirate 50 uL from plate column 4 (mixed 125 uM)
    await lh.aspirate([res["corning_3595"].get_item("A4"), res["corning_3595"].get_item("B4"), res["corning_3595"].get_item("C4"), res["corning_3595"].get_item("D4"), res["corning_3595"].get_item("E4"), res["corning_3595"].get_item("F4"), res["corning_3595"].get_item("G4"), res["corning_3595"].get_item("H4")], vols=[50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 42: Dispense 50 uL into plate column 5 (now 62.5 uM)
    await lh.dispense([res["corning_3595"].get_item("A5"), res["corning_3595"].get_item("B5"), res["corning_3595"].get_item("C5"), res["corning_3595"].get_item("D5"), res["corning_3595"].get_item("E5"), res["corning_3595"].get_item("F5"), res["corning_3595"].get_item("G5"), res["corning_3595"].get_item("H5")], vols=[50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 43: Eject transfer 4 tips to waste
    await lh.discard_tips()
    # step 44: Pick up 8 tips, rack 2 column 5, for transfer 5 to 6
    await lh.pick_up_tips([res["hamilton_tiprack_96_b"].get_item("A5"), res["hamilton_tiprack_96_b"].get_item("B5"), res["hamilton_tiprack_96_b"].get_item("C5"), res["hamilton_tiprack_96_b"].get_item("D5"), res["hamilton_tiprack_96_b"].get_item("E5"), res["hamilton_tiprack_96_b"].get_item("F5"), res["hamilton_tiprack_96_b"].get_item("G5"), res["hamilton_tiprack_96_b"].get_item("H5")], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 45: Aspirate 50 uL from plate column 5 (mixed 62.5 uM)
    await lh.aspirate([res["corning_3595"].get_item("A5"), res["corning_3595"].get_item("B5"), res["corning_3595"].get_item("C5"), res["corning_3595"].get_item("D5"), res["corning_3595"].get_item("E5"), res["corning_3595"].get_item("F5"), res["corning_3595"].get_item("G5"), res["corning_3595"].get_item("H5")], vols=[50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 46: Dispense 50 uL into plate column 6 (now 31.25 uM)
    await lh.dispense([res["corning_3595"].get_item("A6"), res["corning_3595"].get_item("B6"), res["corning_3595"].get_item("C6"), res["corning_3595"].get_item("D6"), res["corning_3595"].get_item("E6"), res["corning_3595"].get_item("F6"), res["corning_3595"].get_item("G6"), res["corning_3595"].get_item("H6")], vols=[50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 47: Eject transfer 5 tips to waste
    await lh.discard_tips()
    # step 48: Pick up 8 tips, rack 2 column 6, for transfer 6 to 7
    await lh.pick_up_tips([res["hamilton_tiprack_96_b"].get_item("A6"), res["hamilton_tiprack_96_b"].get_item("B6"), res["hamilton_tiprack_96_b"].get_item("C6"), res["hamilton_tiprack_96_b"].get_item("D6"), res["hamilton_tiprack_96_b"].get_item("E6"), res["hamilton_tiprack_96_b"].get_item("F6"), res["hamilton_tiprack_96_b"].get_item("G6"), res["hamilton_tiprack_96_b"].get_item("H6")], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 49: Aspirate 50 uL from plate column 6 (mixed 31.25 uM)
    await lh.aspirate([res["corning_3595"].get_item("A6"), res["corning_3595"].get_item("B6"), res["corning_3595"].get_item("C6"), res["corning_3595"].get_item("D6"), res["corning_3595"].get_item("E6"), res["corning_3595"].get_item("F6"), res["corning_3595"].get_item("G6"), res["corning_3595"].get_item("H6")], vols=[50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 50: Dispense 50 uL into plate column 7 (now 15.625 uM)
    await lh.dispense([res["corning_3595"].get_item("A7"), res["corning_3595"].get_item("B7"), res["corning_3595"].get_item("C7"), res["corning_3595"].get_item("D7"), res["corning_3595"].get_item("E7"), res["corning_3595"].get_item("F7"), res["corning_3595"].get_item("G7"), res["corning_3595"].get_item("H7")], vols=[50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 51: Eject transfer 6 tips to waste
    await lh.discard_tips()
    # step 52: Pick up 8 tips, rack 2 column 7, for transfer 7 to 8
    await lh.pick_up_tips([res["hamilton_tiprack_96_b"].get_item("A7"), res["hamilton_tiprack_96_b"].get_item("B7"), res["hamilton_tiprack_96_b"].get_item("C7"), res["hamilton_tiprack_96_b"].get_item("D7"), res["hamilton_tiprack_96_b"].get_item("E7"), res["hamilton_tiprack_96_b"].get_item("F7"), res["hamilton_tiprack_96_b"].get_item("G7"), res["hamilton_tiprack_96_b"].get_item("H7")], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 53: Aspirate 50 uL from plate column 7 (mixed 15.625 uM)
    await lh.aspirate([res["corning_3595"].get_item("A7"), res["corning_3595"].get_item("B7"), res["corning_3595"].get_item("C7"), res["corning_3595"].get_item("D7"), res["corning_3595"].get_item("E7"), res["corning_3595"].get_item("F7"), res["corning_3595"].get_item("G7"), res["corning_3595"].get_item("H7")], vols=[50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 54: Dispense 50 uL into plate column 8 (now 7.8125 uM)
    await lh.dispense([res["corning_3595"].get_item("A8"), res["corning_3595"].get_item("B8"), res["corning_3595"].get_item("C8"), res["corning_3595"].get_item("D8"), res["corning_3595"].get_item("E8"), res["corning_3595"].get_item("F8"), res["corning_3595"].get_item("G8"), res["corning_3595"].get_item("H8")], vols=[50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 55: Eject transfer 7 tips to waste
    await lh.discard_tips()
    # step 56: Pick up 8 tips, rack 2 column 8, for transfer 8 to 9
    await lh.pick_up_tips([res["hamilton_tiprack_96_b"].get_item("A8"), res["hamilton_tiprack_96_b"].get_item("B8"), res["hamilton_tiprack_96_b"].get_item("C8"), res["hamilton_tiprack_96_b"].get_item("D8"), res["hamilton_tiprack_96_b"].get_item("E8"), res["hamilton_tiprack_96_b"].get_item("F8"), res["hamilton_tiprack_96_b"].get_item("G8"), res["hamilton_tiprack_96_b"].get_item("H8")], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 57: Aspirate 50 uL from plate column 8 (mixed 7.8125 uM)
    await lh.aspirate([res["corning_3595"].get_item("A8"), res["corning_3595"].get_item("B8"), res["corning_3595"].get_item("C8"), res["corning_3595"].get_item("D8"), res["corning_3595"].get_item("E8"), res["corning_3595"].get_item("F8"), res["corning_3595"].get_item("G8"), res["corning_3595"].get_item("H8")], vols=[50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 58: Dispense 50 uL into plate column 9 (now 3.90625 uM)
    await lh.dispense([res["corning_3595"].get_item("A9"), res["corning_3595"].get_item("B9"), res["corning_3595"].get_item("C9"), res["corning_3595"].get_item("D9"), res["corning_3595"].get_item("E9"), res["corning_3595"].get_item("F9"), res["corning_3595"].get_item("G9"), res["corning_3595"].get_item("H9")], vols=[50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 59: Eject transfer 8 tips to waste
    await lh.discard_tips()
    # step 60: Pick up 8 tips, rack 2 column 9, for transfer 9 to 10
    await lh.pick_up_tips([res["hamilton_tiprack_96_b"].get_item("A9"), res["hamilton_tiprack_96_b"].get_item("B9"), res["hamilton_tiprack_96_b"].get_item("C9"), res["hamilton_tiprack_96_b"].get_item("D9"), res["hamilton_tiprack_96_b"].get_item("E9"), res["hamilton_tiprack_96_b"].get_item("F9"), res["hamilton_tiprack_96_b"].get_item("G9"), res["hamilton_tiprack_96_b"].get_item("H9")], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 61: Aspirate 50 uL from plate column 9 (mixed 3.90625 uM)
    await lh.aspirate([res["corning_3595"].get_item("A9"), res["corning_3595"].get_item("B9"), res["corning_3595"].get_item("C9"), res["corning_3595"].get_item("D9"), res["corning_3595"].get_item("E9"), res["corning_3595"].get_item("F9"), res["corning_3595"].get_item("G9"), res["corning_3595"].get_item("H9")], vols=[50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 62: Dispense 50 uL into plate column 10 (now 1.95312 uM)
    await lh.dispense([res["corning_3595"].get_item("A10"), res["corning_3595"].get_item("B10"), res["corning_3595"].get_item("C10"), res["corning_3595"].get_item("D10"), res["corning_3595"].get_item("E10"), res["corning_3595"].get_item("F10"), res["corning_3595"].get_item("G10"), res["corning_3595"].get_item("H10")], vols=[50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 63: Eject transfer 9 tips to waste
    await lh.discard_tips()
    # step 64: Pick up 8 tips, rack 2 column 10, for transfer 10 to 11
    await lh.pick_up_tips([res["hamilton_tiprack_96_b"].get_item("A10"), res["hamilton_tiprack_96_b"].get_item("B10"), res["hamilton_tiprack_96_b"].get_item("C10"), res["hamilton_tiprack_96_b"].get_item("D10"), res["hamilton_tiprack_96_b"].get_item("E10"), res["hamilton_tiprack_96_b"].get_item("F10"), res["hamilton_tiprack_96_b"].get_item("G10"), res["hamilton_tiprack_96_b"].get_item("H10")], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 65: Aspirate 50 uL from plate column 10 (mixed 1.95312 uM)
    await lh.aspirate([res["corning_3595"].get_item("A10"), res["corning_3595"].get_item("B10"), res["corning_3595"].get_item("C10"), res["corning_3595"].get_item("D10"), res["corning_3595"].get_item("E10"), res["corning_3595"].get_item("F10"), res["corning_3595"].get_item("G10"), res["corning_3595"].get_item("H10")], vols=[50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 66: Dispense 50 uL into plate column 11 (now 0.976562 uM)
    await lh.dispense([res["corning_3595"].get_item("A11"), res["corning_3595"].get_item("B11"), res["corning_3595"].get_item("C11"), res["corning_3595"].get_item("D11"), res["corning_3595"].get_item("E11"), res["corning_3595"].get_item("F11"), res["corning_3595"].get_item("G11"), res["corning_3595"].get_item("H11")], vols=[50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 67: Eject transfer 10 tips to waste
    await lh.discard_tips()
    # step 68: Pick up 8 tips, rack 2 column 11, for transfer 11 to 12
    await lh.pick_up_tips([res["hamilton_tiprack_96_b"].get_item("A11"), res["hamilton_tiprack_96_b"].get_item("B11"), res["hamilton_tiprack_96_b"].get_item("C11"), res["hamilton_tiprack_96_b"].get_item("D11"), res["hamilton_tiprack_96_b"].get_item("E11"), res["hamilton_tiprack_96_b"].get_item("F11"), res["hamilton_tiprack_96_b"].get_item("G11"), res["hamilton_tiprack_96_b"].get_item("H11")], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 69: Aspirate 50 uL from plate column 11 (mixed 0.976562 uM)
    await lh.aspirate([res["corning_3595"].get_item("A11"), res["corning_3595"].get_item("B11"), res["corning_3595"].get_item("C11"), res["corning_3595"].get_item("D11"), res["corning_3595"].get_item("E11"), res["corning_3595"].get_item("F11"), res["corning_3595"].get_item("G11"), res["corning_3595"].get_item("H11")], vols=[50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 70: Dispense 50 uL into plate column 12 (now 0.488281 uM)
    await lh.dispense([res["corning_3595"].get_item("A12"), res["corning_3595"].get_item("B12"), res["corning_3595"].get_item("C12"), res["corning_3595"].get_item("D12"), res["corning_3595"].get_item("E12"), res["corning_3595"].get_item("F12"), res["corning_3595"].get_item("G12"), res["corning_3595"].get_item("H12")], vols=[50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 71: Eject transfer 11 tips to waste
    await lh.discard_tips()
    # step 72: Pick up 8 tips, rack 2 column 12, for final discard
    await lh.pick_up_tips([res["hamilton_tiprack_96_b"].get_item("A12"), res["hamilton_tiprack_96_b"].get_item("B12"), res["hamilton_tiprack_96_b"].get_item("C12"), res["hamilton_tiprack_96_b"].get_item("D12"), res["hamilton_tiprack_96_b"].get_item("E12"), res["hamilton_tiprack_96_b"].get_item("F12"), res["hamilton_tiprack_96_b"].get_item("G12"), res["hamilton_tiprack_96_b"].get_item("H12")], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 73: Aspirate 50 uL excess from plate column 12
    await lh.aspirate([res["corning_3595"].get_item("A12"), res["corning_3595"].get_item("B12"), res["corning_3595"].get_item("C12"), res["corning_3595"].get_item("D12"), res["corning_3595"].get_item("E12"), res["corning_3595"].get_item("F12"), res["corning_3595"].get_item("G12"), res["corning_3595"].get_item("H12")], vols=[50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 74: Discard 50 uL excess to waste
    await lh.dispense([res["waste"]] * 8, vols=[50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0], use_channels=[0, 1, 2, 3, 4, 5, 6, 7])
    # step 75: Eject discard tips to waste
    await lh.discard_tips()
