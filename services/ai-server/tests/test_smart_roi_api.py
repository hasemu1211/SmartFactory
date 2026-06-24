from __future__ import annotations

from api_test_helpers import client, cv2, main_module, np


def _jpg_bytes(image: np.ndarray) -> bytes:
    ok, buffer = cv2.imencode(".jpg", image)
    assert ok
    return buffer.tobytes()


def test_global_cam_process_generates_lift_roi_overlay_view():
    main_module.store.reset()
    main_module.source_health.reset()
    main_module.metrics.reset()
    main_module.frame_store.reset()
    main_module.overlay_cache.reset()
    with main_module._overlay_images_lock:
        main_module._overlay_images.clear()

    image = np.full((720, 1280, 3), 210, dtype=np.uint8)
    image[280:420, 500:780] = 45

    response = client.post(
        "/api/v1/vision/frame/process",
        data={"source": "global_cam_01", "force": "true"},
        files={"image": ("gopro.jpg", _jpg_bytes(image), "image/jpeg")},
    )

    assert response.status_code == 200
    latest = client.get(
        "/api/v1/vision/overlay/latest",
        params={"source": "global_cam_01", "view": "lift_roi"},
    )
    assert latest.status_code == 200
    overlay = latest.json()["overlay"]
    assert overlay["view"] == "lift_roi"
    assert overlay["frame_seq"] == response.json()["frame_seq"]
    assert overlay["image"]["width"] < 1280
    assert overlay["image"]["height"] < 720

    image_response = client.get(
        "/api/v1/vision/overlay/latest/image",
        params={"source": "global_cam_01", "view": "lift_roi"},
    )
    assert image_response.status_code == 200
    assert image_response.content.startswith(b"\xff\xd8")
