#!/bin/bash
# ~/hexbox/scripts/opsec.sh — Run before going on-site to harden OPSEC posture

HEXBOX_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOOT="$HEXBOX_DIR/loot"

echo "[*] Applying OPSEC posture..."

# Route traffic through Tor (comment out if not using Tor)
if sudo systemctl start tor 2>/dev/null; then
    echo "[+] Tor started"
else
    echo "[!] Tor failed to start (install with: sudo apt install tor)"
fi

# Rotate MACs on every non-loopback interface
for iface in $(ls /sys/class/net | grep -v lo); do
    sudo ip link set "$iface" down 2>/dev/null
    sudo macchanger -r "$iface" 2>/dev/null && echo "[+] MAC rotated: $iface"
    sudo ip link set "$iface" up 2>/dev/null
done

# Spoof hostname
sudo hostnamectl set-hostname "DESKTOP-WIN10"
echo "[+] Hostname → DESKTOP-WIN10"

# Kill bash history for this session
unset HISTFILE
export HISTSIZE=0
export HISTFILESIZE=0
echo "[+] Bash history suppressed"

# Encrypt and shred loot
if [ -d "$LOOT" ] && [ -n "$(find "$LOOT" -type f 2>/dev/null | head -1)" ]; then
    ARCHIVE="/tmp/loot_$(date +%s).tar.gz.gpg"
    tar czf - -C "$(dirname "$LOOT")" "$(basename "$LOOT")" \
        | gpg -c --cipher-algo AES256 > "$ARCHIVE"
    echo "[+] Loot encrypted → $ARCHIVE"
    # Shred individual files (not the directory itself)
    find "$LOOT" -type f -exec shred -uz {} \;
    echo "[+] Plaintext loot shredded"
else
    echo "[*] No loot files to encrypt"
fi

echo "[+] OPSEC posture set."
