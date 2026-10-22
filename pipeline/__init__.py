"""LLNL Capstone Pipeline: automated protocol execution in five stages.

Stage 1: Verifier   (declarative JSON → safety gate)
Stage 2: Compiler   (JSON → PyLabRobot code)
Stage 3: Simulator  (PLR code → ChatterBox dry run)
Stage 4: Visualizer (replay in PyLabRobot's browser visualizer)
Stage 5: Executor   (hardware execution, stub)
"""
