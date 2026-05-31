                    ┌─────────────────────┐
                    │   HexBox (Pi 3B)    │
                    │  Command & Control  │
                    │   Flask Dashboard   │
                    └──────────┬──────────┘
                               │
        ┌──────────┬───────────┼──────────┬──────────┐
        │          │           │          │          │
   ┌────▼───┐ ┌────▼────┐ ┌────▼────┐ ┌──▼───┐ ┌────▼────┐
   │Pineapple││SharkJack│ │Packet   │ │ LAN  │ │ OMG     │
   │ (WiFi) │ │ (Recon) │ │Squirrel │ │Turtle│ │ Plug    │
   └────────┘ └─────────┘ └─────────┘ └──────┘ └────────-┘


# 📦 PART 1: Hardware Setup
### Bill of materials:

Raspberry Pi 3B + 64GB SD card
20,000mAh USB battery (for portability)
Powered USB hub (Hak5 gear is hungry)
USB Ethernet adapter (Pi only has one NIC)
Small touchscreen (optional but baller)
3D-printed enclosure or Pelican case

### Network topology:

Pi wlan0 → connects to Pineapple management AP
Pi eth0 → switch → SharkJack/PacketSquirrel/LAN Turtle
Pineapple → target WiFi attacks
OMG Plug → standalone HID payload deployer (talks back to Pi via WiFi)

