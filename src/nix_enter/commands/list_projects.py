"""--list: show all nix-enter projects system-wide."""

from pathlib import Path

from nix_enter.podman import Podman
from nix_enter import output


def run() -> None:
    output.info("Scanning for nix-enter projects...")
    print()

    managed_filter = {"label": "nix-enter.managed=true"}
    projects: dict[str, str] = {}  # dir -> name

    for container in Podman.ps(filters=managed_filter):
        labels = container.get("Labels", {})
        pdir = labels.get("nix-enter.project-dir", "")
        pname = labels.get("nix-enter.project-name", "")
        if pdir:
            projects[pdir] = pname

    for vol in Podman.volume_ls(filters=managed_filter):
        labels = vol.get("Labels", {})
        pdir = labels.get("nix-enter.project-dir", "")
        pname = labels.get("nix-enter.project-name", "")
        if pdir:
            projects[pdir] = pname

    for img in Podman.image_ls(filters=managed_filter):
        labels = img.get("Labels", {})
        pdir = labels.get("nix-enter.project-dir", "")
        pname = labels.get("nix-enter.project-name", "")
        if pdir:
            projects[pdir] = pname

    if not projects:
        output.info("No nix-enter projects found")
        return

    for pdir, pname in sorted(projects.items()):
        exists = Path(pdir).is_dir()
        marker = f"{output.GREEN}exists{output.NC}" if exists else f"{output.RED}MISSING{output.NC}"
        print(f"  {output.CYAN}{pname}{output.NC}")
        print(f"    Directory: {pdir} ({marker})")

        for container in Podman.ps(filters={"label": f"nix-enter.project-dir={pdir}"}):
            cname = container.get("Names", [""])[0] if isinstance(container.get("Names"), list) else container.get("Names", "")
            state = container.get("State", "unknown")
            print(f"    Container: {cname} ({state})")

        for vol in Podman.volume_ls(filters={"label": f"nix-enter.project-dir={pdir}"}):
            print(f"    Volume:    {vol.get('Name', '')}")

        for img in Podman.image_ls(filters={"label": f"nix-enter.project-dir={pdir}"}):
            repo = img.get("Repository", img.get("repository", ""))
            tag = img.get("Tag", img.get("tag", "latest"))
            print(f"    Image:     {repo}:{tag}")

        print()
