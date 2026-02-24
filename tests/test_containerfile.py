from pathlib import Path
from nix_enter.containerfile import detect_language, generate_containerfile


def test_detect_python(tmp_path):
    (tmp_path / "pyproject.toml").touch()
    assert detect_language(tmp_path) == "python"


def test_detect_node(tmp_path):
    (tmp_path / "package.json").touch()
    assert detect_language(tmp_path) == "node"


def test_detect_rust(tmp_path):
    (tmp_path / "Cargo.toml").touch()
    assert detect_language(tmp_path) == "rust"


def test_detect_go(tmp_path):
    (tmp_path / "go.mod").touch()
    assert detect_language(tmp_path) == "go"


def test_detect_none(tmp_path):
    assert detect_language(tmp_path) == "base"


def test_generate_base(tmp_path):
    content = generate_containerfile(tmp_path, user="user", uid=1000)
    assert "FROM registry.fedoraproject.org/fedora:latest" in content
    assert "USER" in content
    assert "claude.ai/install.sh" in content


def test_generate_python(tmp_path):
    (tmp_path / "pyproject.toml").touch()
    content = generate_containerfile(tmp_path, user="user", uid=1000)
    assert "python3-pip" in content or "python3-devel" in content


def test_generate_node(tmp_path):
    (tmp_path / "package.json").touch()
    content = generate_containerfile(tmp_path, user="user", uid=1000)
    assert "nodejs" in content


def test_existing_containerfile_not_overwritten(tmp_path):
    cf = tmp_path / "Containerfile.dev"
    cf.write_text("FROM custom:image\n")
    content = generate_containerfile(
        tmp_path, user="user", uid=1000, containerfile_name="Containerfile.dev"
    )
    assert content is None  # signals: don't generate, user has their own
