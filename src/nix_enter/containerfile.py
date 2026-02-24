"""Containerfile generation with language detection."""

from pathlib import Path

TEMPLATES = {
    "base": """\
FROM registry.fedoraproject.org/fedora:latest

# System packages
RUN dnf install -y --skip-unavailable \\
    git \\
    wget \\
    nodejs \\
    npm \\
    python3 \\
    gcc \\
    gcc-c++ \\
    make \\
    procps-ng \\
  && dnf clean all

# Claude Code
RUN npm install -g @anthropic-ai/claude-code

# Non-root user
ARG USER_NAME={user}
ARG USER_UID={uid}
RUN useradd -m -u "$USER_UID" -s /bin/bash "$USER_NAME"
USER $USER_NAME

WORKDIR /workspace
CMD ["/bin/bash"]
""",
    "python": """\
FROM registry.fedoraproject.org/fedora:latest

# System + Python packages
RUN dnf install -y --skip-unavailable \\
    git \\
    wget \\
    nodejs \\
    npm \\
    python3 \\
    python3-devel \\
    python3-pip \\
    gcc \\
    gcc-c++ \\
    make \\
    procps-ng \\
  && dnf clean all

# Claude Code
RUN npm install -g @anthropic-ai/claude-code

# Non-root user
ARG USER_NAME={user}
ARG USER_UID={uid}
RUN useradd -m -u "$USER_UID" -s /bin/bash "$USER_NAME"
USER $USER_NAME

WORKDIR /workspace
CMD ["/bin/bash"]
""",
    "node": """\
FROM registry.fedoraproject.org/fedora:latest

# System + Node packages
RUN dnf install -y --skip-unavailable \\
    git \\
    wget \\
    nodejs \\
    npm \\
    python3 \\
    gcc \\
    gcc-c++ \\
    make \\
    procps-ng \\
  && dnf clean all

# Claude Code
RUN npm install -g @anthropic-ai/claude-code

# Non-root user
ARG USER_NAME={user}
ARG USER_UID={uid}
RUN useradd -m -u "$USER_UID" -s /bin/bash "$USER_NAME"
USER $USER_NAME

WORKDIR /workspace
CMD ["/bin/bash"]
""",
    "rust": """\
FROM registry.fedoraproject.org/fedora:latest

# System packages
RUN dnf install -y --skip-unavailable \\
    git \\
    wget \\
    nodejs \\
    npm \\
    python3 \\
    gcc \\
    gcc-c++ \\
    make \\
    procps-ng \\
    rustup \\
  && dnf clean all

# Claude Code
RUN npm install -g @anthropic-ai/claude-code

# Non-root user
ARG USER_NAME={user}
ARG USER_UID={uid}
RUN useradd -m -u "$USER_UID" -s /bin/bash "$USER_NAME"
USER $USER_NAME

# Rust toolchain
RUN rustup-init -y
ENV PATH="/home/{user}/.cargo/bin:${{PATH}}"

WORKDIR /workspace
CMD ["/bin/bash"]
""",
    "go": """\
FROM registry.fedoraproject.org/fedora:latest

# System + Go packages
RUN dnf install -y --skip-unavailable \\
    git \\
    wget \\
    nodejs \\
    npm \\
    python3 \\
    gcc \\
    gcc-c++ \\
    make \\
    procps-ng \\
    golang \\
  && dnf clean all

# Claude Code
RUN npm install -g @anthropic-ai/claude-code

# Non-root user
ARG USER_NAME={user}
ARG USER_UID={uid}
RUN useradd -m -u "$USER_UID" -s /bin/bash "$USER_NAME"
USER $USER_NAME

WORKDIR /workspace
CMD ["/bin/bash"]
""",
}


def detect_language(project_dir: Path) -> str:
    """Detect project language from marker files."""
    markers = {
        "python": ["pyproject.toml", "requirements.txt", "setup.py"],
        "node": ["package.json"],
        "rust": ["Cargo.toml"],
        "go": ["go.mod"],
    }
    for lang, files in markers.items():
        if any((project_dir / f).exists() for f in files):
            return lang
    return "base"


def generate_containerfile(
    project_dir: Path,
    user: str,
    uid: int,
    containerfile_name: str = "Containerfile.dev",
) -> str | None:
    """Generate a Containerfile. Returns None if user already has one."""
    if (project_dir / containerfile_name).exists():
        return None
    lang = detect_language(project_dir)
    return TEMPLATES[lang].format(user=user, uid=uid)
