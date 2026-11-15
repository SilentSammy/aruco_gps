#!/bin/bash
# Launches camera capture, viewing, and vision on an existing network.
# Usage: ./run.sh [extra args passed to main.py]
cd "$(dirname "$0")" || exit 1

# Stop an older instance from this checkout before opening the camera.  This
# avoids the common "device busy" failure when run.sh is launched again after
# a previous terminal or supervisor was closed unexpectedly.
SCRIPT_DIR=$(pwd -P)
CURRENT_PID=$$
OLD_PIDS=()
if command -v pgrep >/dev/null 2>&1; then
  while IFS= read -r pid; do
    [ -n "$pid" ] || continue
    [ "$pid" = "$CURRENT_PID" ] && continue
    cmd=$(ps -p "$pid" -o args= 2>/dev/null || true)
    case "$cmd" in
      *camera_stream.py*|*main.py*--camera-source*)
      process_dir=$(readlink "/proc/$pid/cwd" 2>/dev/null || true)
      [ "$process_dir" = "$SCRIPT_DIR" ] && OLD_PIDS+=("$pid")
      ;;
    esac
  done < <(pgrep -f 'camera_stream.py|main.py.*--camera-source' || true)
fi
if [ "${#OLD_PIDS[@]}" -gt 0 ]; then
  echo "Stopping previous vision instance(s): ${OLD_PIDS[*]}"
  kill "${OLD_PIDS[@]}" 2>/dev/null || true
  for _ in {1..20}; do
    alive=false
    for pid in "${OLD_PIDS[@]}"; do
      kill -0 "$pid" 2>/dev/null && alive=true
    done
    "$alive" || break
    sleep 0.25
  done
  for pid in "${OLD_PIDS[@]}"; do
    kill -0 "$pid" 2>/dev/null && kill -KILL "$pid" 2>/dev/null || true
  done
fi

source .venv/bin/activate || exit 1

# An explicit setup (or a help request) skips the interactive menu.
SELECT_SETUP=true
for arg in "$@"; do
  case "$arg" in
    --setup|--setup=*|--help|-h) SELECT_SETUP=false ;;
  esac
done

if "$SELECT_SETUP"; then
  # Query the actual setups so names and print dimensions stay in sync.
  SETUP_DATA=$(python - <<'PY'
from vision_setup import DEFAULT_SETUP, VISION_SETUPS

for name, setup in VISION_SETUPS.items():
    width, height = setup.board.get_print_dimensions()
    default = "default" if setup is DEFAULT_SETUP else ""
    print(f"{name}\t{width * 100:g} x {height * 100:g} cm\t{default}")
PY
  ) || exit 1

  SETUP_NAMES=()
  DEFAULT_CHOICE=1
  echo "Select a vision setup (print width x height):"
  while IFS=$'\t' read -r setup_name dimensions default; do
    [ -n "$setup_name" ] || continue
    SETUP_NAMES+=("$setup_name")
    index=${#SETUP_NAMES[@]}
    if [ "$default" = "default" ]; then
      DEFAULT_CHOICE=$index
      printf '  %d) %s - %s (default)\n' "$index" "$setup_name" "$dimensions"
    else
      printf '  %d) %s - %s\n' "$index" "$setup_name" "$dimensions"
    fi
  done <<< "$SETUP_DATA"

  if [ "${#SETUP_NAMES[@]}" -eq 0 ]; then
    echo "No vision setups are available." >&2
    exit 1
  fi
  while true; do
    read -r -p "Choose a setup (press Enter for default): " choice || choice=$DEFAULT_CHOICE
    choice=${choice:-$DEFAULT_CHOICE}
    # Compare as strings to avoid interpreting user input as shell arithmetic.
    SELECTED_SETUP=
    for index in "${!SETUP_NAMES[@]}"; do
      if [ "$choice" = "$((index + 1))" ]; then
        SELECTED_SETUP=${SETUP_NAMES[$index]}
        break
      fi
    done
    [ -n "$SELECTED_SETUP" ] && break
    echo "Enter an option number from 1 to ${#SETUP_NAMES[@]}."
  done
  echo "Using vision setup: $SELECTED_SETUP"
  set -- --setup "$SELECTED_SETUP" "$@"
fi

HAS_BROADCAST=false
for arg in "$@"; do
  case "$arg" in --broadcast|--broadcast=*) HAS_BROADCAST=true ;; esac
done
if ! "$HAS_BROADCAST"; then
  # Preserve the legacy broadcast feed without assuming a particular subnet.
  set -- --broadcast 255.255.255.255 "$@"
fi
echo "Starting camera streaming and vision. Press Ctrl+C to stop both."
# Replace Bash with the supervisor so terminal signals reach it directly.
# Both child processes inherit this terminal; the supervisor owns their cleanup.
exec python -u -B camera_stream.py --run-vision "$@"
