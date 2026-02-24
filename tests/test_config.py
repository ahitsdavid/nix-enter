from pathlib import Path
from nix_enter.config import Config, load_config, init_config


def test_default_config():
    cfg = Config()
    assert cfg.container_user == "user"
    assert cfg.containerfile == "Containerfile.dev"
    assert cfg.read_only is True
    assert cfg.cap_drop == "all"
    assert cfg.network == "host"
    assert cfg.build_logs_keep == 5
    assert cfg.session_logs_keep == 10
    assert cfg.session_log_limit_mb == 50
    assert cfg.extra_mounts == []


def test_load_config_missing_file(tmp_path):
    cfg = load_config(tmp_path / ".nix-enter" / "config.toml")
    assert cfg.container_user == "user"  # defaults


def test_load_config_partial_override(tmp_path):
    config_dir = tmp_path / ".nix-enter"
    config_dir.mkdir(parents=True)
    config_file = config_dir / "config.toml"
    config_file.write_text('[container]\nuser = "dev"\n')
    cfg = load_config(config_file)
    assert cfg.container_user == "dev"
    assert cfg.containerfile == "Containerfile.dev"  # default preserved


def test_load_config_extra_mounts(tmp_path):
    config_dir = tmp_path / ".nix-enter"
    config_dir.mkdir(parents=True)
    config_file = config_dir / "config.toml"
    config_file.write_text('[container.mounts]\nextra = ["/data:/data:ro"]\n')
    cfg = load_config(config_file)
    assert cfg.extra_mounts == ["/data:/data:ro"]


def test_init_config_creates_file(tmp_path):
    config_path = tmp_path / ".nix-enter" / "config.toml"
    init_config(config_path)
    assert config_path.exists()
    # Generated config should be valid TOML that loads with defaults
    cfg = load_config(config_path)
    assert cfg.container_user == "user"
    assert cfg.build_logs_keep == 5
