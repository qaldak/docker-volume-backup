#!/usr/bin/env bash
set -euo pipefail

# === Configuration ===
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_DIR/venv"
REQ_FILE="$PROJECT_DIR/requirements.txt"

# === Helpers ===
get_python_version() {
  local cmd=$1
  if command -v "$cmd" &> /dev/null; then
    $cmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
  else
    echo ""
  fi
}

# Function: Show info/warning for selected version
show_version_info() {
  local version=$1
  case $version in
    3.13|3.14|3.15)
      echo
      echo "⚠ WARNING: Python $version may not be fully tested yet."
      echo "Proceed with caution."
      ;;
    3.9)
      echo
      echo "⚠ WARNING: Python $version reached End-of-Life in October 2025."
      echo "Consider upgrading to a supported version."
      ;;
    3.10)
      echo
      echo "ℹ INFO: Python $version will reach End-of-Life in October 2026."
      ;;
    3.11|3.12)
      echo
      echo "✓ venv installed with Python $version (stable and recommended)."
      ;;
    *)
      echo
      echo "⚠ WARNING: Python $version not supported. Install a supported version or proceed at your own risk."
      ;;
  esac
}

# === Main ===
echo "=== SETUP PYTHON PROJECT ENVIRONMENT ==="
echo "Project directory: $PROJECT_DIR"

# Find available python binaries in /usr/bin
echo
echo "Searching for available Python versions..."
PYVERSIONS=$(ls /usr/bin 2>/dev/null | grep -E '^python(3(\.[0-9]+)?)?$' | sort -rV || true)

if [ -z "$PYVERSIONS" ]; then
  echo "ERROR: No Python installation found!"
  exit 1
fi

declare -a PYTHON_COMMANDS=()
declare -a PYTHON_VERSIONS=()
declare -a PYTHON_DISPLAY=()
counter=0

for PY in $PYVERSIONS; do
  version=$(get_python_version "/usr/bin/$PY")
  if [ -n "$version" ]; then
    counter=$((counter + 1))
    PYTHON_COMMANDS+=("/usr/bin/$PY")
    PYTHON_VERSIONS+=("$version")
    PYTHON_DISPLAY+=("$counter) Python $version ($PY)")
  fi
done

if [ ${#PYTHON_COMMANDS[@]} -eq 0 ]; then
  echo "ERROR: No working Python installation found!"
  exit 1
fi

echo
echo "Available Python versions:"
echo "----------------------------------------"
for display in "${PYTHON_DISPLAY[@]}"; do
  echo "$display"
done
echo "----------------------------------------"

# Prompt user for selection
while true; do
  echo
  read -p "Select Python version (1-${#PYTHON_COMMANDS[@]}): " selection

  # Validate input
  if [[ "$selection" =~ ^[0-9]+$ ]] && [ "$selection" -ge 1 ] && [ "$selection" -le "${#PYTHON_COMMANDS[@]}" ]; then
    break
  else
    echo "Invalid selection. Please enter a number between 1 and ${#PYTHON_COMMANDS[@]}."
  fi
done

# Get selected Python
index=$((selection - 1))
PYTHON_CMD="${PYTHON_COMMANDS[$index]}"
PYTHON_VERSION_SHORT="${PYTHON_VERSIONS[$index]}"
PYTHON_VERSION_FULL=$($PYTHON_CMD --version 2>&1)

echo
echo "Selected: $PYTHON_VERSION_FULL"
echo "Python command: $PYTHON_CMD"

# Create venv if missing
echo
if [ ! -d "$VENV_DIR" ]; then
  echo "Setup new virtual environment (venv) ..."
  $PYTHON_CMD -m venv "$VENV_DIR"
else
  echo "Use existing venv environment"
fi

# Activate venv
# shellcheck disable=SC1090
source "$VENV_DIR/bin/activate"

# Upgrade packaging tools
echo
echo "Upgrade pip, setuptools and wheel ..."
python -m pip install --upgrade pip setuptools wheel build

# Install/Update dependencies
echo
if [ -f "$REQ_FILE" ]; then
  echo "Install or update dependencies ..."
  pip install --upgrade -r "$REQ_FILE"
else
  echo "WARNING: requirements.txt not found"
fi

# Build and install package reproducibly
echo
echo "Install package ..."
pip install --upgrade .


# Verify dependency graph
echo
echo "Verify installed packages and dependency consistency ..."
pip check || true

# Optional: run tests if pytest present
if command -v pytest > /dev/null 2>&1; then
  echo
  echo "Running test suite (pytest) ..."
  pytest || echo "Tests failed or returned non-zero exit code"
fi

echo
echo "=== Setup completed successfully ==="

# Show version-specific info/warnings
show_version_info "$PYTHON_VERSION_SHORT"

echo
echo "Check crontab. Example:"
echo "0 2 * * * $PROJECT_DIR/venv/bin/python -m docker_volume_backup.main --backup <Docker container name>"
