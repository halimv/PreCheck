"""LLNL Capstone Pipeline: 4-stage automated protocol execution.

Stage 1: Verifier (declarative JSON → safety gate)
Stage 2: Compiler (JSON → PyLabRobot code)
Stage 3: Simulator (PLR code → ChatterBox dry run)
Stage 4: Executor (hardware execution)
"""
