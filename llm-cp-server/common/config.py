from __future__ import annotations

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_API_CORS_ORIGIN_REGEX = (
    r"^https?://(localhost|127\.0\.0\.1|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
    r"172\.(1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3}|"
    r"192\.168\.\d{1,3}\.\d{1,3})(:\d+)?$"
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "local-llm-cp"
    environment: str = "development"
    log_level: str = "INFO"
    database_url: str = "sqlite+aiosqlite:///./data/llm-cp.db"

    remote_mode: Literal["ssh", "local"] = "ssh"
    gpu_ssh_host: str = ""
    gpu_ssh_port: int = 22
    gpu_ssh_user: str = ""
    gpu_ssh_key_path: str = ""
    gpu_ssh_password: str = ""
    gpu_ssh_known_hosts: str = ""
    remote_state_dir: str = "~/.local/state/local-llm-cp"
    # GPU_SSH_PASSWORD is fed to its stdin for `sudo -S`; without one the SSH user
    # needs passwordless sudo on the GPU host.
    host_shutdown_command: str = "sudo -S -p '' shutdown -h now"

    # Comma-separated list; the regex covers private-network origins on any port.
    api_cors_origins: str = "http://localhost:5173"
    api_cors_origin_regex: str = DEFAULT_API_CORS_ORIGIN_REGEX

    status_poll_interval_seconds: float = 3.0
    # Host polling pauses this long after the last dashboard request. 0 polls all the time.
    dashboard_idle_seconds: float = 2.0
    stop_timeout_seconds: int = 10
    log_buffer_lines: int = 5000
    log_backlog_lines: int = 1000
    gpu_history_samples: int = 300
    gpu_process_interval_seconds: float = 3.0

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.api_cors_origins.split(",") if origin.strip()]


def load_settings() -> Settings:
    return Settings()
