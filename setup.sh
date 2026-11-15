#!/usr/bin/env bash
# Set up the standalone vision service. Pass --yes to skip the confirmation.
set -euo pipefail
cd "$(dirname "$0")"
if [[ ${1:-} != --yes ]]; then
  read -r -p "Create .venv and install vision dependencies? [Y/n] " answer
  [[ ${answer:-y} =~ ^[Yy]([Ee][Ss])?$ ]] || exit 0
fi
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
