#!/usr/bin/env bash
set -euo pipefail

# === Configuration ===
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_DIR/venv"
MIN_PYTHON="3.10"  # keep in sync with requires-python in pyproject.toml

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
    3.10)
      echo
      echo "⚠ WARNING: Python $version reached End-of-Life in October 2026."
      echo "Consider upgrading to a supported version."
      ;;
    3.11|3.12|3.13|3.14)
      echo
      echo "✓ venv installed with Python $version (covered by the CI test matrix)."
      ;;
    *)
      echo
      echo "⚠ WARNING: Python $version is not covered by the CI test matrix (3.10 - 3.14)."
      echo "Proceed with caution."
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
  read -r -p "Select Python version (1-${#PYTHON_COMMANDS[@]}): " selection

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

# Reject Python versions below the minimum required by the project
if ! "$PYTHON_CMD" -c "import sys; sys.exit(0 if sys.version_info >= tuple(map(int, '$MIN_PYTHON'.split('.'))) else 1)"; then
  echo
  echo "ERROR: $PYTHON_VERSION_FULL is not supported. Python $MIN_PYTHON or higher is required."
  exit 1
fi

echo
echo "Selected: $PYTHON_VERSION_FULL"
echo "Python command: $PYTHON_CMD"

# Create venv if missing (recreate it if its Python interpreter is gone)
echo
if [ -d "$VENV_DIR" ] && [ ! -x "$VENV_DIR/bin/python" ]; then
  echo "Existing venv at '$VENV_DIR' has no working Python interpreter (its original Python "
  echo "installation was likely removed or upgraded). Recreating it ..."
  rm -rf "$VENV_DIR"
fi

if [ ! -d "$VENV_DIR" ]; then
  echo "Setup new virtual environment (venv) ..."
  $PYTHON_CMD -m venv "$VENV_DIR"
else
  echo "Use existing venv environment"
fi

# Activate venv
# shellcheck disable=SC1090
source "$VENV_DIR/bin/activate"

# Update pip
echo
echo "Update pip ..."
python -m pip install --upgrade pip

# Install/Update docker_volume_backup including its dependencies (pinned in requirements.txt).
# No separate 'pip install -r requirements.txt': it caused false dependency conflict
# messages when an older installed version still pinned other dependency versions.
echo
echo "Install docker_volume_backup and dependencies ..."
pip install --upgrade "$PROJECT_DIR"

# Verify dependency graph (warning only)
echo
echo "Verify installed packages ..."
if ! pip check; then
  echo "⚠ WARNING: pip reports dependency problems (see above)."
fi

echo
echo "=== Setup completed successfully ==="

# Show version-specific info/warnings
show_version_info "$PYTHON_VERSION_SHORT"

echo
echo "Check crontab. Example:"
echo "0 2 * * * $PROJECT_DIR/venv/bin/python -m docker_volume_backup.main --backup <Docker container name>"
