FROM python:3.12-slim

# Real shells: zsh, bash, fish
RUN apt-get update && apt-get install -y --no-install-recommends \
    zsh bash fish \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/

# Test user (non-root)
RUN useradd -m -s /bin/zsh testuser
USER testuser
WORKDIR /home/testuser/app

# Install capture with test deps
COPY --chown=testuser capture/pyproject.toml ./
RUN uv sync --no-install-project --extra test 2>/dev/null || uv sync --no-install-project

COPY --chown=testuser capture/src/ src/
COPY --chown=testuser capture/tests/ tests/

# Generate real shell histories
COPY --chown=testuser capture/tests/docker/setup_shells.sh /home/testuser/setup_shells.sh
RUN /home/testuser/setup_shells.sh

ENV PYTHONPATH=/home/testuser/app/src
CMD ["uv", "run", "pytest", "tests/test_probe_docker.py", "-xvs"]
