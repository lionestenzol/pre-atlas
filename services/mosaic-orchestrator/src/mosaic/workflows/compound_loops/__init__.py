"""Cross-agent compound feedback loops.

Each loop is a pure function: CompoundSnapshot -> LoopResult.
No side effects, no I/O. Orchestration and write-back happen in compound_loop.py.
"""
