# 🔥 HexBox — The Ultimate Red Team Multitool

> *"One box to rule them all."*
![Alt text](/images/hexbox-banner.png)
HexBox is a portable, all-in-one offensive security platform built around a **Raspberry Pi 3B** that orchestrates an arsenal of **Hak5 hardware** into a unified red team weapon system. Drop it in a backpack, plug it into a wall outlet, and run full-spectrum engagements from a single web dashboard.

![Status](https://img.shields.io/badge/status-operational-red) ![Platform](https://img.shields.io/badge/platform-Raspberry%20Pi%203B-c51a4a) ![License](https://img.shields.io/badge/license-Authorized%20Use%20Only-black) ![Python](https://img.shields.io/badge/python-3.9%2B-blue)

---

## ⚠️ Legal Disclaimer

**This toolkit is for AUTHORIZED penetration testing and red team engagements ONLY.**

You must have **explicit written permission** from the system/network owner before deploying any component of HexBox. Unauthorized use against systems you do not own or have permission to test is **illegal** and may result in criminal prosecution.

The authors assume **zero liability** for misuse. You are the operator. You are responsible.

---

## 🎯 What is HexBox?

HexBox turns a Raspberry Pi 3B into a **command-and-control hub** for the following Hak5 ecosystem devices — and more:

| Device | Role |
|--------|------|
| 🍍 **WiFi Pineapple** | Wireless attacks, rogue AP, Evil Portal, handshake capture |
| 🦈 **Shark Jack** | Drop-and-go network recon, fast nmap sweeps |
| 🐿️ **Packet Squirrel** | Inline MITM, traffic capture, DNS spoofing |
| 🐢 **LAN Turtle** | Persistent foothold, reverse SSH tunnels, Responder, Meterpreter |
| 🔌 **OMG Plug** | Wireless HID payload delivery via DuckyScript |
| 🐇 **Bash Bunny** | Multi-mode HID+ECM attacks, switch-selectable payloads |
| 🐬 **Flipper Zero** | NFC/RFID cloning, Sub-GHz capture, BadUSB — serial bridge |

Also integrates **Sliver C2** (implant generation and session management) and **BloodHound CE** (AD graph auto-ingest).

All controlled from a single **Flask-based C2 dashboard** running on the Pi.

---

## 🏗️ Architecture

```
                    ┌─────────────────────┐
                    │   HexBox (Pi 3B)    │
                    │  Command & Control  │
                    │   Flask Dashboard   │
                    └──────────┬──────────┘
                               │
        ┌──────────┬───────────┼──────────┬──────────┐
        │          │           │          │          │
   ┌────▼───┐ ┌────▼────┐ ┌────▼────┐ ┌──▼───┐ ┌────▼────┐
   │Pineapple│ │SharkJack│ │Packet   │ │ LAN  │ │ OMG    │
   │ (WiFi) │ │ (Recon) │ │Squirrel │ │Turtle│ │ Plug   │
   └────────┘ └─────────┘ └─────────┘ └──────┘ └────────┘
```

---

## 🧰 Features

### Core Platform
- ✅ **Unified Web Dashboard** — 6-tab C2 interface: Devices, Intel, Payloads, Loot, Logs, Report
- ✅ **Token Authentication** — Session-based login with configurable `HEXBOX_TOKEN`; all routes protected
- ✅ **Real-Time Event Feed** — SSE-powered live activity stream; toast notifications for new loot and process events
- ✅ **Engagement Sessions** — Named engagement tracking with start time, target, and notes
- ✅ **Device Status Indicators** — Live ping dots with parallel reachability checks

### Intelligence & Analysis
- ✅ **Loot Intelligence Engine** — `parse_loot.py` auto-parses all captured data into structured intel
- ✅ **NTLM Hash Extraction** — Auto-discovers NTLMv1/v2 hashes from Responder logs with deduplication
- ✅ **WiFi Credential Parsing** — Parses stolen WiFi profiles (SSID + plaintext password table)
- ✅ **Network Map** — nmap XML parsing populates a sortable host/service/role table; role inference (DC, web server, printer, etc.)
- ✅ **System Profile Collection** — Captures hostname, domain membership, IPs, local admins, AV products, running processes
- ✅ **Active Directory Recon** — No-module LDAP enumeration: users, computers, domain admins
- ✅ **BloodHound Auto-Ingest** — `bloodhound_collect.ps1` builds full BloodHound v5 JSON (users, computers, groups, domains with real SIDs); Intel tab shows summary; one-click upload to BloodHound CE via REST API
- ✅ **One-Click Report Generator** — Produces a self-contained HTML engagement report with all intel sections

### Offense & Collection
- ✅ **Bash Bunny Integration** — SSH device management, install switch payloads from dashboard, pull loot; `bunny_recon.sh` (ECM subnet sweep) and `bunny_exfil.sh` (HID+ECM Windows credential dump)
- ✅ **Flipper Zero Serial Bridge** — pyserial bridge to `/dev/ttyACM0`; dashboard buttons for NFC detect, RFID read, Sub-GHz RX, BadUSB execution
- ✅ **Sliver C2 Implant Generation** — Start/stop sliver-server daemon, generate implants (Windows/Linux/macOS × amd64/arm64 × exe/shellcode/shared), list active sessions, download generated implants
- ✅ **Payload Builder** — Web UI generates custom DuckyScript for any of 5 payload types with configurable IP/port/delay
- ✅ **Hashcat Integration** — Auto-extracts NTLMv2 hashes from Responder logs and launches hashcat (`-m 5600`) cracking
- ✅ **PMKID Capture** — One-click hcxdumptool PMKID attack via Pineapple
- ✅ **Monitor Mode Management** — airmon-ng monitor mode toggle from dashboard
- ✅ **Credential Harvesting** — Responder LLMNR/NBT-NS poisoning, Chrome DPAPI exfil, WiFi profile theft
- ✅ **MITM Suite** — Bettercap ARP spoofing, DNS spoofing, Packet Squirrel inline capture
- ✅ **SSH Pivot** — LAN Turtle reverse tunnel to `hexbox_ip:2222` for internal access
- ✅ **Persistent C2** — AutoSSH reverse tunnels via LAN Turtle + Meterpreter module

### Operations
- ✅ **Loot File Browser** — Download any captured file directly from the dashboard
- ✅ **Process Management** — Start/stop all background services with whitelist-enforced kill buttons
- ✅ **Log Viewer** — Real-time log tail for all services with auto-refresh
- ✅ **"Engage" Button** — Single script launches full assessment with graceful Ctrl+C shutdown
- ✅ **OPSEC Hardening** — MAC randomization, hostname spoofing, GPG loot encryption, configurable interfaces

---

## 📦 Hardware Requirements

### Core
- **Raspberry Pi 3B** (or 3B+ / 4)
- 64GB+ Class 10 microSD card
- 20,000mAh USB-C power bank
- Powered USB hub (4+ ports, 2A per port)
- USB-to-Ethernet adapter (the Pi's onboard NIC is occupied)

### Hak5 Arsenal
- WiFi Pineapple (Mark VII or Enterprise)
- Shark Jack
- Packet Squirrel (Mark II recommended)
- LAN Turtle
- OMG Plug (or OMG Cable / Adapter)

### Optional but Recommended
- 3.5" touchscreen HAT (for headless field ops)
- External 1TB SSD for loot storage
- Pelican 1200 case
- Travel router (for off-site C2 callback)

---

## 🚀 Installation

### 1. Flash the Pi
Use Raspberry Pi Imager to write **Raspberry Pi OS Lite (64-bit)** to your SD card. Enable SSH in the imager's advanced options.

### 2. Clone & Run Setup
```bash
ssh pi@<pi-ip>
git clone https://github.com/yourhandle/hexbox.git ~/hexbox
cd ~/hexbox
chmod +x setup/hexbox_setup.sh
sudo ./setup/hexbox_setup.sh
```

The setup script installs the entire offensive toolchain: nmap, aircrack-ng, Responder, Bettercap, Metasploit, hashcat, and all Python dependencies.

### 3. Configure
```bash
bash setup/configure.sh
```

This interactive script prompts for your attacker IP and device credentials **once**, writes `config.json`, and automatically propagates your IP into every payload file — no manual editing of multiple files required.

### 4. Reboot
```bash
sudo reboot
```

---

## ⚙️ Configuration — **READ THIS BEFORE DEPLOYING**

> 🚨 **HexBox will NOT work out of the box.** Every environment is different, and you **must** customize it to match your network topology, device IPs, and target environment.

### One-Command Setup (Recommended)

```bash
bash setup/configure.sh
```

Prompts you for:
- Your HexBox / attacker IP (replaces `10.0.0.99` in all payload files automatically)
- Default target scan subnet
- External C2 server IP
- Passwords for each Hak5 device

Writes everything to **`config.json`** — the single source of truth loaded by all Python scripts.

### Manual Configuration

Edit **`config.json`** in the repo root:

```json
{
  "hexbox": {
    "ip": "10.0.0.99",
    "scan_target": "192.168.1.0/24"
  },
  "devices": {
    "pineapple":      {"ip": "172.16.42.1",  "user": "root", "pass": "hak5pineapple"},
    "sharkjack":      {"ip": "172.16.24.1",  "user": "root", "pass": "hak5shark"},
    "packetsquirrel": {"ip": "172.16.32.1",  "user": "root", "pass": "hak5squirrel"},
    "lanturtle":      {"ip": "172.16.84.1",  "user": "root", "pass": "hak5turtle"},
    "omgplug":        {"ip": "192.168.1.50", "user": "root", "pass": "hak5omg"},
    "bashbunny":      {"ip": "172.16.64.1",  "user": "root", "pass": "hak5bunny"}
  },
  "flipper":    {"serial_port": "/dev/ttyACM0"},
  "bloodhound": {"url": "http://localhost:8080", "username": "admin", "password": "BloodHound!"},
  "sliver":     {"host": "127.0.0.1", "port": 31337},
  "c2": {
    "external_ip": "YOUR.C2.IP.HERE"
  }
}
```

`hexbox_c2.py`, `catcher.py`, and `pineapple_auto.py` all load from this file. After editing, propagate the IP to payload files:

```bash
grep -rl "10.0.0.99" ~/hexbox/payloads/ | xargs sed -i 's/10.0.0.99/YOUR.IP.HERE/g'
```

### Additional Required Steps

#### 🐢 LAN Turtle AutoSSH
For the reverse tunnel to work:
- A **public IP or VPS** the LAN Turtle can phone home to
- A `tunnel` user on that host with key-based SSH auth
- Edit `SERVER=<YOUR_HEXBOX_PUBLIC_IP>` in `payloads/turtle_foothold.sh`

#### 📡 WiFi Interface Names
Defaults assume `wlan0` (Pi built-in) and `wlan1mon` (Pineapple). If using external adapters, update interface references in:
- `c2/hexbox_c2.py` (Bettercap, Responder routes)
- `scripts/opsec.sh` (MAC rotation loop)

#### 📁 External SSD for Loot (Optional)
```bash
sudo mount /dev/sda1 /mnt/ssd
rm -rf ~/hexbox/loot
ln -s /mnt/ssd/loot ~/hexbox/loot
```

#### 🔒 Dashboard Authentication
The C2 dashboard is **token-protected by default**. On startup it prints a random access token — set it permanently via environment variable:

```bash
export HEXBOX_TOKEN="your-strong-secret-here"
sudo -E python3 ~/hexbox/c2/hexbox_c2.py
```

Or add `"api_token": "your-token"` to `config.json` under `"hexbox"`. All routes require a valid session or `X-HexBox-Token` header.

---

### Configuration Sanity Check

Run the included pre-flight check before going on-site:

```bash
sudo python3 scripts/preflight.py
```

This will:
- Ping every configured Hak5 device and test SSH credentials
- Verify Python packages and required tools are installed
- Confirm required services are running
- Validate loot directory structure is correct
- Check OPSEC posture (MAC randomization, hostname, firewall)
- Output a GO / NO-GO decision with a JSON report

---

## 🎮 Usage

### Start the C2 Dashboard
```bash
sudo python3 ~/hexbox/c2/hexbox_c2.py
```
Browse to `http://<pi-ip>:1337`. On first launch, the access token is printed to the console. Set `HEXBOX_TOKEN=<token>` to pin it permanently.

The dashboard has **6 tabs**:

| Tab | Purpose |
|-----|---------|
| **Devices** | Control all Hak5 devices, launch Pi-local tools, live activity feed |
| **Intel** | Parsed NTLM hashes, WiFi credentials, network map, Chrome DBs, system profiles |
| **Payloads** | Build and download custom DuckyScript payloads, deploy to OMG Plug |
| **Loot** | File browser with one-click download for any captured file |
| **Logs** | Real-time log tail for all services (Responder, Bettercap, hashcat, etc.) |
| **Report** | One-click HTML engagement report generator covering all intel |

### Credential Catcher

Run alongside the dashboard to receive payload callbacks:
```bash
python3 ~/hexbox/c2/catcher.py
```
Receives: Chrome databases (`/upload`), WiFi profiles (`/wifi`), system info (`/sysinfo`), and serves payloads to devices (`/serve/<name>`).

### One-Shot Engagement Mode
```bash
sudo bash ~/hexbox/scripts/engage.sh 10.10.0.0/24
```
Fires up everything — Pineapple, Responder, credential catcher, dashboard, reverse shell listeners — in one shot. Press **Ctrl+C** to cleanly stop all services.

### Deploy a Hak5 Payload
1. Plug device into target environment
2. Hit the corresponding button in the dashboard
3. Watch loot stream into `~/hexbox/loot/`

### OPSEC Hardening (Run Before Going On-Site)
```bash
bash ~/hexbox/scripts/opsec.sh
```
Rotates MACs, spoofs hostname, suppresses bash history, and encrypts existing loot with GPG AES-256.

### Bash Bunny Payload Installation

From the dashboard's **Devices → Bash Bunny** card:
- **Net Recon** — SSH-triggered recon (ARP scan + nmap) results appear in `/bunny/loot`
- **Pull Loot** — SFTP pull from `/tmp/bb_recon/` or `/root/loot/` to `loot/bunny/`
- **Install Switch1** — Copies `payloads/bunny_recon.sh` to `/root/udisk/payloads/switch1/payload.sh` via SFTP
- **Install Switch2** — Copies `payloads/bunny_exfil.sh` to `/root/udisk/payloads/switch2/payload.sh` via SFTP

### Flipper Zero Serial Bridge

Connect your Flipper Zero via USB. Dashboard auto-detects `/dev/ttyACM0` (configurable in `config.json → flipper.serial_port`). Install pyserial first:
```bash
pip install pyserial
```
Dashboard buttons send CLI commands to the Flipper and display output.

### Sliver C2

Install Sliver on the Pi:
```bash
curl https://sliver.sh/install | sudo bash
```
From the **Devices → Sliver C2** panel:
1. Click **Start Server** to launch `sliver-server daemon`
2. Select OS/arch/format and a listener URL, then click **Generate Implant**
3. Active sessions appear automatically in the panel
4. Generated implants are saved to `loot/implants/` and downloadable from the dashboard

### BloodHound Auto-Ingest

1. Deploy `bloodhound_collect.ducky` on an OMG Plug or type it via a Bash Bunny switch
2. The PowerShell script collects users, computers, groups, and domains with real SIDs and POSTs BloodHound v5 JSON to `catcher.py /bloodhound`
3. Data lands in `loot/bloodhound/`
4. In the **Intel → BloodHound Data** section, click **Upload to BloodHound** to push directly to BloodHound CE

Configure BloodHound CE credentials in `config.json → bloodhound`.

---

## 📁 Project Structure

```
hexbox/
├── config.json                      # ← Edit this: all IPs and credentials
├── requirements.txt                 # Python dependencies
├── setup/
│   ├── hexbox_setup.sh              # Base provisioning (run once on fresh Pi)
│   ├── configure.sh                 # Interactive one-time configuration
│   └── install_dependancies.sh      # Install Python deps from requirements.txt
├── c2/
│   ├── hexbox_c2.py                 # Main Flask C2 dashboard (Phase 4: Bunny, Flipper, Sliver, BloodHound)
│   ├── catcher.py                   # Credential receiver: Chrome, WiFi, sysinfo, BloodHound JSON
│   └── parse_loot.py                # Loot intelligence: hash parsing, nmap XML, WiFi, BloodHound, report gen
├── payloads/
│   ├── reverse_shell.ducky          # OMG: Windows reverse shell
│   ├── browser_exfil.ducky          # OMG: Chrome credential theft
│   ├── wifi_steal.ducky             # OMG: WiFi profile dump
│   ├── sysinfo.ducky                # OMG: Windows system profiling
│   ├── ad_recon.ducky               # OMG: Active Directory enumeration
│   ├── bloodhound_collect.ducky     # OMG: BloodHound v5 JSON collection
│   ├── chrome.ps1                   # PowerShell DPAPI exfil stager
│   ├── sysinfo.ps1                  # System recon: hostname/domain/admins/AV
│   ├── ad_recon.ps1                 # AD enumeration via .NET LDAP (no module required)
│   ├── bloodhound_collect.ps1       # BloodHound v5 data collector (users/computers/groups/domains with real SIDs)
│   ├── bunny_recon.sh               # Bash Bunny Switch 1: ECM net recon → exfil to HexBox
│   ├── bunny_exfil.sh               # Bash Bunny Switch 2: HID+ECM Windows credential dump
│   ├── sharkjack_recon.sh           # Shark Jack auto-recon
│   ├── squirrel_mitm.sh             # Packet Squirrel transparent MITM
│   ├── turtle_foothold.sh           # LAN Turtle module provisioning
│   └── turtle_receiver.sh           # C2-side tunnel receiver setup
├── scripts/
│   ├── engage.sh                    # Master launch + graceful shutdown
│   ├── opsec.sh                     # MAC rotation, GPG loot encryption
│   ├── pineapple_auto.py            # Pineapple REST API automation
│   └── preflight.py                 # Pre-deployment validation
├── loot/                            # Captured data lands here
│   ├── pcaps/
│   ├── handshakes/
│   ├── creds/
│   ├── screenshots/
│   ├── nmap/
│   ├── hashes/
│   ├── exfil/
│   └── shark/
└── logs/                            # Operational logs (c2.log, responder.log, etc.)
```

---

## 🛡️ OPSEC Notes

- **Always run `scripts/opsec.sh` before deployment** to rotate MACs and harden the hostname
- HexBox encrypts loot at rest using GPG AES-256 — set a strong passphrase
- The C2 dashboard binds to `0.0.0.0:1337` — firewall it to your management interface only
- Consider routing Pi callbacks through Tor or a VPN for off-site C2
- DuckyScript payloads are **plaintext on the OMG Plug** — assume they can be recovered if the device is captured
- `config.json` contains device passwords — do not commit it with real credentials to a public repo

---

## 🗺️ Roadmap

### Completed
- ✅ Phase 1: Core C2 dashboard, device control, process management
- ✅ Phase 2: Config-driven interfaces, parallel status, tabbed dashboard, loot/log APIs, auth, security hardening
- ✅ Phase 3: SSE live feed, intel engine (hash/WiFi/nmap/sysinfo parsing), payload builder, engagement sessions, hashcat, PMKID, AD recon, HTML report generator
- ✅ Phase 4: Bash Bunny integration, Flipper Zero serial bridge, Sliver C2 implant generation, BloodHound CE auto-ingest

### Upcoming
- [ ] Custom Evil Portal templates (O365, Okta, Duo, Google)
- [ ] PCAP analysis dashboard (tshark protocol/credential stats)
- [ ] GPS war-driving mode with Kismet integration
- [ ] Encrypted loot exfil over DNS / HTTPS covert channels
- [ ] Mobile companion app (read-only Android dashboard)
- [ ] Cracked password feedback loop (hashcat output back into Intel tab)

---

## 🤝 Contributing

PRs welcome from authorized red team operators. Please:
- Don't commit real callback IPs or credentials
- Don't include client-specific payloads or loot
- Tag any new payloads with target OS and detection notes

---

## 📚 Recommended Reading

- *Red Team Warfare* — Sarang Tumne
- *Red Team Operations* — MITRE ATT&CK aligned tradecraft
- *The Hacker Playbook 3* — Peter Kim
- Hak5 official docs: https://docs.hak5.org

---

## 📜 License

Released under an **Authorized Use Only** license. By cloning this repo you agree:
1. You will only use HexBox on systems you own or have written authorization to test
2. You will not redistribute this toolkit to unauthorized parties
3. You accept full legal responsibility for your actions

---

## 💀 Final Word

HexBox is a **force multiplier**, not a magic button. Real red teaming requires recon, patience, creativity, and discipline. This kit will get you operational fast — but **the operator behind it is the actual weapon.**

Stay sharp. Stay authorized. Stay on the dark side.

**— The HexBox Project**
