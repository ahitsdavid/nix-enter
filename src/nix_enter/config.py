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
    # [container.network]
    allowed_domains: list[str] = field(default_factory=list)
    # [container.mounts]
    extra_mounts: list[str] = field(default_factory=list)
    # [container.forwarding]
    forward_ssh_agent: bool = True
    forward_gitconfig: bool = True
    forward_claude_config: bool = True
    forward_wayland: bool = True
    forward_x11: bool = True
    # [container.cache]
    shared_cache: bool = True
    # [container.resources]
    cpu_limit: str = ""
    memory_limit: str = ""
    pids_limit: int = 0
    # [logging]
    build_logs_keep: int = 5


DEFAULT_CONFIG = """\
# nix-enter project config
# See: https://github.com/ahitsdavid/nix-enter

[container]
user = "user"
containerfile = "Containerfile.dev"

[container.security]
read_only = true
cap_drop = "all"
no_new_privileges = true
network = "host"

# [container.network]
# allowed_domains = ["github.com", "pypi.org", "files.pythonhosted.org", "npmjs.com", "registry.npmjs.org", "crates.io", "static.crates.io", "registry.fedoraproject.org", "claude.ai", "api.anthropic.com", "statsig.anthropic.com"]

# [container.mounts]
# extra = ["/data:/data:ro"]

# [container.resources]
# cpu_limit = "2.0"
# memory_limit = "8g"
# pids_limit = 1024

[container.cache]
shared = true

[container.forwarding]
ssh_agent = true
gitconfig = true
claude_config = true
wayland = true
x11 = true

[logging]
build_logs_keep = 5
"""


def init_config(config_path: Path) -> None:
    """Create default config.toml and .gitignore if they don't exist."""
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(DEFAULT_CONFIG)
    gitignore = config_path.parent / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("logs/\nplugin-patches/\n")


def load_config(config_path: Path) -> Config:
    """Load config from TOML file, falling back to defaults for missing keys."""
    cfg = Config()
    if not config_path.exists():
        return cfg

    with open(config_path, "rb") as f:
        data = tomllib.load(f)

    container = data.get("container", {})
    security = container.get("security", {})
    network_cfg = container.get("network", {})
    mounts = container.get("mounts", {})
    cache = container.get("cache", {})
    resources = container.get("resources", {})
    forwarding = container.get("forwarding", {})
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
    if "allowed_domains" in network_cfg:
        cfg.allowed_domains = network_cfg["allowed_domains"]
    if "extra" in mounts:
        cfg.extra_mounts = mounts["extra"]
    if "shared" in cache:
        cfg.shared_cache = cache["shared"]
    if "cpu_limit" in resources:
        cfg.cpu_limit = resources["cpu_limit"]
    if "memory_limit" in resources:
        cfg.memory_limit = resources["memory_limit"]
    if "pids_limit" in resources:
        cfg.pids_limit = resources["pids_limit"]
    if "ssh_agent" in forwarding:
        cfg.forward_ssh_agent = forwarding["ssh_agent"]
    if "gitconfig" in forwarding:
        cfg.forward_gitconfig = forwarding["gitconfig"]
    if "claude_config" in forwarding:
        cfg.forward_claude_config = forwarding["claude_config"]
    if "wayland" in forwarding:
        cfg.forward_wayland = forwarding["wayland"]
    if "x11" in forwarding:
        cfg.forward_x11 = forwarding["x11"]
    if "build_logs_keep" in logging:
        cfg.build_logs_keep = logging["build_logs_keep"]

    return cfg
