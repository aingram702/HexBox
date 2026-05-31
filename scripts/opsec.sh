#!/bin/bash
# ~/hexbox/scripts/opsec.sh - Run before going on-site

# Route all Pi traffic through Tor (optional)
sudo systemctl start tor

# Rotate MACs on every interface
for iface in $(ls /sys/class/net | grep -v lo); do
    sudo ifconfig $iface down
    sudo macchanger -r $iface
    sudo ifconfig $iface up
done

# Set hostname to something boring
sudo hostnamectl set-hostname "DESKTOP-WIN10"

# Disable bash history for this session
unset HISTFILE
export HISTSIZE=0

# Encrypt loot at rest
LOOT=~/hexbox/loot
tar czf - $LOOT | gpg -c --cipher-algo AES256 > /tmp/loot_$(date +%s).tar.gz.gpg
shred -uz $LOOT/*

echo "[+] OPSEC posture set."
