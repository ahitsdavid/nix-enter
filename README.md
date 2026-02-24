# nix-enter

Hardened per-project podman containers for AI coding agents. Drop into any project directory, get an isolated container with your code mounted at `/workspace`.

Not a general-purpose dev shell — purpose-built for running Claude Code (or similar) in a locked-down environment.

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

## Usage

```bash
cd ~/projects/myapp
nix-enter                # build image, create container, attach
```

First run auto-generates a `Containerfile.dev` with Fedora, basic dev tools, and Claude Code. Edit it to add project-specific dependencies, then `nix-enter --rebuild`.

## CLI

| Flag | Action |
|------|--------|
| *(none)* | Build/create/attach |
| `--rebuild` | Rebuild image, recreate container |
| `--force` | Recreate container (keep image) |
| `--clean` | Remove container + home volume |
| `--clean --all` | Remove everything including credentials |
| `--list` | Show all nix-enter projects |
| `--purge` | Remove orphaned resources |
| `--status` | Show project resource state |
| `--verbose` | Verbose output |

## Security

- Read-only root filesystem
- All capabilities dropped (`--cap-drop=all`)
- No privilege escalation (`no-new-privileges`)
- User namespace mapping (`--userns=keep-id`)
- Host network (for git/npm/pip access)
- Writable: `/tmp`, `/var/tmp`, `/run` (tmpfs), `/workspace` (bind mount), `/home/user` (volume)

## Config

Optional `.nix-enter/config.toml` in your project root:

```toml
[container]
user = "user"
containerfile = "Containerfile.dev"

[container.security]
read_only = true
cap_drop = "all"
network = "host"

[logging]
build_logs_keep = 5
session_logs_keep = 10
```

All fields have defaults — the file is optional.

## License

MIT
