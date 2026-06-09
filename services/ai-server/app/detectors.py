from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np


ARUCO_DICTIONARY_NAME = "DICT_4X4_50"


@dataclass(frozen=True)
class MarkerDetection:
    """Deterministic marker detection result in image pixel coordinates."""

    marker_id: str
    bbox_xyxy: list[float]
    center_xy: tuple[float, float]
    corners_xy: list[list[float]]
    dictionary: str = ARUCO_DICTIONARY_NAME
    confidence: float = 1.0


def decode_image(payload: bytes) -> np.ndarray | None:
    """Decode uploaded image bytes into an OpenCV BGR image."""

    if not payload:
        return None
    encoded = np.frombuffer(payload, dtype=np.uint8)
    image = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
    return image


def _aruco_detector() -> Any:
    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    parameters = cv2.aruco.DetectorParameters()
    if hasattr(cv2.aruco, "ArucoDetector"):
        return cv2.aruco.ArucoDetector(aruco_dict, parameters)
    return aruco_dict, parameters


def detect_aruco_markers(image: np.ndarray) -> list[MarkerDetection]:
    """Detect DICT_4X4_50 ArUco markers without ROS2/runtime side effects.

    Results are sorted by numeric marker ID and then bbox origin so API responses
    remain stable for generated fixtures and repeated uploads.
    """

    detector = _aruco_detector()
    if hasattr(detector, "detectMarkers"):
        corners, ids, _ = detector.detectMarkers(image)
    else:
        aruco_dict, parameters = detector
        corners, ids, _ = cv2.aruco.detectMarkers(image, aruco_dict, parameters=parameters)

    if ids is None:
        return []

    detections: list[MarkerDetection] = []
    for marker_id, marker_corners in zip(ids.flatten().tolist(), corners, strict=True):
        points = np.asarray(marker_corners, dtype=np.float32).reshape(4, 2)
        x_min = float(points[:, 0].min())
        y_min = float(points[:, 1].min())
        x_max = float(points[:, 0].max())
        y_max = float(points[:, 1].max())
        center = (float(points[:, 0].mean()), float(points[:, 1].mean()))
        detections.append(
            MarkerDetection(
                marker_id=str(int(marker_id)),
                bbox_xyxy=[x_min, y_min, x_max, y_max],
                center_xy=center,
                corners_xy=[[float(x), float(y)] for x, y in points.tolist()],
            )
        )

    return sorted(
        detections,
        key=lambda item: (int(item.marker_id), item.bbox_xyxy[1], item.bbox_xyxy[0]),
    )
