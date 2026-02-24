from unittest.mock import patch, MagicMock
import json
from nix_enter.podman import Podman


def _mock_run(stdout="", returncode=0):
    result = MagicMock()
    result.stdout = stdout
    result.returncode = returncode
    return result


@patch("nix_enter.podman.subprocess.run")
def test_container_exists_true(mock_run):
    mock_run.return_value = _mock_run(returncode=0)
    assert Podman.container_exists("mycontainer") is True
    mock_run.assert_called_once()
    assert "exists" in mock_run.call_args[0][0]


@patch("nix_enter.podman.subprocess.run")
def test_container_exists_false(mock_run):
    mock_run.return_value = _mock_run(returncode=1)
    assert Podman.container_exists("mycontainer") is False


@patch("nix_enter.podman.subprocess.run")
def test_inspect_returns_parsed_json(mock_run):
    data = [{"State": {"Status": "running"}}]
    mock_run.return_value = _mock_run(stdout=json.dumps(data))
    result = Podman.inspect("mycontainer")
    assert result["State"]["Status"] == "running"


@patch("nix_enter.podman.subprocess.run")
def test_ps_with_filters(mock_run):
    data = [{"Names": "test", "State": "running"}]
    mock_run.return_value = _mock_run(stdout=json.dumps(data))
    result = Podman.ps(filters={"label": "nix-enter.managed=true"})
    assert len(result) == 1
    cmd = mock_run.call_args[0][0]
    assert "--filter" in cmd
    assert "label=nix-enter.managed=true" in cmd


@patch("nix_enter.podman.subprocess.run")
def test_volume_exists(mock_run):
    mock_run.return_value = _mock_run(returncode=0)
    assert Podman.volume_exists("myvol") is True


@patch("nix_enter.podman.subprocess.run")
def test_image_exists(mock_run):
    mock_run.return_value = _mock_run(returncode=0)
    assert Podman.image_exists("myimg") is True
