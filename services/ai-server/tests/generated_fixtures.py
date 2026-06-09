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


def qr_png_bytes(payload: str = "TB3_DOCK_A", *, scale: int = 8, padding: int = 24) -> bytes:
    """Generate a deterministic QR fixture image entirely in test code."""

    encoder = cv2.QRCodeEncoder_create()
    qr = encoder.encode(payload)
    qr = cv2.resize(qr, None, fx=scale, fy=scale, interpolation=cv2.INTER_NEAREST)
    canvas = np.full(
        (qr.shape[0] + (padding * 2), qr.shape[1] + (padding * 2)),
        255,
        dtype=np.uint8,
    )
    canvas[padding : padding + qr.shape[0], padding : padding + qr.shape[1]] = qr
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
