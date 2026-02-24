"""TOML config loading with defaults."""

from dataclasses import dataclass, field
from pathlib import Path
import tomllib


@dataclass
class Config:
    # [container]
    container_user: str = "user"
    containerfile: str = "Containerfile.dev"
    # [container.security]
    read_only: bool = True
    cap_drop: str = "all"
    no_new_privileges: bool = True
    network: str = "host"
    # [container.mounts]
    extra_mounts: list[str] = field(default_factory=list)
    # [logging]
    build_logs_keep: int = 5
    session_logs_keep: int = 10
    session_log_limit_mb: int = 50


def load_config(config_path: Path) -> Config:
    """Load config from TOML file, falling back to defaults for missing keys."""
    cfg = Config()
    if not config_path.exists():
        return cfg

    with open(config_path, "rb") as f:
        data = tomllib.load(f)

    container = data.get("container", {})
    security = container.get("security", {})
    mounts = container.get("mounts", {})
    logging = data.get("logging", {})

    if "user" in container:
        cfg.container_user = container["user"]
    if "containerfile" in container:
        cfg.containerfile = container["containerfile"]
    if "read_only" in security:
        cfg.read_only = security["read_only"]
    if "cap_drop" in security:
        cfg.cap_drop = security["cap_drop"]
    if "no_new_privileges" in security:
        cfg.no_new_privileges = security["no_new_privileges"]
    if "network" in security:
        cfg.network = security["network"]
    if "extra" in mounts:
        cfg.extra_mounts = mounts["extra"]
    if "build_logs_keep" in logging:
        cfg.build_logs_keep = logging["build_logs_keep"]
    if "session_logs_keep" in logging:
        cfg.session_logs_keep = logging["session_logs_keep"]
    if "session_log_limit_mb" in logging:
        cfg.session_log_limit_mb = logging["session_log_limit_mb"]

    return cfg
