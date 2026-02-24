"""Project identity — naming, hashing, path conventions."""

from dataclasses import dataclass
from pathlib import Path
import hashlib
import re


@dataclass
class Project:
    dir: Path
    name: str
    hash: str

    @classmethod
    def from_path(cls, path: Path) -> "Project":
        name = path.name
        name = re.sub(r"[^a-zA-Z0-9._-]", "-", name).rstrip("-")
        if not name:
            name = "project"
        path_hash = hashlib.sha256(str(path).encode()).hexdigest()[:12]
        return cls(dir=path, name=name, hash=path_hash)

    @classmethod
    def from_cwd(cls) -> "Project":
        return cls.from_path(Path.cwd())

    @property
    def container_name(self) -> str:
        return f"nix-enter-{self.name}-{self.hash}"

    @property
    def image_name(self) -> str:
        return f"nix-enter-{self.name}-{self.hash}:latest"

    @property
    def volume_home(self) -> str:
        return f"nix-enter-home-{self.name}-{self.hash}"

    @property
    def volume_claude(self) -> str:
        return f"nix-enter-claude-{self.name}-{self.hash}"

    @property
    def labels(self) -> dict[str, str]:
        return {
            "nix-enter.managed": "true",
            "nix-enter.project-dir": str(self.dir),
            "nix-enter.project-name": self.name,
            "nix-enter.project-hash": self.hash,
        }

    @property
    def nixenter_dir(self) -> Path:
        return self.dir / ".nix-enter"

    @property
    def log_dir(self) -> Path:
        return self.nixenter_dir / "logs"
