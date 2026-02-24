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
| `--spawn CMD` | Run command in ephemeral container and exit |
| `--worktree NAME` | Create a git worktree with its own container |
| `--worktree NAME --branch BRANCH` | Create worktree from existing branch |
| `--worktree NAME --remove` | Remove worktree and its container resources |
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
- Host network by default (for git/npm/pip access)
- Writable: `/tmp`, `/var/tmp`, `/run` (tmpfs), `/workspace` (bind mount), `/home/user` (volume)
- Containers have passwordless sudo (for installing packages at runtime)
- Optional restricted network mode (see [Network Policy](#network-policy))

All security settings are configurable in `[container.security]`.

### Network Policy

Set `network = "restricted"` in `[container.security]` and list allowed domains in `[container.network]`:

```toml
[container.security]
network = "restricted"

[container.network]
allowed_domains = ["github.com", "pypi.org", "npmjs.com", "claude.ai", "api.anthropic.com"]
```

Restricted mode uses `slirp4netns` instead of host networking. An iptables init script resolves each domain at startup and blocks all other outbound traffic. DNS queries are always allowed.

## Headless Spawns

Run a command in an ephemeral container (no TTY, auto-removed on exit):

```bash
nix-enter --spawn "claude -p 'fix the failing tests'"
```

Returns the command's exit code. Useful for scripted agent invocations, CI, or batch tasks. The Claude volume is shared with the main container so conversation history persists.

## Git Worktrees

Run multiple agents on the same repo in parallel using git worktrees:

```bash
nix-enter --worktree feature-auth                # new branch + container
nix-enter --worktree fix-bug --branch fix/bug-42  # existing branch
cd ../.nix-enter-worktrees/feature-auth && nix-enter  # enter the worktree container
nix-enter --worktree feature-auth --remove        # clean up everything
```

Each worktree gets its own directory under `../.nix-enter-worktrees/`, its own container, and its own volumes. The config and Containerfile are copied from the main project.

## Resource Limits

Optionally cap CPU, memory, and process count per container:

```toml
[container.resources]
cpu_limit = "2.0"       # CPU cores
memory_limit = "8g"     # memory limit
pids_limit = 1024       # max processes
```

Defaults to no limits. Useful for preventing a runaway agent from consuming all host resources.

## Shared Cache

Package manager caches (pip, npm, cargo) are shared across all nix-enter projects via a global volume (`nix-enter-cache-global`). Enabled by default:

```toml
[container.cache]
shared = true
```

Set `shared = false` to disable. Cache paths inside the container: `/cache/pip`, `/cache/npm`, `/cache/cargo`.

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

# [container.network]
# allowed_domains = ["github.com", "pypi.org", "npmjs.com", "claude.ai", "api.anthropic.com"]

# [container.resources]
# cpu_limit = "2.0"
# memory_limit = "8g"
# pids_limit = 1024

[container.cache]
shared = true

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
