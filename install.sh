#!/usr/bin/env bash
set -euo pipefail

# Kestrel installer — one command from zero to running
# Usage: curl -fsSL https://raw.githubusercontent.com/pleasedodisturb/kestrel/main/install.sh | bash

KESTREL_VENV="$HOME/.kestrel/venv"
KESTREL_MIN_PYTHON="3.13"

# ──────────────────────────────────────────────

echo ""
echo "  Kestrel Installer"
echo "  ================="
echo "  AI-powered job search, running on your computer."
echo ""

cleanup() {
    if [ $? -ne 0 ]; then
        echo ""
        echo "  Something went wrong during installation."
        echo ""
        echo "  Try the manual install instead:"
        echo "    pip install kestrel-app && kestrel start"
        echo ""
        echo "  Still stuck? Open an issue:"
        echo "    https://github.com/pleasedodisturb/kestrel/issues"
    fi
}
trap cleanup EXIT

# ── Helpers ──

command_exists() { command -v "$1" &>/dev/null; }

version_gte() {
    # Returns 0 if $1 >= $2 (dotted version comparison)
    local IFS=.
    local i a=($1) b=($2)
    for ((i = 0; i < ${#b[@]}; i++)); do
        local av="${a[i]:-0}" bv="${b[i]:-0}"
        if ((av > bv)); then return 0; fi
        if ((av < bv)); then return 1; fi
    done
    return 0
}

detect_python() {
    # Try python3 first, then python
    for cmd in python3 python; do
        if command_exists "$cmd"; then
            local ver
            ver=$("$cmd" --version 2>&1 | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?' | head -1)
            if [ -n "$ver" ] && version_gte "$ver" "$KESTREL_MIN_PYTHON"; then
                echo "$cmd"
                return 0
            fi
        fi
    done
    return 1
}

# ── Handle --dry-run ──

if [[ "${1:-}" == "--dry-run" ]]; then
    DRY_RUN=true
else
    DRY_RUN=false
fi

# ── Step 1: Detect OS ──

OS="$(uname -s)"
ARCH="$(uname -m)"

case "$OS" in
    Darwin) OS_NAME="macOS" ;;
    Linux)  OS_NAME="Linux" ;;
    *)
        echo "Unsupported operating system: $OS"
        echo "Kestrel supports macOS and Linux."
        echo "On Windows, use WSL: https://learn.microsoft.com/en-us/windows/wsl/install"
        exit 1
        ;;
esac

echo "[ok] Detected $OS_NAME ($ARCH)"

# ── Step 2: Check internet ──

if ! curl -sf --max-time 5 https://pypi.org/simple/ >/dev/null 2>&1; then
    echo ""
    echo "Can't reach PyPI (pypi.org). Check your internet connection."
    echo "Kestrel needs internet for installation."
    exit 1
fi
echo "[ok] Internet connection works"

# ── Step 3: Check / install Python ──

PYTHON_CMD=""
if PYTHON_CMD=$(detect_python); then
    python_ver=$("$PYTHON_CMD" --version 2>&1 | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?' | head -1)
    echo "[ok] Python $python_ver found ($PYTHON_CMD)"
else
    echo ""
    echo "Python $KESTREL_MIN_PYTHON or newer is required but not found."
    echo ""

    case "$OS" in
        Darwin)
            if command_exists brew; then
                echo "  Install with Homebrew:"
                echo "    brew install python@3.13"
                echo ""
                echo "  Then run this installer again."
            else
                echo "  Download Python from:"
                echo "    https://www.python.org/downloads/"
                echo ""
                echo "  Or install Homebrew first (https://brew.sh), then:"
                echo "    brew install python@3.13"
            fi
            ;;
        Linux)
            if command_exists apt-get; then
                echo "  Install on Ubuntu/Debian:"
                echo "    sudo add-apt-repository ppa:deadsnakes/ppa"
                echo "    sudo apt-get update"
                echo "    sudo apt-get install python3.13 python3.13-venv"
                echo ""
                echo "  Then run this installer again."
            elif command_exists dnf; then
                echo "  Install on Fedora/RHEL:"
                echo "    sudo dnf install python3.13"
                echo ""
                echo "  Then run this installer again."
            elif command_exists pacman; then
                echo "  Install on Arch Linux:"
                echo "    sudo pacman -S python"
                echo ""
                echo "  Then run this installer again."
            else
                echo "  Download Python from:"
                echo "    https://www.python.org/downloads/"
            fi
            ;;
    esac
    echo ""
    exit 1
fi

if [ "$DRY_RUN" = true ]; then
    echo ""
    echo "Dry run complete. Everything looks good."
    echo "Run this script without --dry-run to install Kestrel."
    exit 0
fi

# ── Step 4: Install kestrel-app ──

echo ""
echo "Installing Kestrel..."

# Check if kestrel is already installed
if command_exists kestrel; then
    echo "[ok] Kestrel is already installed, upgrading..."
    if command_exists pipx; then
        pipx upgrade kestrel-app 2>/dev/null || pipx install kestrel-app --force
    elif [ -d "$KESTREL_VENV" ]; then
        "$KESTREL_VENV/bin/pip" install --upgrade kestrel-app
    else
        "$PYTHON_CMD" -m pip install --upgrade kestrel-app
    fi
else
    # Fresh install — prefer pipx, then venv, then bare pip
    if command_exists pipx; then
        echo "  Using pipx for isolated install..."
        pipx install kestrel-app
    elif "$PYTHON_CMD" -m venv --help &>/dev/null 2>&1; then
        echo "  Creating virtual environment at $KESTREL_VENV..."
        mkdir -p "$HOME/.kestrel"
        "$PYTHON_CMD" -m venv "$KESTREL_VENV"
        "$KESTREL_VENV/bin/pip" install --upgrade pip >/dev/null 2>&1
        "$KESTREL_VENV/bin/pip" install kestrel-app
    else
        echo "  Installing with pip..."
        "$PYTHON_CMD" -m pip install kestrel-app
    fi
fi

# ── Step 5: Ensure kestrel is on PATH ──

if command_exists kestrel; then
    echo "[ok] kestrel command is available"
elif [ -x "$KESTREL_VENV/bin/kestrel" ]; then
    # Venv install — add to PATH
    KESTREL_BIN="$KESTREL_VENV/bin"
    SHELL_NAME="$(basename "${SHELL:-/bin/bash}")"

    case "$SHELL_NAME" in
        zsh)  PROFILE="$HOME/.zshrc" ;;
        bash) PROFILE="$HOME/.bashrc" ;;
        fish) PROFILE="$HOME/.config/fish/config.fish" ;;
        *)    PROFILE="$HOME/.profile" ;;
    esac

    if [ -f "$PROFILE" ] && grep -q "$KESTREL_BIN" "$PROFILE" 2>/dev/null; then
        : # Already in profile
    else
        echo "" >> "$PROFILE"
        echo "# Kestrel" >> "$PROFILE"
        echo "export PATH=\"$KESTREL_BIN:\$PATH\"" >> "$PROFILE"
        echo "[ok] Added $KESTREL_BIN to PATH in $PROFILE"
        echo "     Restart your shell or run: source $PROFILE"
    fi

    export PATH="$KESTREL_BIN:$PATH"
    echo "[ok] kestrel command is available"
else
    echo ""
    echo "  Installation succeeded but 'kestrel' isn't on your PATH."
    echo "  Try: pip install kestrel-app && kestrel start"
    exit 1
fi

# ── Step 6: Launch ──

echo ""
echo "================================================"
echo ""
echo "  Kestrel is installed!"
echo ""
echo "  Starting Kestrel..."
echo "  Your browser will open automatically."
echo ""
echo "  Data stored in: ~/.kestrel/"
echo "  To stop: press Ctrl+C"
echo "  To start again: kestrel start"
echo ""
echo "================================================"
echo ""

kestrel start
