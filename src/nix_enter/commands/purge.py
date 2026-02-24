"""--purge: remove orphaned nix-enter resources."""

from pathlib import Path

from nix_enter.podman import Podman
from nix_enter import output


def run() -> None:
    output.info("Scanning for orphaned nix-enter resources...")

    managed_filter = {"label": "nix-enter.managed=true"}
    orphans: dict[str, str] = {}  # dir -> name
    orphan_containers: list[str] = []
    orphan_volumes: list[str] = []
    orphan_images: list[str] = []

    for container in Podman.ps(filters=managed_filter):
        labels = container.get("Labels", {})
        pdir = labels.get("nix-enter.project-dir", "")
        if pdir and not Path(pdir).is_dir():
            orphans[pdir] = labels.get("nix-enter.project-name", "unknown")
            cname = container.get("Names", [""])[0] if isinstance(container.get("Names"), list) else container.get("Names", "")
            orphan_containers.append(cname)

    for vol in Podman.volume_ls(filters=managed_filter):
        labels = vol.get("Labels", {})
        pdir = labels.get("nix-enter.project-dir", "")
        if pdir and not Path(pdir).is_dir():
            orphans[pdir] = labels.get("nix-enter.project-name", "unknown")
            orphan_volumes.append(vol.get("Name", ""))

    for img in Podman.image_ls(filters=managed_filter):
        labels = img.get("Labels", {})
        pdir = labels.get("nix-enter.project-dir", "")
        if pdir and not Path(pdir).is_dir():
            orphans[pdir] = labels.get("nix-enter.project-name", "unknown")
            orphan_images.append(img.get("Id", img.get("ID", "")))

    if not orphans:
        output.ok("No orphaned resources found")
        return

    print()
    output.warn(f"Found orphaned resources from {len(orphans)} deleted project(s):")
    print()
    for pdir, pname in orphans.items():
        print(f"  {output.RED}{pname}{output.NC} ({pdir})")
    print()
    print(f"  Containers: {len(orphan_containers)}")
    print(f"  Volumes:    {len(orphan_volumes)}")
    print(f"  Images:     {len(orphan_images)}")
    print()

    if not output.confirm("Remove all orphaned resources? Type 'yes' to confirm: "):
        output.info("Aborted")
        return

    for c in orphan_containers:
        output.info(f"Removing container: {c}")
        Podman.rm(c, force=True)
    for v in orphan_volumes:
        output.info(f"Removing volume: {v}")
        Podman.volume_rm(v)
    for i in orphan_images:
        output.info(f"Removing image: {i}")
        Podman.rmi(i)

    output.ok("Purge complete")
