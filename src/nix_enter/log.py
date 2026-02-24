"""Logging -- lifecycle events, build logs, session log rotation."""

from datetime import datetime, timezone
from pathlib import Path


def init_logging(project_dir: Path) -> Path:
    log_dir = project_dir / ".nix-enter" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def log_event(log_dir: Path, message: str) -> None:
    lifecycle = log_dir / "lifecycle.log"
    timestamp = datetime.now(timezone.utc).isoformat()
    with open(lifecycle, "a") as f:
        f.write(f"[{timestamp}] {message}
")
    if lifecycle.stat().st_size > 1_048_576:
        old = log_dir / "lifecycle.log.old"
        lifecycle.rename(old)
        with open(lifecycle, "a") as f:
            f.write(f"[{timestamp}] LOG rotated (previous in lifecycle.log.old)
")


def rotate_logs(log_dir: Path, prefix: str, keep: int) -> None:
    logs = sorted(log_dir.glob(f"{prefix}*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old_log in logs[keep:]:
        old_log.unlink()


def build_log_path(log_dir: Path) -> Path:
    ts = datetime.now().strftime("%Y-%m-%dT%H%M%S")
    return log_dir / f"build-{ts}.log"


def session_log_path(log_dir: Path) -> Path:
    ts = datetime.now().strftime("%Y-%m-%dT%H%M%S")
    return log_dir / f"session-{ts}.log"
