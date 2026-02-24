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


def test_default_forwarding():
    cfg = Config()
    assert cfg.forward_ssh_agent is True
    assert cfg.forward_gitconfig is True
    assert cfg.forward_claude_config is True
    assert cfg.forward_wayland is True
    assert cfg.forward_x11 is True


def test_load_config_forwarding_override(tmp_path):
    config_dir = tmp_path / ".nix-enter"
    config_dir.mkdir(parents=True)
    config_file = config_dir / "config.toml"
    config_file.write_text(
        '[container.forwarding]\ngitconfig = false\nclaude_config = false\n'
    )
    cfg = load_config(config_file)
    assert cfg.forward_gitconfig is False
    assert cfg.forward_claude_config is False
    assert cfg.forward_ssh_agent is True  # default preserved


def test_default_resource_limits():
    cfg = Config()
    assert cfg.cpu_limit == ""
    assert cfg.memory_limit == ""
    assert cfg.pids_limit == 0


def test_load_config_resource_limits(tmp_path):
    config_dir = tmp_path / ".nix-enter"
    config_dir.mkdir(parents=True)
    config_file = config_dir / "config.toml"
    config_file.write_text(
        '[container.resources]\ncpu_limit = "2.0"\nmemory_limit = "8g"\npids_limit = 1024\n'
    )
    cfg = load_config(config_file)
    assert cfg.cpu_limit == "2.0"
    assert cfg.memory_limit == "8g"
    assert cfg.pids_limit == 1024


def test_load_config_no_resources_keeps_defaults(tmp_path):
    config_dir = tmp_path / ".nix-enter"
    config_dir.mkdir(parents=True)
    config_file = config_dir / "config.toml"
    config_file.write_text('[container]\nuser = "dev"\n')
    cfg = load_config(config_file)
    assert cfg.cpu_limit == ""
    assert cfg.memory_limit == ""
    assert cfg.pids_limit == 0


def test_default_shared_cache():
    cfg = Config()
    assert cfg.shared_cache is True


def test_load_config_shared_cache_false(tmp_path):
    config_dir = tmp_path / ".nix-enter"
    config_dir.mkdir(parents=True)
    config_file = config_dir / "config.toml"
    config_file.write_text('[container.cache]\nshared = false\n')
    cfg = load_config(config_file)
    assert cfg.shared_cache is False


def test_load_config_no_cache_section_keeps_default(tmp_path):
    config_dir = tmp_path / ".nix-enter"
    config_dir.mkdir(parents=True)
    config_file = config_dir / "config.toml"
    config_file.write_text('[container]\nuser = "dev"\n')
    cfg = load_config(config_file)
    assert cfg.shared_cache is True


def test_init_config_creates_file(tmp_path):
    config_path = tmp_path / ".nix-enter" / "config.toml"
    init_config(config_path)
    assert config_path.exists()
    # Generated config should be valid TOML that loads with defaults
    cfg = load_config(config_path)
    assert cfg.container_user == "user"
    assert cfg.build_logs_keep == 5


def test_init_config_creates_gitignore(tmp_path):
    config_path = tmp_path / ".nix-enter" / "config.toml"
    init_config(config_path)
    gitignore = tmp_path / ".nix-enter" / ".gitignore"
    assert gitignore.exists()
    assert "logs/" in gitignore.read_text()


def test_default_allowed_domains():
    cfg = Config()
    assert cfg.allowed_domains == []


def test_load_config_allowed_domains(tmp_path):
    config_dir = tmp_path / ".nix-enter"
    config_dir.mkdir(parents=True)
    config_file = config_dir / "config.toml"
    config_file.write_text(
        '[container.network]\n'
        'allowed_domains = ["github.com", "pypi.org"]\n'
    )
    cfg = load_config(config_file)
    assert cfg.allowed_domains == ["github.com", "pypi.org"]


def test_load_config_no_network_section_keeps_default(tmp_path):
    config_dir = tmp_path / ".nix-enter"
    config_dir.mkdir(parents=True)
    config_file = config_dir / "config.toml"
    config_file.write_text('[container]\nuser = "dev"\n')
    cfg = load_config(config_file)
    assert cfg.allowed_domains == []
