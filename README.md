# nix-enter

Hardened per-project podman containers for AI coding agents. Drop into any project directory, get an isolated container with your code mounted at `/workspace`.

Not a general-purpose dev shell -- purpose-built for running Claude Code in a locked-down environment.

## Install

Add to your NixOS flake:

```nix
# flake.nix inputs
inputs.nix-enter = {
  url = "github:ahitsdavid/nix-enter";
  inputs.nixpkgs.follows = "nixpkgs";
};

# In a module
environment.systemPackages = [
  inputs.nix-enter.packages.${pkgs.system}.default
];
```

Requires `podman` on the host.

## Quick Start

```bash
cd ~/projects/myapp
nix-enter --init      # create .nix-enter/config.toml
nix-enter             # build image, create container, attach
```

First run auto-generates a `Containerfile.dev` with Fedora, dev tools, and Claude Code (native installer). Edit it to add project-specific dependencies, then `nix-enter --rebuild`.

## CLI

| Flag | Action |
|------|--------|
| `--init` | Initialize project (required before first run) |
| *(none)* | Build/create/attach |
| `--rebuild` | Rebuild image and recreate container |
| `--force` | Recreate container (keep image) |
| `--status` | Show container/image/volume state |
| `--clean` | Remove container + home volume |
| `--clean --all` | Remove everything including claude volume |
| `--list` | Show all nix-enter projects system-wide |
| `--purge` | Remove orphaned resources (deleted project dirs) |
| `--verbose` | Verbose output |
| `--help` | Show help |

## Host Forwarding

nix-enter automatically detects and forwards host resources into the container. All forwarding is configurable via `[container.forwarding]` in config.

| Resource | What | Behavior when missing |
|----------|------|-----------------------|
| SSH agent | `SSH_AUTH_SOCK` socket | Warns (git push/pull won't work) |
| Git config | `~/.gitconfig` or `~/.config/git/config` | Warns (git unconfigured) |
| Claude Code | `~/.claude/` (credentials, settings, plugins, skills) | Warns |
| Wayland | `$WAYLAND_DISPLAY` socket | Silent skip |
| X11 | `$DISPLAY` + `/tmp/.X11-unix` | Silent skip |

Plugin path references are automatically patched when the container username differs from the host username.

## Language Detection

When no `Containerfile.dev` exists, one is generated based on project files:

| Marker file | Language | Extra packages |
|-------------|----------|----------------|
| `pyproject.toml`, `requirements.txt`, `setup.py` | Python | python3-devel, python3-pip |
| `package.json` | Node | nodejs, npm |
| `Cargo.toml` | Rust | rustup |
| `go.mod` | Go | golang |
| *(none)* | Base | git, curl, gcc, make |

All templates include Claude Code via the native installer (`curl -fsSL https://claude.ai/install.sh | sh`), which self-updates and persists on the home volume.

## Security

- Read-only root filesystem (`--read-only`)
- All capabilities dropped (`--cap-drop=all`)
- No privilege escalation (`--security-opt no-new-privileges`)
- User namespace mapping (`--userns=keep-id`)
- Host network (for git/npm/pip access)
- Writable: `/tmp`, `/var/tmp`, `/run` (tmpfs), `/workspace` (bind mount), `/home/user` (volume)

All security settings are configurable in `[container.security]`.

## Config

`.nix-enter/config.toml` (created by `--init`):

```toml
[container]
user = "user"
containerfile = "Containerfile.dev"

[container.security]
read_only = true
cap_drop = "all"
no_new_privileges = true
network = "host"

# [container.mounts]
# extra = ["/data:/data:ro"]

[container.forwarding]
ssh_agent = true
gitconfig = true
claude_config = true
wayland = true
x11 = true

[logging]
build_logs_keep = 5
```

## Logging

Logs are stored in `.nix-enter/logs/` (gitignored automatically):

- `lifecycle.log` -- timestamped container events (create, attach, remove, build). Rotates at 1MB.
- `build-*.log` -- full podman build output (tee'd to terminal + file). Keeps last 5 by default.

## Project Structure

```
myproject/
├── .nix-enter/
│   ├── config.toml          # project config
│   ├── .gitignore            # ignores logs/ and plugin-patches/
│   ├── logs/
│   │   ├── lifecycle.log
│   │   └── build-2026-02-23T143022.log
│   └── plugin-patches/       # auto-generated patched plugin metadata
├── Containerfile.dev          # auto-generated or custom
└── src/...
```

## Resource Naming

All resources include a hash of the project directory path for uniqueness:

| Resource | Pattern |
|----------|---------|
| Container | `nix-enter-{name}-{hash}` |
| Image | `nix-enter-{name}-{hash}:latest` |
| Home volume | `nix-enter-home-{name}-{hash}` |
| Claude volume | `nix-enter-claude-{name}-{hash}` |

Labels (`nix-enter.managed`, `nix-enter.project-dir`, etc.) are applied to all resources for `--list` and `--purge`.

## License

MIT
