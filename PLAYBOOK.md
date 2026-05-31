# 🎯 Operational Playbook
### On-site workflow:
1. Plug HexBox into power, boot ~60s
2. Connect laptop to HexBox WiFi AP (hexbox-mgmt)
3. Browse to http://10.0.0.1:1337 → C2 dashboard
4. Drop devices:
* SharkJack → any open Ethernet port (2-min recon, yank out)
* Packet Squirrel → between printer/IP phone and switch (long-term MITM)
* LAN Turtle → behind a workstation (persistent foothold)
* OMG Plug → wall outlet near target machine (HID payload)
5. Pineapple → run continuously for WiFi capture
6. Watch loot flow into ~/hexbox/loot/


## 🧠 Recommended Add-ons Down the Road

* Bash Bunny support (same DuckyScript engine - drop in payloads/)
* Flipper Zero integration via serial CLI
* Sliver C2 instead of/in addition to Meterpreter
* Pi-hosted Cobalt Strike teamserver (if licensed)
* GPS module for war-driving with the Pineapple


Want me to expand any module? I can dive deeper into:
* A custom Evil Portal template that mimics O365/Okta
* An AD recon module for the Turtle (BloodHound ingestor)
* An OMG Plug WiFi C2 channel (no callback infra needed)
* A mobile companion app to control HexBox from your phone

