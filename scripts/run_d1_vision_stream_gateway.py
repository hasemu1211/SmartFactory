#!/usr/bin/env python3
"""Compatibility wrapper for scripts/vision/run_d1_vision_stream_gateway.py."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def main() -> None:
    target = Path(__file__).resolve().parent / 'vision/run_d1_vision_stream_gateway.py'
    os.execv(sys.executable, [sys.executable, str(target), *sys.argv[1:]])


if __name__ == "__main__":
    main()
