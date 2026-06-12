"""Pytest configuration for the ATLAS project tests.

Forces a headless matplotlib backend and ensures both the project root and the
``src`` package directory are importable so tests can ``from src... import``.
"""

import os
import sys

# Headless plotting for figure tests.
os.environ.setdefault("MPLBACKEND", "Agg")

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "src")
for path in (ROOT, SRC):
    if path not in sys.path:
        sys.path.insert(0, path)
