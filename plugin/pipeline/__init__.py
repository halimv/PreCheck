"""LLNL Capstone Pipeline: automated protocol execution.

Stage 0: Drafter      (protocol PDF/text → JSON IR with labware needs, by the Claude CLI)
Stage 0b: Deck builder (labware needs → real labware from VENUS's library and the deck on the STARlet;
                        needs nothing fits go back to Claude)
Stage 1: Verifier     (declarative JSON → safety gate; out of the self-healing loop for now)
Stage 2: Compiler   (JSON → PyLabRobot code)
Stage 3: Simulator  (PLR code → ChatterBox dry run)
Stage 4: Visualizer (replay in PyLabRobot's browser visualizer)
Stage 5: Executor   (Hamilton STARlet via STARBackend, after the deck setup checklist)
"""
