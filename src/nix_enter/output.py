"""Colored terminal output helpers."""

import sys

RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
CYAN = "\033[0;36m"
NC = "\033[0m"

_verbose = False


def set_verbose(enabled: bool) -> None:
    global _verbose
    _verbose = enabled


def info(msg: str) -> None:
    print(f"{CYAN}[info]{NC}  {msg}")


def ok(msg: str) -> None:
    print(f"{GREEN}[ok]{NC}    {msg}")


def warn(msg: str) -> None:
    print(f"{YELLOW}[warn]{NC}  {msg}")


def err(msg: str) -> None:
    print(f"{RED}[error]{NC} {msg}", file=sys.stderr)


def verbose(msg: str) -> None:
    if _verbose:
        info(msg)


def die(msg: str) -> None:
    err(msg)
    sys.exit(1)


def confirm(prompt: str) -> bool:
    """Prompt user for 'yes' confirmation. Returns True if confirmed."""
    print(f"{prompt}", end="", flush=True)
    response = input()
    return response.strip() == "yes"
