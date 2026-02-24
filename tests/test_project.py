from pathlib import Path
from nix_enter.project import Project


def test_project_from_path():
    p = Project.from_path(Path("/home/user/projects/myapp"))
    assert p.name == "myapp"
    assert len(p.hash) == 12
    assert p.container_name == f"nix-enter-myapp-{p.hash}"
    assert p.image_name == f"nix-enter-myapp-{p.hash}:latest"
    assert p.volume_home == f"nix-enter-home-myapp-{p.hash}"
    assert p.volume_claude == f"nix-enter-claude-myapp-{p.hash}"


def test_project_name_sanitization():
    p = Project.from_path(Path("/home/user/my weird project!"))
    assert all(c.isalnum() or c in "._-" for c in p.name)
    assert not p.name.endswith("-")


def test_project_hash_deterministic():
    a = Project.from_path(Path("/home/user/myapp"))
    b = Project.from_path(Path("/home/user/myapp"))
    assert a.hash == b.hash


def test_project_hash_differs_for_different_paths():
    a = Project.from_path(Path("/home/user/myapp"))
    b = Project.from_path(Path("/home/user/otherapp"))
    assert a.hash != b.hash


def test_project_labels():
    p = Project.from_path(Path("/home/user/myapp"))
    labels = p.labels
    assert labels["nix-enter.managed"] == "true"
    assert labels["nix-enter.project-dir"] == "/home/user/myapp"
    assert labels["nix-enter.project-name"] == "myapp"
    assert labels["nix-enter.project-hash"] == p.hash


def test_project_nixenter_dir():
    p = Project.from_path(Path("/home/user/myapp"))
    assert p.nixenter_dir == Path("/home/user/myapp/.nix-enter")
    assert p.log_dir == Path("/home/user/myapp/.nix-enter/logs")
