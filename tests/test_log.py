from pathlib import Path
from nix_enter.log import init_logging, log_event, rotate_logs


def test_init_logging_creates_dirs(tmp_path):
    log_dir = init_logging(tmp_path)
    assert log_dir.exists()
    assert log_dir == tmp_path / ".nix-enter" / "logs"


def test_log_event_appends(tmp_path):
    log_dir = init_logging(tmp_path)
    log_event(log_dir, "TEST event one")
    log_event(log_dir, "TEST event two")
    lifecycle = log_dir / "lifecycle.log"
    assert lifecycle.exists()
    lines = lifecycle.read_text().strip().split("
")
    assert len(lines) == 2
    assert "TEST event one" in lines[0]
    assert "TEST event two" in lines[1]


def test_log_event_has_timestamp(tmp_path):
    log_dir = init_logging(tmp_path)
    log_event(log_dir, "TEST event")
    content = (log_dir / "lifecycle.log").read_text()
    assert content.startswith("[2")


def test_lifecycle_rotation(tmp_path):
    log_dir = init_logging(tmp_path)
    lifecycle = log_dir / "lifecycle.log"
    lifecycle.write_text("x" * (1024 * 1024 + 1))
    log_event(log_dir, "AFTER rotation")
    assert (log_dir / "lifecycle.log.old").exists()
    content = lifecycle.read_text()
    assert "AFTER rotation" in content


def test_rotate_logs_keeps_n(tmp_path):
    log_dir = init_logging(tmp_path)
    for i in range(8):
        (log_dir / f"build-2026-02-{i:02d}T120000.log").write_text(f"build {i}")
    rotate_logs(log_dir, "build-", keep=3)
    remaining = sorted(log_dir.glob("build-*.log"))
    assert len(remaining) == 3
