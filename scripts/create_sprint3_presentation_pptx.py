#!/usr/bin/env python3
"""Compatibility wrapper for scripts/reports/create_sprint3_presentation_pptx.py."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def main() -> None:
    target = Path(__file__).resolve().parent / 'reports/create_sprint3_presentation_pptx.py'
    os.execv(sys.executable, [sys.executable, str(target), *sys.argv[1:]])


if __name__ == "__main__":
    main()
