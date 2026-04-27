"""
fuzz — anatomy extension fuzz corpus generator.

Deterministic HTML generator for stress-testing the auto-label cascade.
Entry point: fuzz.cli.cmd_fuzz (wired into atlas_triage_cli.py as `atl fuzz`).
"""
from fuzz.generator import generate_corpus
from fuzz.shapes import SHAPE_REGISTRY, Fragment

__all__ = ["generate_corpus", "SHAPE_REGISTRY", "Fragment"]
