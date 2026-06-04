#!/bin/bash
# hexbox_setup.sh — One-time provisioning for Raspberry Pi 3B, 4, or 5
# Run as root on a fresh Raspberry Pi OS Lite (Bullseye or Bookworm)
#
# Usage: sudo bash setup/hexbox_setup.sh

set -e

# ── Detect hardware and OS ────────────────────────────────────────────────────

PI_MODEL=$(tr -d '\0' < /proc/device-tree/model 2>/dev/null || echo "Unknown Pi")
OS_CODENAME=$(. /etc/os-release 2>/dev/null && echo "${VERSION_CODENAME:-unknown}" || echo "unknown")

# Pi 5 / Bookworm uses /boot/firmware/config.txt; Pi 3/4 uses /boot/config.txt
if [ -f /boot/firmware/config.txt ]; then
    BOOT_CFG=/boot/firmware/config.txt
else
    BOOT_CFG=/boot/config.txt
fi

echo "╔══════════════════════════════════════════════╗"
echo "║       HexBox — Base Provisioning             ║"
echo "╚══════════════════════════════════════════════╝"
echo ""
echo "  Hardware : $PI_MODEL"
echo "  OS       : Raspberry Pi OS $OS_CODENAME"
echo "  Boot cfg : $BOOT_CFG"
echo ""

# ── System update ─────────────────────────────────────────────────────────────

sudo apt update && sudo apt full-upgrade -y

# ── Base packages (all models) ────────────────────────────────────────────────

sudo apt install -y \
    python3-pip python3-venv git tmux \
    nmap masscan \
    aircrack-ng hcxdumptool hashcat hostapd dnsmasq \
    tcpdump tshark \
    responder \
    net-tools sshpass proxychains4 tor \
    sqlmap nikto hydra \
    macchanger iptables-persistent \
    dsniff ettercap-text-only \
    bettercap mitmproxy

# ── Bookworm: python3-full required for pip --break-system-packages ───────────
# Bookworm enforces the "externally-managed-environment" restriction.
# python3-full provides the stdlib extensions needed before --break-system-packages works.

if [ "$OS_CODENAME" = "bookworm" ]; then
    sudo apt install -y python3-full
    echo "[+] Installed python3-full (Bookworm requirement)"
fi

# ── Pi 4 / Pi 5: EEPROM updater ───────────────────────────────────────────────
# rpi-eeprom manages bootloader firmware for Pi 4 (VL805 USB controller)
# and Pi 5 (RP1 integrated controller). Safe to install on all models.

if echo "$PI_MODEL" | grep -qE "Raspberry Pi [45]"; then
    sudo apt install -y rpi-eeprom
    echo "[+] Installed rpi-eeprom (Pi 4/5 firmware updater)"
fi

# ── Pi 5: enable maximum USB current ─────────────────────────────────────────
# Pi 5 defaults to limiting USB ports to 600mA total when powered by a
# standard 15W supply. With a 27W (5V/5A) supply, setting usb_max_current_enable=1
# unlocks full 1.6A per port — required when running multiple Hak5 devices.

if echo "$PI_MODEL" | grep -q "Raspberry Pi 5"; then
    if ! grep -q "usb_max_current_enable=1" "$BOOT_CFG" 2>/dev/null; then
        echo "" | sudo tee -a "$BOOT_CFG" > /dev/null
        echo "# HexBox: unlock full USB current (requires 27W / 5V 5A supply)" \
            | sudo tee -a "$BOOT_CFG" > /dev/null
        echo "usb_max_current_enable=1" | sudo tee -a "$BOOT_CFG" > /dev/null
        echo "[+] Pi 5: enabled max USB current in $BOOT_CFG"
        echo "[!] Pi 5 requires a 27W (5V/5A) USB-C supply for full operation"
    else
        echo "[*] Pi 5: usb_max_current_enable already set"
    fi
fi

# ── Python packages ───────────────────────────────────────────────────────────

sudo pip3 install --break-system-packages \
    flask flask-socketio requests \
    paramiko scapy pwntools impacket \
    pycryptodome netaddr colorama

# ── Metasploit ────────────────────────────────────────────────────────────────

curl -fsSL \
    https://raw.githubusercontent.com/rapid7/metasploit-omnibus/master/config/templates/metasploit-framework-wrappers/msfupdate.erb \
    > msfinstall \
    && chmod 755 msfinstall \
    && sudo ./msfinstall \
    && rm -f msfinstall

# ── Directory structure ───────────────────────────────────────────────────────

mkdir -p ~/hexbox/{loot,payloads,scripts,logs,c2,modules}
mkdir -p ~/hexbox/loot/{pcaps,handshakes,creds,screenshots,nmap,hashes,exfil,shark,bunny,bloodhound,implants,portals,wardrive,cracks,reports}

# ── IP forwarding for MITM ────────────────────────────────────────────────────

if ! grep -q 'net.ipv4.ip_forward=1' /etc/sysctl.conf; then
    echo 'net.ipv4.ip_forward=1' | sudo tee -a /etc/sysctl.conf
fi
sudo sysctl -p

# ── MAC randomisation service ─────────────────────────────────────────────────
# Enumerates every non-loopback interface dynamically so this works on Pi 3,
# 4, and 5 regardless of the number of attached USB Ethernet adapters.
# Runs before networking starts so the random MAC is used for the first DHCP
# request — important for OPSEC on engagement networks.

sudo tee /etc/systemd/system/macspoof.service > /dev/null <<'UNIT'
[Unit]
Description=Randomize MAC addresses at boot (HexBox OPSEC)
After=network-pre.target
Before=network.target
DefaultDependencies=no

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/bin/bash -c '\
  for iface in $(ls /sys/class/net | grep -v "^lo$"); do \
    ip link set "$iface" down  2>/dev/null || true; \
    macchanger -r "$iface"    2>/dev/null || true; \
    ip link set "$iface" up   2>/dev/null || true; \
  done'

[Install]
WantedBy=multi-user.target
UNIT

sudo systemctl daemon-reload
sudo systemctl enable macspoof.service
echo "[+] macspoof.service enabled (dynamic interface enumeration)"

# ── Summary ───────────────────────────────────────────────────────────────────

echo ""
echo "[+] =================================================="
echo "[+]  Provisioning complete."
echo "[+]"
echo "[+]  Next steps:"
echo "[+]    1. bash setup/configure.sh"
echo "[+]    2. reboot"
echo "[+]    3. sudo python3 scripts/preflight.py"
echo "[+] =================================================="

# Model-specific reminders
if echo "$PI_MODEL" | grep -q "Raspberry Pi 5"; then
    echo ""
    echo "[!]  Pi 5 reminders:"
    echo "     - Use a 27W (5V/5A) USB-C power supply"
    echo "     - Use a powered USB hub for multiple Hak5 devices"
    echo "     - Flipper Zero: verify /dev/ttyACM0 is available after boot"
    echo "     - Boot config lives at $BOOT_CFG (not /boot/config.txt)"
elif echo "$PI_MODEL" | grep -q "Raspberry Pi 4"; then
    echo ""
    echo "[!]  Pi 4 reminders:"
    echo "     - Use a 15W (5V/3A) USB-C power supply"
    echo "     - USB 3.0 ports (blue) give faster loot transfers from Hak5 devices"
fi
