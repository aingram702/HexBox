#!/bin/bash
# ~/hexbox/payloads/sharkjack_recon.sh
# Auto-recon any network it gets plugged into

NETMODE DHCP_CLIENT
LED SETUP
wait_for_network() {
    while ! ip route | grep -q default; do sleep 1; done
}
wait_for_network

LED ATTACK
LOOT=/root/loot/$(date +%s)
mkdir -p $LOOT

# Gateway + local IP
ip route > $LOOT/route.txt
ip addr  > $LOOT/ip.txt

GW=$(ip route | grep default | awk '{print $3}')
SUB=$(echo $GW | cut -d. -f1-3).0/24

# Fast nmap
nmap -sS -T4 -F $SUB -oA $LOOT/nmap_fast
# Targeted version scan on the gateway + DC ports
nmap -sV -p21,22,23,53,80,88,135,139,389,443,445,3389,5985 $SUB -oA $LOOT/nmap_services

# Grab DHCP info
cat /var/lib/dhcp/dhclient.leases > $LOOT/dhcp.txt 2>/dev/null

# Stage for exfil
tar czf /root/loot/latest.tgz -C /root/loot .

LED FINISH
