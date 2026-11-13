The diluent draw can't be 4 × 90 µL = 360 µL, because the 300 µL filter tip can't hold it. Each draw will be 270 µL (3 × 90 µL), so columns 1 to 3 come from one draw and columns 4 to 6 from a second. That makes steps 2 to 13 into 10 steps, and the later steps are renumbered.

```json
{
 "protocol_name": "Serial 1:10 dilution of culture in 0.9% saline",
 "description": "Makes a six-step 1:10 serial dilution of an optimum-growth culture in sterile 0.9% saline across plate columns 1 to 6 (10^-1 to 10^-6). Diluent is drawn in multi-dispense batches of three columns each. Plating and colony counting happen off the deck.",
 "assumptions": [
  "Scaled the bench 1 mL culture into 10 mL diluent to 10 µL culture into 90 µL saline per step. This keeps the 1:10 dilution factor per step (1 part culture to 9 parts diluent, 100 µL total). Read literally, '1 mL in 10 mL' is 1:11, so tell me if you want that instead.",
  "Column 1 is 10^-1 and column k is 10^-k, so columns 1 to 6 cover 10^-1 to 10^-6. Columns 7 to 12 are unused. Plating and counting, and choosing the dilution that gives 10 to 100 CFU/mL, are off the robot.",
  "Each well holds 100 µL during the run and keeps 90 µL after each transfer, which stays within the 289.7 µL well capacity.",
  "Culture is held in a reservoir (trough) rather than a tube so that all 8 channels can aspirate from it. 500 µL is loaded, which covers the 80 µL needed plus dead volume.",
  "All tips are 300 µL filter tips, the size already on deck. This is the smallest tip that holds a 90 µL aspiration. 10 µL transfers would be more accurate with 10 µL tips, but the deck does not have them.",
  "Diluent is multi-dispensed. Four 90 µL dispenses would need 360 µL, which does not fit in a 300 µL tip, so each diluent draw is 270 µL (3 × 90 µL). Columns 1 to 3 come from the first draw and columns 4 to 6 from the second.",
  "Each column is mixed with 50 µL before its 10 µL transfer, and the last column is mixed at the end with fresh tips.",
  "Tip columns are used once each: column 1 for diluent, column 2 for culture, columns 3 to 8 for mixing and transfers.",
  "The robot does not incubate or grow the culture, and does not handle sterility of the deck or tips. The saline is assumed sterile and the culture is assumed to be at optimum growth before the run."
 ],
 "labware": {
  "tips": {
   "kind": "tip_rack",
   "tip_volume_ul": 300,
   "filter": true,
   "description": "300 µL filter tips for diluent, culture, mixing and transfers (on deck)"
  },
  "diluent": {
   "kind": "reservoir",
   "min_capacity_ul": 6000,
   "description": "0.9% normal saline trough, 4320 µL needed for 6 columns x 90 µL x 8 channels plus dead volume"
  },
  "culture": {
   "kind": "reservoir",
   "min_capacity_ul": 500,
   "description": "Optimum-growth culture trough, 80 µL needed for column 1"
  },
  "dilution_plate": {
   "kind": "plate",
   "wells": 96,
   "min_capacity_ul": 150,
   "description": "96-well PCR plate (Cos_96_PCR, on deck); columns 1-6 hold the 10^-1 to 10^-6 dilutions"
  },
  "waste": {
   "kind": "waste",
   "description": "Tips and discarded liquid"
  }
 },
 "reagents": {
  "diluent": "0.9% normal saline (sterile)",
  "culture": "Optimum-growth culture"
 },
 "initial_volumes_ul": {
  "diluent": 5000,
  "culture": 500
 },
 "steps": [
  {"step": 1, "action": "tips_on", "labware": "tips", "column": 1, "volume_ul": 0, "channels": [0,1,2,3,4,5,6,7], "description": "Pick up tip column 1 for diluent"},
  {"step": 2, "action": "aspirate", "labware": "diluent", "volume_ul": 270, "channels": [0,1,2,3,4,5,6,7], "description": "Aspirate 270 µL saline (enough for 3 dispenses of 90 µL)"},
  {"step": 3, "action": "dispense", "labware": "dilution_plate", "column": 1, "volume_ul": 90, "channels": [0,1,2,3,4,5,6,7], "description": "Dispense 90 µL saline into column 1 (dispense 1 of 3 from this draw)"},
  {"step": 4, "action": "dispense", "labware": "dilution_plate", "column": 2, "volume_ul": 90, "channels": [0,1,2,3,4,5,6,7], "description": "Dispense 90 µL saline into column 2 (dispense 2 of 3 from this draw)"},
  {"step": 5, "action": "dispense", "labware": "dilution_plate", "column": 3, "volume_ul": 90, "channels": [0,1,2,3,4,5,6,7], "description": "Dispense 90 µL saline into column 3 (dispense 3 of 3 from this draw)"},
  {"step": 6, "action": "aspirate", "labware": "diluent", "volume_ul": 270, "channels": [0,1,2,3,4,5,6,7], "description": "Aspirate 270 µL saline (enough for 3 dispenses of 90 µL)"},
  {"step": 7, "action": "dispense", "labware": "dilution_plate", "column": 4, "volume_ul": 90, "channels": [0,1,2,3,4,5,6,7], "description": "Dispense 90 µL saline into column 4 (dispense 1 of 3 from this draw)"},
  {"step": 8, "action": "dispense", "labware": "dilution_plate", "column": 5, "volume_ul": 90, "channels": [0,1,2,3,4,5,6,7], "description": "Dispense 90 µL saline into column 5 (dispense 2 of 3 from this draw)"},
  {"step": 9, "action": "dispense", "labware": "dilution_plate", "column": 6, "volume_ul": 90, "channels": [0,1,2,3,4,5,6,7], "description": "Dispense 90 µL saline into column 6 (dispense 3 of 3 from this draw)"},
  {"step": 10, "action": "tips_off", "labware": "waste", "volume_ul": 0, "channels": [0,1,2,3,4,5,6,7], "description": "Drop diluent tips"},
  {"step": 11, "action": "tips_on", "labware": "tips", "column": 2, "volume_ul": 0, "channels": [0,1,2,3,4,5,6,7], "description": "Pick up tip column 2 for culture"},
  {"step": 12, "action": "aspirate", "labware": "culture", "volume_ul": 10, "channels": [0,1,2,3,4,5,6,7], "description": "Aspirate 10 µL culture"},
  {"step": 13, "action": "dispense", "labware": "dilution_plate", "column": 1, "volume_ul": 10, "channels": [0,1,2,3,4,5,6,7], "description": "Add culture to column 1 (now 10^-1, 100 µL)"},
  {"step": 14, "action": "tips_off", "labware": "waste", "volume_ul": 0, "channels": [0,1,2,3,4,5,6,7], "description": "Drop culture tips"},
  {"step": 15, "action": "tips_on", "labware": "tips", "column": 3, "volume_ul": 0, "channels": [0,1,2,3,4,5,6,7], "description": "Pick up tip column 3 for mix and transfer 1 to 2"},
  {"step": 16, "action": "aspirate", "labware": "dilution_plate", "column": 1, "volume_ul": 50, "channels": [0,1,2,3,4,5,6,7], "description": "Mix column 1: aspirate 50 µL"},
  {"step": 17, "action": "dispense", "labware": "dilution_plate", "column": 1, "volume_ul": 50, "channels": [0,1,2,3,4,5,6,7], "description": "Mix column 1: dispense 50 µL back"},
  {"step": 18, "action": "aspirate", "labware": "dilution_plate", "column": 1, "volume_ul": 10, "channels": [0,1,2,3,4,5,6,7], "description": "Take 10 µL from column 1"},
  {"step": 19, "action": "dispense", "labware": "dilution_plate", "column": 2, "volume_ul": 10, "channels": [0,1,2,3,4,5,6,7], "description": "Transfer to column 2 (10^-2)"},
  {"step": 20, "action": "tips_off", "labware": "waste", "volume_ul": 0, "channels": [0,1,2,3,4,5,6,7], "description": "Drop tips"},
  {"step": 21, "action": "tips_on", "labware": "tips", "column": 4, "volume_ul": 0, "channels": [0,1,2,3,4,5,6,7], "description": "Pick up tip column 4 for mix and transfer 2 to 3"},
  {"step": 22, "action": "aspirate", "labware": "dilution_plate", "column": 2, "volume_ul": 50, "channels": [0,1,2,3,4,5,6,7], "description": "Mix column 2: aspirate 50 µL"},
  {"step": 23, "action": "dispense", "labware": "dilution_plate", "column": 2, "volume_ul": 50, "channels": [0,1,2,3,4,5,6,7], "description": "Mix column 2: dispense 50 µL back"},
  {"step": 24, "action": "aspirate", "labware": "dilution_plate", "column": 2, "volume_ul": 10, "channels": [0,1,2,3,4,5,6,7], "description": "Take 10 µL from column 2"},
  {"step": 25, "action": "dispense", "labware": "dilution_plate", "column": 3, "volume_ul": 10, "channels": [0,1,2,3,4,5,6,7], "description": "Transfer to column 3 (10^-3)"},
  {"step": 26, "action": "tips_off", "labware": "waste", "volume_ul": 0, "channels": [0,1,2,3,4,5,6,7], "description": "Drop tips"},
  {"step": 27, "action": "tips_on", "labware": "tips", "column": 5, "volume_ul": 0, "channels": [0,1,2,3,4,5,6,7], "description": "Pick up tip column 5 for mix and transfer 3 to 4"},
  {"step": 28, "action": "aspirate", "labware": "dilution_plate", "column": 3, "volume_ul": 50, "channels": [0,1,2,3,4,5,6,7], "description": "Mix column 3: aspirate 50 µL"},
  {"step": 29, "action": "dispense", "labware": "dilution_plate", "column": 3, "volume_ul": 50, "channels": [0,1,2,3,4,5,6,7], "description": "Mix column 3: dispense 50 µL back"},
  {"step": 30, "action": "aspirate", "labware": "dilution_plate", "column": 3, "volume_ul": 10, "channels": [0,1,2,3,4,5,6,7], "description": "Take 10 µL from column 3"},
  {"step": 31, "action": "dispense", "labware": "dilution_plate", "column": 4, "volume_ul": 10, "channels": [0,1,2,3,4,5,6,7], "description": "Transfer to column 4 (10^-4)"},
  {"step": 32, "action": "tips_off", "labware": "waste", "volume_ul": 0, "channels": [0,1,2,3,4,5,6,7], "description": "Drop tips"},
  {"step": 33, "action": "tips_on", "labware": "tips", "column": 6, "volume_ul": 0, "channels": [0,1,2,3,4,5,6,7], "description": "Pick up tip column 6 for mix and transfer 4 to 5"},
  {"step": 34, "action": "aspirate", "labware": "dilution_plate", "column": 4, "volume_ul": 50, "channels": [0,1,2,3,4,5,6,7], "description": "Mix column 4: aspirate 50 µL"},
  {"step": 35, "action": "dispense", "labware": "dilution_plate", "column": 4, "volume_ul": 50, "channels": [0,1,2,3,4,5,6,7], "description": "Mix column 4: dispense 50 µL back"},
  {"step": 36, "action": "aspirate", "labware": "dilution_plate", "column": 4, "volume_ul": 10, "channels": [0,1,2,3,4,5,6,7], "description": "Take 10 µL from column 4"},
  {"step": 37, "action": "dispense", "labware": "dilution_plate", "column": 5, "volume_ul": 10, "channels": [0,1,2,3,4,5,6,7], "description": "Transfer to column 5 (10^-5)"},
  {"step": 38, "action": "tips_off", "labware": "waste", "volume_ul": 0, "channels": [0,1,2,3,4,5,6,7], "description": "Drop tips"},
  {"step": 39, "action": "tips_on", "labware": "tips", "column": 7, "volume_ul": 0, "channels": [0,1,2,3,4,5,6,7], "description": "Pick up tip column 7 for mix and transfer 5 to 6"},
  {"step": 40, "action": "aspirate", "labware": "dilution_plate", "column": 5, "volume_ul": 50, "channels": [0,1,2,3,4,5,6,7], "description": "Mix column 5: aspirate 50 µL"},
  {"step": 41, "action": "dispense", "labware": "dilution_plate", "column": 5, "volume_ul": 50, "channels": [0,1,2,3,4,5,6,7], "description": "Mix column 5: dispense 50 µL back"},
  {"step": 42, "action": "aspirate", "labware": "dilution_plate", "column": 5, "volume_ul": 10, "channels": [0,1,2,3,4,5,6,7], "description": "Take 10 µL from column 5"},
  {"step": 43, "action": "dispense", "labware": "dilution_plate", "column": 6, "volume_ul": 10, "channels": [0,1,2,3,4,5,6,7], "description": "Transfer to column 6 (10^-6)"},
  {"step": 44, "action": "tips_off", "labware": "waste", "volume_ul": 0, "channels": [0,1,2,3,4,5,6,7], "description": "Drop tips"},
  {"step": 45, "action": "tips_on", "labware": "tips", "column": 8, "volume_ul": 0, "channels": [0,1,2,3,4,5,6,7], "description": "Pick up fresh tip column 8 to mix last column"},
  {"step": 46, "action": "aspirate", "labware": "dilution_plate", "column": 6, "volume_ul": 50, "channels": [0,1,2,3,4,5,6,7], "description": "Mix column 6: aspirate 50 µL"},
  {"step": 47, "action": "dispense", "labware": "dilution_plate", "column": 6, "volume_ul": 50, "channels": [0,1,2,3,4,5,6,7], "description": "Mix column 6: dispense 50 µL back"},
  {"step": 48, "action": "tips_off", "labware": "waste", "volume_ul": 0, "channels": [0,1,2,3,4,5,6,7], "description": "Drop tips"}
 ]
}
```