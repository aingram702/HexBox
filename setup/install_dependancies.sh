#!/bin/bash
# ~/hexbox/setup/install_dependancies.sh
# Install Python dependencies listed in requirements.txt

set -euo pipefail

HEXBOX_DIR="$(cd "$(dirname "$0")/.." && pwd)"
REQ="$HEXBOX_DIR/requirements.txt"

if [ ! -f "$REQ" ]; then
    echo "[ERR] requirements.txt not found at $REQ"
    exit 1
fi

echo "[*] Installing Python dependencies from requirements.txt..."
pip3 install --break-system-packages -r "$REQ"
echo "[+] Done."
