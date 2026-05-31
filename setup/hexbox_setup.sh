#!/bin/bash
# hexbox_setup.sh - Run on fresh Raspberry Pi OS Lite

set -e

echo "[*] HexBox base provisioning starting..."

# Update + harden
sudo apt update && sudo apt full-upgrade -y
sudo apt install -y python3-pip python3-venv git tmux nmap masscan \
    aircrack-ng hcxdumptool hashcat hostapd dnsmasq tcpdump tshark \
    responder net-tools sshpass proxychains4 tor sqlmap nikto hydra \
    macchanger iptables-persistent dsniff ettercap-text-only \
    bettercap mitmproxy

# Python tooling
sudo pip3 install --break-system-packages flask flask-socketio requests \
    paramiko scapy pwntools impacket pycryptodome netaddr colorama

# Metasploit
curl https://raw.githubusercontent.com/rapid7/metasploit-omnibus/master/config/templates/metasploit-framework-wrappers/msfupdate.erb \
    > msfinstall && chmod 755 msfinstall && sudo ./msfinstall

# Directory structure
mkdir -p ~/hexbox/{loot,payloads,scripts,logs,c2,modules}
mkdir -p ~/hexbox/loot/{pcaps,handshakes,creds,screenshots}

# Enable IP forwarding for MITM
echo 'net.ipv4.ip_forward=1' | sudo tee -a /etc/sysctl.conf
sudo sysctl -p

# Auto-rotate MAC on boot
sudo tee /etc/systemd/system/macspoof.service > /dev/null <<EOF
[Unit]
Description=Spoof MAC at boot
After=network-pre.target
Before=network.target
[Service]
Type=oneshot
ExecStart=/usr/bin/macchanger -r wlan0
ExecStart=/usr/bin/macchanger -r eth0
[Install]
WantedBy=multi-user.target
EOF
sudo systemctl enable macspoof.service

echo "[+] Base done. Reboot, then run hexbox_c2.py"
