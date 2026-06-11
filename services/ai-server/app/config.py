from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


SERVICE_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVICE_DIR.parents[1]


class Settings(BaseSettings):
    """Runtime configuration for the API-first AI Server."""

    model_config = SettingsConfigDict(
        env_file=(SERVICE_DIR / ".env.local", SERVICE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ai_server_host: str = "127.0.0.1"
    ai_server_port: int = 8100
    main_server_url: str = "http://127.0.0.1:8000"
    camera_sources: str = "global_cam_01,tb3_1_picam,tb3_2_picam"
    ros_image_topics: str = "/global_camera/image_raw,/tb3_1/pi_camera/image_raw,/tb3_2/pi_camera/image_raw"
    vision_event_schema_version: str = "vision-event.v1"
    model_name: str = "opencv-marker-detector"
    policy_version: str = "mvp1"
    wms_emit_enabled: bool = False
    wms_emit_timeout_s: float = 2.0
    wms_emit_retries: int = 0
    wms_vision_events_path: str = "/api/v1/vision/events"
    source_target_fps: float = 10.0
    source_stale_after_s: float = 2.0
    source_offline_after_s: float = 30.0
    contract_schema_path: Path = Field(
        default=REPO_ROOT / "docs" / "contracts" / "vision-event.schema.json"
    )
    aruco_pose_profiles_path: Path = Field(
        default=REPO_ROOT / "config" / "perception" / "aruco_pose_profiles.example.json"
    )

    @property
    def source_ids(self) -> list[str]:
        return [part.strip() for part in self.camera_sources.split(",") if part.strip()]

    @property
    def image_topics(self) -> list[str]:
        return [part.strip() for part in self.ros_image_topics.split(",") if part.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
