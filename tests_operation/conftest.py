"""Isolated operation tests (A10). No real database, no containers, no network.

Run with:  .venv/bin/pytest tests_operation -q
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
for p in (str(SCRIPTS), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)
