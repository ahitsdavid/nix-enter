# nix-enter User Guide

## What is nix-enter?

nix-enter creates isolated Podman containers for Claude Code. Each project gets its own container with:

- Your project code mounted at `/workspace`
- A persistent home directory (survives container recreation)
- Claude Code pre-installed with native auto-updates
- Your host SSH keys, git config, and Claude settings forwarded in
- A hardened security profile (read-only root, no capabilities, no privilege escalation)

The container is Fedora-based with language-specific dev tools auto-detected from your project.

## Getting Started

### Prerequisites

- NixOS with flakes enabled
- Podman installed and configured for rootless use
- An SSH agent running (for git operations inside the container)

### Installation

Add nix-enter to your NixOS flake:

```nix
# flake.nix
{
  inputs.nix-enter = {
    url = "github:ahitsdavid/nix-enter";
    inputs.nixpkgs.follows = "nixpkgs";
  };

  # In your system configuration module:
  environment.systemPackages = [
    inputs.nix-enter.packages.${pkgs.system}.default
  ];
}
```

Rebuild your system:

```bash
sudo nixos-rebuild switch --flake .#hostname
```

### First Project

```bash
cd ~/projects/myapp
nix-enter --init
```

This creates `.nix-enter/config.toml` with default settings and a `.gitignore` for generated files. Review the config, then:

```bash
nix-enter
```

On first run, nix-enter will:

1. Generate a `Containerfile.dev` based on your project language
2. Build the container image (Fedora + dev tools + Claude Code)
3. Create the container with all mounts and security settings
4. Attach you to the container shell

Subsequent runs skip steps 1-3 and just attach to the existing container.

## Daily Workflow

### Enter your project container

```bash
cd ~/projects/myapp
nix-enter
```

If the container is stopped, it starts and attaches. If it's running, it attaches directly. If it doesn't exist yet, it builds everything from scratch.

### Work inside the container

Once attached, you're in `/workspace` with your project files:

```bash
[user@myapp workspace]$ claude    # run Claude Code
[user@myapp workspace]$ git push  # uses forwarded SSH agent
[user@myapp workspace]$ exit      # detach from container
```

The container stays around after you exit. Next time you run `nix-enter`, it re-attaches instantly.

### Update your Containerfile

Edit `Containerfile.dev` to add project-specific dependencies:

```dockerfile
FROM registry.fedoraproject.org/fedora:latest

RUN dnf install -y --skip-unavailable \
    git curl wget \
    gcc gcc-c++ make cmake ninja-build \
    qt6-qtbase-devel \
    qt6-qtwayland \
    procps-ng \
  && dnf clean all

ARG USER_NAME=user
ARG USER_UID=1000
RUN useradd -m -u "$USER_UID" -s /bin/bash "$USER_NAME"
USER $USER_NAME

RUN curl -fsSL https://claude.ai/install.sh | sh
ENV PATH="/home/user/.claude/local/bin:${PATH}"

WORKDIR /workspace
CMD ["/bin/bash"]
```

Then rebuild:

```bash
nix-enter --rebuild
```

This removes the old container, rebuilds the image, creates a new container, and attaches. Your home volume (installed tools, shell history, Claude state) persists across rebuilds.

### Force recreate without rebuilding

If you just need a fresh container but the image is fine:

```bash
nix-enter --force
```

This removes and recreates the container with the existing image. Faster than `--rebuild`.

## Headless Agent Runs

Use `--spawn` to run a command in an ephemeral container without a TTY:

```bash
nix-enter --spawn "claude -p 'write tests for the auth module'"
```

The container is created with `--rm` (auto-removed on exit) and no persistent home volume. The Claude volume is still mounted, so conversation history carries over. The exit code from the spawned command is returned to the caller.

Use cases:
- Scripted agent invocations (CI, cron, batch processing)
- Running multiple agents in parallel (each `--spawn` gets its own container)
- Fire-and-forget tasks where you don't need an interactive shell

```bash
# Run and check exit code
nix-enter --spawn "claude -p 'fix lint errors'" && echo "Success" || echo "Failed"
```

## Git Worktrees

Work on multiple branches simultaneously, each with its own isolated container:

```bash
# Create a worktree with a new branch
nix-enter --worktree feature-auth

# Create from an existing branch
nix-enter --worktree fix-bug --branch fix/bug-42

# Enter the worktree's container
cd ../.nix-enter-worktrees/feature-auth
nix-enter

# Clean up worktree + container + volumes
nix-enter --worktree feature-auth --remove
```

Worktrees are created under `../.nix-enter-worktrees/` (sibling to the project's parent directory). The main project's `config.toml` and `Containerfile.dev` are copied into each worktree.

Each worktree gets its own container and volumes, so agents in different worktrees are fully isolated from each other.

## Configuration

### Config file

`.nix-enter/config.toml` controls all container behavior. Created by `--init`.

#### Container settings

```toml
[container]
user = "user"                    # username inside container
containerfile = "Containerfile.dev"  # which Containerfile to use
```

#### Security settings

```toml
[container.security]
read_only = true          # read-only root filesystem
cap_drop = "all"          # drop all Linux capabilities
no_new_privileges = true  # prevent privilege escalation
network = "host"          # network mode: "host" or "restricted"
```

Setting `read_only = false` gives the container a writable root filesystem. Setting `cap_drop = "none"` keeps all capabilities. These weaken security -- only change them if you know what you're doing.

All containers include passwordless sudo, so you can install packages at runtime without rebuilding the image.

#### Network policy

```toml
[container.security]
network = "restricted"

[container.network]
allowed_domains = ["github.com", "pypi.org", "files.pythonhosted.org", "npmjs.com", "registry.npmjs.org", "claude.ai", "api.anthropic.com", "statsig.anthropic.com"]
```

In restricted mode, the container uses `slirp4netns` networking instead of host networking. An iptables init script resolves each allowed domain at container startup and drops all other outbound traffic. DNS queries are always permitted.

This is useful for locking down agent network access to only the services it needs.

#### Resource limits

```toml
[container.resources]
cpu_limit = "2.0"       # max CPU cores (e.g. "0.5", "2.0")
memory_limit = "8g"     # max memory (e.g. "512m", "8g")
pids_limit = 1024       # max number of processes
```

All fields are optional. Defaults to no limits. Prevents a runaway agent from consuming all host resources.

#### Shared package cache

```toml
[container.cache]
shared = true   # share pip/npm/cargo cache across projects (default: true)
```

When enabled, a global volume (`nix-enter-cache-global`) is mounted at `/cache` with subdirectories for pip, npm, and cargo. This means downloading a package once makes it available in all your project containers.

Set `shared = false` to disable.

#### Extra mounts

```toml
[container.mounts]
extra = [
  "/data:/data:ro",
  "/home/user/.aws:/home/user/.aws:ro",
]
```

Mount additional host paths into the container. Format: `host_path:container_path:mode`.

#### Host forwarding

```toml
[container.forwarding]
ssh_agent = true       # forward SSH_AUTH_SOCK
gitconfig = true       # mount git config (auto-detects path)
claude_config = true   # mount Claude credentials, settings, plugins, skills
wayland = true         # forward Wayland display socket
x11 = true             # forward X11 display
```

Set any to `false` to disable that forwarding. Useful if you don't want certain host configs leaking into the container, or if auto-detection is causing issues.

#### Logging

```toml
[logging]
build_logs_keep = 5   # number of build logs to keep
```

### Git config detection

nix-enter checks two locations for git config:

1. `~/.gitconfig` (traditional)
2. `~/.config/git/config` (XDG, used by home-manager on NixOS)

Symlinks are resolved (home-manager creates symlinks to `/nix/store/`), so the actual file content is mounted into the container. If neither location exists, a warning is shown.

### Claude Code forwarding

When `claude_config = true`, the following are mounted read-only from `~/.claude/`:

| File/Directory | Purpose |
|---------------|---------|
| `.credentials.json` | Authentication |
| `settings.json` | Global settings |
| `settings.local.json` | Local settings |
| `CLAUDE.md` | Global instructions |
| `skills/` | User-defined skills |
| `plugins/` | Installed plugins + cache |

These are mounted on top of the persistent Claude volume, so the container can still write its own session data (history, logs, todos) while inheriting your host configuration.

**Plugin path patching**: Plugin metadata files contain absolute paths with your host username. When the container username differs (default: `user` vs your host username), nix-enter automatically generates patched copies with corrected paths. These patches are stored in `.nix-enter/plugin-patches/` (gitignored).

### GUI forwarding

nix-enter can forward Wayland or X11 displays into the container, allowing GUI applications to render on your host desktop. This is automatic when the display server is detected.

For Qt applications, add `qt6-qtwayland` to your Containerfile:

```dockerfile
RUN dnf install -y qt6-qtbase-devel qt6-qtwayland
```

For GTK applications, the Wayland socket forwarding is usually sufficient without extra packages.

## Managing Projects

### Check project status

```bash
nix-enter --status
```

Shows the state of the container, image, and volumes for the current project.

### List all projects

```bash
nix-enter --list
```

Shows all nix-enter projects system-wide, including their containers, volumes, and images. Projects whose directory has been deleted are marked as `MISSING`.

### Clean up a project

```bash
nix-enter --clean         # remove container + home volume
nix-enter --clean --all   # also remove Claude volume (credentials, history)
```

Both prompt for confirmation. The image is kept (shared across rebuilds).

### Purge orphaned resources

```bash
nix-enter --purge
```

Finds containers, volumes, and images from deleted project directories and removes them after confirmation.

## Build Logs

Build output is tee'd to both the terminal and a log file in `.nix-enter/logs/`:

```
.nix-enter/logs/
├── lifecycle.log                    # container events (append-only, rotates at 1MB)
├── build-2026-02-23T143022.log      # full build output
└── build-2026-02-22T091500.log
```

Old build logs are automatically cleaned up (default: keep last 5).

## Persistent Data

Each project has two named Podman volumes:

| Volume | Contents | Survives |
|--------|----------|----------|
| Home (`nix-enter-home-*`) | Shell history, installed tools, dotfiles | `--rebuild`, `--force` |
| Claude (`nix-enter-claude-*`) | Claude conversation history, todos, session data | `--rebuild`, `--force`, `--clean` |

The Claude volume is only removed with `--clean --all`.

## Troubleshooting

### Container dies after every command

Make sure you're running the latest version of nix-enter. The attach mechanism uses `podman start -ai` which handles TTY correctly. If you updated the flake input, rebuild NixOS to get the new binary.

### Git not configured inside container

nix-enter mounts your host git config read-only. On NixOS with home-manager, git config lives at `~/.config/git/config` (not `~/.gitconfig`). nix-enter checks both locations and resolves symlinks. Run with `--verbose` to see which path was detected.

If git config still isn't working, check that the file exists on your host:

```bash
ls -la ~/.gitconfig ~/.config/git/config
```

### SSH not working inside container

The SSH agent socket (`SSH_AUTH_SOCK`) must be set on the host. Check:

```bash
echo $SSH_AUTH_SOCK
ssh-add -l
```

If empty, start your SSH agent before running nix-enter.

### Claude Code plugins not loading

Plugin metadata contains absolute paths with your host username. nix-enter patches these automatically, but if plugins still fail, check with `--verbose` to see if the patching is happening. You can also try setting `container_user` to match your host username:

```toml
[container]
user = "davidthach"   # match your host username
```

### Old Claude Code version in container

The default templates use the native installer (`curl -fsSL https://claude.ai/install.sh | sh`) which installs to `~/.claude/local/bin/` on the persistent home volume. Claude Code self-updates on this path. If you're seeing an old version, it may be from an old `Containerfile.dev` that used npm. Update your Containerfile and `--rebuild`.

### Build cache not working

If builds are slow because the cache isn't being reused, make sure you haven't changed early layers in your Containerfile. Podman invalidates the cache from the first changed layer onward. Put frequently-changing instructions (like `COPY` or custom tool installs) at the end.

### Wayland/X11 GUI not working

Run with `--verbose` to check if the display socket was detected. For Wayland, both `WAYLAND_DISPLAY` and `XDG_RUNTIME_DIR` must be set on the host. For X11, `DISPLAY` must be set and `/tmp/.X11-unix` must exist.

For Qt apps, install `qt6-qtwayland` in your Containerfile. For GTK apps, Wayland support is usually built-in.

### Restricted network mode blocks everything

The iptables rules are built by resolving domain names at container startup. If DNS is slow or a domain fails to resolve, it won't be reachable. Check the allowed_domains list includes all necessary domains (don't forget CDN subdomains like `files.pythonhosted.org` for PyPI).

### --spawn command hangs

`--spawn` runs without a TTY. If the command you're running expects interactive input, it will hang. Make sure the command runs non-interactively (e.g., `claude -p '...'` not just `claude`).
