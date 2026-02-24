"""--clean: remove container and volumes."""

from pathlib import Path

from nix_enter.project import Project
from nix_enter.podman import Podman
from nix_enter.log import log_event
from nix_enter import output


def run(project: Project, log_dir: Path, clean_all: bool = False) -> None:
    output.info(f"This will remove the container and home volume for: {project.name}")
    if clean_all:
        output.warn("With --all: claude config volume will also be removed")
    print()

    if not output.confirm("Type 'yes' to confirm: "):
        output.info("Aborted")
        return

    if Podman.container_exists(project.container_name):
        output.info(f"Removing container: {project.container_name}")
        Podman.rm(project.container_name, force=True)
        log_event(log_dir, f"REMOVE container={project.container_name}")
        output.ok("Container removed")
    else:
        output.info("Container not found, skipping")

    if Podman.volume_exists(project.volume_home):
        output.info(f"Removing volume: {project.volume_home}")
        Podman.volume_rm(project.volume_home)
        log_event(log_dir, f"REMOVE volume={project.volume_home}")
        output.ok("Home volume removed")
    else:
        output.info("Home volume not found, skipping")

    if clean_all:
        if Podman.volume_exists(project.volume_claude):
            output.info(f"Removing volume: {project.volume_claude}")
            Podman.volume_rm(project.volume_claude)
            log_event(log_dir, f"REMOVE volume={project.volume_claude}")
            output.ok("Claude volume removed")
        else:
            output.info("Claude volume not found, skipping")

    output.ok("Clean complete")
