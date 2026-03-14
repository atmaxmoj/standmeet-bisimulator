#!/usr/bin/env bash
#
# Bisimulator one-line installer:
#   curl -fsSL https://raw.githubusercontent.com/.../install.sh | bash
#
# Prerequisites: macOS + Docker must be running.
#
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[bisimulator]${NC} $*"; }
warn()  { echo -e "${YELLOW}[bisimulator]${NC} $*"; }
error() { echo -e "${RED}[bisimulator]${NC} $*"; exit 1; }

OS="$(uname -s)"
info "Detected OS: $OS"

if [ "$OS" != "Darwin" ]; then
    error "bisimulator requires macOS (native screen capture uses CoreGraphics + Vision framework)"
fi

# --- Check Docker ---
if ! command -v docker >/dev/null 2>&1; then
    error "Docker not found. Install Docker Desktop first: https://www.docker.com/products/docker-desktop/"
fi
if ! docker info >/dev/null 2>&1; then
    error "Docker is not running. Start Docker Desktop and try again."
fi
info "Docker is running"

# --- Check uv ---
if ! command -v uv >/dev/null 2>&1; then
    info "Installing uv (Python package manager)..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi
info "uv is available"

# --- Clone or update bisimulator ---
INSTALL_DIR="${BISIMULATOR_DIR:-${HOME}/.bisimulator/app}"

if [ -d "$INSTALL_DIR/.git" ]; then
    info "Updating bisimulator in $INSTALL_DIR..."
    cd "$INSTALL_DIR"
    git pull --ff-only 2>/dev/null || true
else
    info "Installing bisimulator to $INSTALL_DIR..."
    mkdir -p "$(dirname "$INSTALL_DIR")"
    git clone https://github.com/atmaxmoj/standmeet-bisimulator.git "$INSTALL_DIR" 2>/dev/null || {
        mkdir -p "$INSTALL_DIR"
        warn "No remote repo found — assuming local development"
    }
fi

cd "$INSTALL_DIR"

# --- API key ---
if [ -f "$INSTALL_DIR/.env" ]; then
    info "Using existing .env"
elif [ -n "${ANTHROPIC_API_KEY:-}" ]; then
    echo "ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY" > "$INSTALL_DIR/.env"
    info "Created .env from environment variable"
else
    warn "No API key found!"
    echo ""
    echo "  Set your Anthropic API key:"
    echo "    export ANTHROPIC_API_KEY=sk-ant-..."
    echo "    # then re-run this script"
    echo ""
    echo "  Or create manually:"
    echo "    echo 'ANTHROPIC_API_KEY=sk-ant-...' > $INSTALL_DIR/.env"
    echo ""
    error "ANTHROPIC_API_KEY is required"
fi

# --- Install capture daemon dependencies ---
info "Installing capture daemon dependencies..."
cd "$INSTALL_DIR/capture"
uv sync
cd "$INSTALL_DIR"

# --- Start capture daemon ---
mkdir -p "${HOME}/.bisimulator"

if pgrep -f "python -m capture" >/dev/null 2>&1; then
    info "Capture daemon already running (pid $(pgrep -f 'python -m capture'))"
else
    info "Starting capture daemon..."
    cd "$INSTALL_DIR/capture"
    uv run python -m capture > /tmp/bisimulator-capture.log 2>&1 &
    cd "$INSTALL_DIR"
    sleep 2
    if pgrep -f "python -m capture" >/dev/null 2>&1; then
        info "Capture daemon started (pid $(pgrep -f 'python -m capture'))"
    else
        error "Capture daemon failed to start. Check /tmp/bisimulator-capture.log"
    fi
fi

# --- Screen recording permission check ---
if [ ! -f "${HOME}/.bisimulator/capture.db" ]; then
    warn "Capture DB not created yet. You may need to grant screen recording permission:"
    warn "  System Settings > Privacy & Security > Screen Recording > Terminal (or your terminal app)"
fi

# --- Start engine ---
info "Building and starting bisimulator engine..."
docker compose up --build -d

echo ""
info "========================================="
info "  Bisimulator is running!"
info "========================================="
info ""
info "  API:      http://localhost:5001"
info "  Status:   curl http://localhost:5001/engine/status"
info "  Usage:    curl http://localhost:5001/engine/usage"
info "  Logs:     cd $INSTALL_DIR && docker compose logs -f"
info "  Capture:  tail -f /tmp/bisimulator-capture.log"
info ""
info "  Stop:     cd $INSTALL_DIR && make stop"
info "  Restart:  cd $INSTALL_DIR && make start"
info ""
