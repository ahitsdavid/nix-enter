"""Thin wrapper around podman subprocess calls with JSON parsing."""

import json
import subprocess
from pathlib import Path


class Podman:
    """Static methods wrapping podman CLI commands."""

    @staticmethod
    def _run(
        args: list[str],
        capture: bool = True,
        check: bool = True,
    ) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["podman", *args],
            capture_output=capture,
            text=True,
            check=check,
        )

    @staticmethod
    def _run_json(args: list[str]) -> list[dict]:
        result = Podman._run([*args, "--format", "json"], check=False)
        if result.returncode != 0 or not result.stdout.strip():
            return []
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return []

    @staticmethod
    def container_exists(name: str) -> bool:
        result = Podman._run(["container", "exists", name], check=False)
        return result.returncode == 0

    @staticmethod
    def container_running(name: str) -> bool:
        data = Podman.inspect(name)
        if data is None:
            return False
        return data.get("State", {}).get("Status") == "running"

    @staticmethod
    def inspect(name: str) -> dict | None:
        results = Podman._run_json(["inspect", name])
        return results[0] if results else None

    @staticmethod
    def ps(filters: dict | None = None) -> list[dict]:
        args = ["ps", "-a"]
        for key, val in (filters or {}).items():
            args.extend(["--filter", f"{key}={val}"])
        return Podman._run_json(args)

    @staticmethod
    def volume_ls(filters: dict | None = None) -> list[dict]:
        args = ["volume", "ls"]
        for key, val in (filters or {}).items():
            args.extend(["--filter", f"{key}={val}"])
        return Podman._run_json(args)

    @staticmethod
    def image_ls(filters: dict | None = None) -> list[dict]:
        args = ["image", "ls"]
        for key, val in (filters or {}).items():
            args.extend(["--filter", f"{key}={val}"])
        return Podman._run_json(args)

    @staticmethod
    def volume_exists(name: str) -> bool:
        result = Podman._run(["volume", "exists", name], check=False)
        return result.returncode == 0

    @staticmethod
    def image_exists(name: str) -> bool:
        result = Podman._run(["image", "exists", name], check=False)
        return result.returncode == 0

    @staticmethod
    def rm(name: str, force: bool = False) -> None:
        args = ["rm"]
        if force:
            args.append("-f")
        args.append(name)
        Podman._run(args)

    @staticmethod
    def volume_create(name: str, labels: dict | None = None) -> None:
        args = ["volume", "create"]
        for key, val in (labels or {}).items():
            args.extend(["--label", f"{key}={val}"])
        args.append(name)
        Podman._run(args)

    @staticmethod
    def volume_rm(name: str) -> None:
        Podman._run(["volume", "rm", name])

    @staticmethod
    def rmi(name: str) -> None:
        Podman._run(["rmi", name], check=False)

    @staticmethod
    def build(
        tag: str,
        containerfile: Path,
        context: Path,
        build_args: dict | None = None,
        labels: dict | None = None,
        log_file: Path | None = None,
    ) -> subprocess.CompletedProcess:
        args = ["build"]
        for key, val in (build_args or {}).items():
            args.extend(["--build-arg", f"{key}={val}"])
        for key, val in (labels or {}).items():
            args.extend(["--label", f"{key}={val}"])
        args.extend(["-t", tag, "-f", str(containerfile), str(context)])
        if log_file is None:
            return Podman._run(args, capture=False, check=False)
        # Tee build output to both terminal and log file
        proc = subprocess.Popen(
            ["podman", *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        try:
            with open(log_file, "w") as f:
                for line in proc.stdout:
                    print(line, end="", flush=True)
                    f.write(line)
        finally:
            proc.stdout.close()
            proc.wait()
        return subprocess.CompletedProcess(
            args=["podman", *args],
            returncode=proc.returncode,
        )

    @staticmethod
    def create(args: list[str], image: str) -> None:
        Podman._run(["create", *args, image])
