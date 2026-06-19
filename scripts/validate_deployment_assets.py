#!/usr/bin/env python3
"""Compatibility wrapper for scripts/validate/validate_deployment_assets.py."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def main() -> None:
    target = Path(__file__).resolve().parent / 'validate/validate_deployment_assets.py'
    os.execv(sys.executable, [sys.executable, str(target), *sys.argv[1:]])


if __name__ == "__main__":
    main()
