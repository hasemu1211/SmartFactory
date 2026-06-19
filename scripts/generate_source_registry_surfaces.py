#!/usr/bin/env python3
"""Compatibility wrapper for scripts/generate/generate_source_registry_surfaces.py."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def main() -> None:
    target = Path(__file__).resolve().parent / 'generate/generate_source_registry_surfaces.py'
    os.execv(sys.executable, [sys.executable, str(target), *sys.argv[1:]])


if __name__ == "__main__":
    main()
