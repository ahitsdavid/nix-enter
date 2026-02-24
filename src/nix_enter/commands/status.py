"""--status: show container/image/volume state for current project."""

from nix_enter.project import Project
from nix_enter.podman import Podman
from nix_enter import output


def run(project: Project) -> None:
    output.info(f"Project:   {project.name}")
    output.info(f"Directory: {project.dir}")
    output.info(f"Hash:      {project.hash}")
    print()

    if Podman.container_exists(project.container_name):
        data = Podman.inspect(project.container_name)
        state = data["State"]["Status"] if data else "unknown"
        output.ok(f"Container: {project.container_name} ({state})")
    else:
        output.warn(f"Container: {project.container_name} (not found)")

    if Podman.image_exists(project.image_name):
        output.ok(f"Image:     {project.image_name}")
    else:
        output.warn(f"Image:     {project.image_name} (not found)")

    for vol_name, label in [
        (project.volume_home, "Home"),
        (project.volume_claude, "Claude"),
    ]:
        if Podman.volume_exists(vol_name):
            output.ok(f"Volume:    {vol_name} ({label})")
        else:
            output.warn(f"Volume:    {vol_name} ({label}, not found)")
