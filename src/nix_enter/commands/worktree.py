"""--worktree: create/remove git worktrees with isolated containers."""

import subprocess
from pathlib import Path

from nix_enter.project import Project
from nix_enter.podman import Podman
from nix_enter import output


def _worktree_parent(project_dir: Path) -> Path:
    """Return the worktree parent directory (sibling to project's parent)."""
    return project_dir.parent / ".nix-enter-worktrees"


def _check_git_repo(project_dir: Path) -> None:
    """Validate that project_dir is inside a git repository."""
    result = subprocess.run(
        ["git", "-C", str(project_dir), "rev-parse", "--git-dir"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        output.die(f"Not a git repository: {project_dir}")


def _check_branch_name(name: str) -> None:
    """Validate that name is a valid git branch name."""
    result = subprocess.run(
        ["git", "check-ref-format", "--branch", name],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        output.die(f"Invalid branch name: {name}")


def create_worktree(project_dir: Path, name: str, branch: str | None = None) -> None:
    """Create a git worktree with its own container workspace."""
    _check_git_repo(project_dir)
    _check_branch_name(name)

    parent = _worktree_parent(project_dir)
    wt_path = parent / name

    if wt_path.exists():
        output.die(f"Worktree already exists: {wt_path}")

    parent.mkdir(parents=True, exist_ok=True)

    if branch is None:
        cmd = ["git", "-C", str(project_dir), "worktree", "add", str(wt_path), "-b", name]
    else:
        cmd = ["git", "-C", str(project_dir), "worktree", "add", str(wt_path), branch]

    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        output.die(f"git worktree add failed: {result.stderr.strip()}")

    # Copy .nix-enter/config.toml if it exists in the main project
    src_config = project_dir / ".nix-enter" / "config.toml"
    if src_config.exists():
        dst_config_dir = wt_path / ".nix-enter"
        dst_config_dir.mkdir(parents=True, exist_ok=True)
        dst_config = dst_config_dir / "config.toml"
        dst_config.write_text(src_config.read_text())
        output.verbose(f"Copied config.toml to worktree")

    # Copy Containerfile if it exists
    containerfile_name = "Containerfile.dev"  # Default
    if src_config.exists():
        from nix_enter.config import load_config
        config = load_config(src_config)
        containerfile_name = config.containerfile

    src_containerfile = project_dir / containerfile_name
    if src_containerfile.exists():
        dst_containerfile = wt_path / containerfile_name
        dst_containerfile.write_text(src_containerfile.read_text())
        output.verbose(f"Copied {containerfile_name} to worktree")

    output.ok(f"Worktree created at {wt_path}")
    output.info(f"cd {wt_path} && nix-enter")


def remove_worktree(project_dir: Path, name: str) -> None:
    """Remove a worktree and its associated container resources."""
    _check_git_repo(project_dir)

    parent = _worktree_parent(project_dir)
    wt_path = parent / name

    if not wt_path.exists():
        output.die(f"Worktree not found: {wt_path}")

    # Create a Project from the worktree path to find its resources
    wt_project = Project.from_path(wt_path)

    # Remove container if it exists
    if Podman.container_exists(wt_project.container_name):
        output.info(f"Removing container: {wt_project.container_name}")
        Podman.rm(wt_project.container_name, force=True)
        output.ok("Container removed")

    # Remove volumes if they exist
    for vol in [wt_project.volume_home, wt_project.volume_claude]:
        if Podman.volume_exists(vol):
            output.info(f"Removing volume: {vol}")
            Podman.volume_rm(vol)

    # Remove the git worktree
    result = subprocess.run(
        ["git", "-C", str(project_dir), "worktree", "remove", str(wt_path)],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        # Try with --force
        result = subprocess.run(
            ["git", "-C", str(project_dir), "worktree", "remove", "--force", str(wt_path)],
            capture_output=True, text=True, check=False,
        )
        if result.returncode != 0:
            output.die(f"git worktree remove failed: {result.stderr.strip()}")

    output.ok(f"Worktree removed: {name}")


def run(project_dir: Path, name: str, branch: str | None = None, remove: bool = False) -> None:
    """Dispatch to create or remove worktree."""
    if remove:
        remove_worktree(project_dir, name)
    else:
        create_worktree(project_dir, name, branch=branch)
