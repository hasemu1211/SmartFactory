from __future__ import annotations

import cv2
import numpy as np


def png_bytes(image: np.ndarray) -> bytes:
    ok, encoded = cv2.imencode(".png", image)
    assert ok
    return encoded.tobytes()


def blank_png_bytes(*, width: int = 64, height: int = 64) -> bytes:
    return png_bytes(np.full((height, width, 3), 255, dtype=np.uint8))


def aruco_png_bytes(marker_id: int = 7, *, marker_size: int = 96, padding: int = 32) -> bytes:
    """Generate a deterministic ArUco fixture image entirely in test code."""

    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    marker = cv2.aruco.generateImageMarker(dictionary, marker_id, marker_size)
    canvas_size = marker_size + (padding * 2)
    canvas = np.full((canvas_size, canvas_size), 255, dtype=np.uint8)
    canvas[padding : padding + marker_size, padding : padding + marker_size] = marker
    return png_bytes(cv2.cvtColor(canvas, cv2.COLOR_GRAY2BGR))


def multi_aruco_png_bytes(marker_ids: tuple[int, int] = (4, 5)) -> bytes:
    """Generate a deterministic two-marker ArUco fixture with non-overlapping boxes."""

    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    canvas = np.full((160, 304), 255, dtype=np.uint8)
    for index, marker_id in enumerate(marker_ids):
        marker = cv2.aruco.generateImageMarker(dictionary, marker_id, 96)
        left = 32 + (index * 144)
        canvas[32:128, left : left + 96] = marker
    return png_bytes(cv2.cvtColor(canvas, cv2.COLOR_GRAY2BGR))
