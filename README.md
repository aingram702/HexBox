# 🔥 HexBox — The Ultimate Red Team Multitool

> *"One box to rule them all."*

HexBox is a portable, all-in-one offensive security platform built around a **Raspberry Pi 3B** that orchestrates an arsenal of **Hak5 hardware** into a unified red team weapon system. Drop it in a backpack, plug it into a wall outlet, and run full-spectrum engagements from a single web dashboard.

![Status](https://img.shields.io/badge/status-operational-red) ![Platform](https://img.shields.io/badge/platform-Raspberry%20Pi%203B-c51a4a) ![License](https://img.shields.io/badge/license-Authorized%20Use%20Only-black) ![Python](https://img.shields.io/badge/python-3.9%2B-blue)

---

## ⚠️ Legal Disclaimer

**This toolkit is for AUTHORIZED penetration testing and red team engagements ONLY.**

You must have **explicit written permission** from the system/network owner before deploying any component of HexBox. Unauthorized use against systems you do not own or have permission to test is **illegal** and may result in criminal prosecution.

The authors assume **zero liability** for misuse. You are the operator. You are responsible.

---

## 🎯 What is HexBox?

HexBox turns a Raspberry Pi 3B into a **command-and-control hub** for the following Hak5 ecosystem devices:

| Device | Role |
|--------|------|
| 🍍 **WiFi Pineapple** | Wireless attacks, rogue AP, Evil Portal, handshake capture |
| 🦈 **Shark Jack** | Drop-and-go network recon, fast nmap sweeps |
| 🐿️ **Packet Squirrel** | Inline MITM, traffic capture, DNS spoofing |
| 🐢 **LAN Turtle** | Persistent foothold, reverse SSH tunnels, Responder, Meterpreter |
| 🔌 **OMG Plug** | Wireless HID payload delivery via DuckyScript |

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

- ✅ **Unified Web Dashboard** — Control every device from one browser tab
- ✅ **Automated Recon** — One-click nmap, masscan, Pineapple scanning
- ✅ **Credential Harvesting** — Built-in Responder, browser cred exfil, WiFi profile theft
- ✅ **MITM Suite** — Bettercap, ARP spoofing, DNS spoofing, transparent proxying
- ✅ **HID Attack Delivery** — Pre-built DuckyScript payloads for OMG Plug
- ✅ **Persistent C2** — Auto-SSH reverse tunnels via LAN Turtle
- ✅ **Loot Management** — Centralized storage, auto-pull from all devices
- ✅ **OPSEC Hardening** — MAC randomization, Tor routing, encrypted loot at rest
- ✅ **"Engage" Button** — Single script launches a full assessment

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

### 3. Reboot
```bash
sudo reboot
```

---

## ⚙️ Configuration — **READ THIS BEFORE DEPLOYING**

> 🚨 **HexBox will NOT work out of the box.** Every environment is different, and you **must** customize several files to match your network topology, device IPs, and target environment.

### Required Configuration Steps

#### 🔧 1. Device IP Addresses
The default IPs in `c2/hexbox_c2.py` are based on each Hak5 device's **factory default management subnet**. If you've changed any device's IP (which you should for OPSEC), or if you're routing them through a switch on a different subnet, **update the `DEVICES` dictionary**:

```python
DEVICES = {
    "pineapple":      {"ip": "172.16.42.1",  "user": "root", "pass": "hak5pineapple"},
    "sharkjack":      {"ip": "172.16.24.1",  "user": "root", "pass": "hak5shark"},
    "packetsquirrel": {"ip": "172.16.32.1",  "user": "root", "pass": "hak5squirrel"},
    "lanturtle":      {"ip": "172.16.84.1",  "user": "root", "pass": "hak5turtle"},
    "omgplug":        {"ip": "192.168.1.50", "user": "root", "pass": "hak5omg"},
}
```

#### 🔑 2. Credentials
**Change every password.** The defaults above are placeholders — your real Hak5 devices use whatever you set during their initial provisioning. If you reused factory defaults, change them now and update this dictionary.

#### 🎯 3. Callback / C2 IP
Multiple payloads reference a hardcoded callback IP (`10.0.0.99` by default). This needs to be **your HexBox's IP on the target network** (or your public C2 IP for off-site work). Update these files:

| File | What to change |
|------|----------------|
| `payloads/reverse_shell.ducky` | Replace `10.0.0.99` with your listener IP |
| `payloads/browser_exfil.ducky` | Update the `iwr` URL |
| `payloads/chrome.ps1` | Update the `Invoke-WebRequest` target |
| `payloads/wifi_steal.ducky` | Update the POST URL |
| `payloads/squirrel_mitm.sh` | Update the DNS spoof target IP (`10.10.10.10`) |

A handy one-liner to find & replace globally:
```bash
grep -rl "10.0.0.99" ~/hexbox/payloads/ | xargs sed -i 's/10.0.0.99/YOUR.IP.HERE/g'
```

#### 🌐 4. Target Network Range
The `scripts/engage.sh` master script defaults to scanning `192.168.1.0/24`. Either:
- Pass the target subnet as an argument: `./engage.sh 10.10.0.0/16`
- Or edit the default in the script

#### 🐢 5. LAN Turtle AutoSSH
For the reverse tunnel back to your HexBox to work, you need:
- A **public IP or VPS** that the LAN Turtle can phone home to
- A `tunnel` user on that host with key-based SSH auth
- Edit `SERVER=<YOUR_HEXBOX_PUBLIC_IP>` in the Turtle setup block

#### 📡 6. WiFi Interface Names
The default config assumes `wlan0` (Pi's built-in) and `wlan1mon` (Pineapple). If you're using external adapters (Alfa AWUS036ACH, etc.), update interface references in:
- `c2/hexbox_c2.py` (Bettercap, Responder routes)
- `scripts/opsec.sh` (MAC rotation loop)

#### 🍍 7. Pineapple API Token
The `scripts/pineapple_auto.py` script logs into the Pineapple's API. If you've changed the root password from the default, update the `USER` / `PASS` constants at the top of that file.

#### 📁 8. Loot Path (Optional)
Loot defaults to `~/hexbox/loot/`. If you've added an external SSD, symlink it:
```bash
sudo mount /dev/sda1 /mnt/ssd
rm -rf ~/hexbox/loot
ln -s /mnt/ssd/loot ~/hexbox/loot
```

#### 🔒 9. Dashboard Authentication (Strongly Recommended)
The Flask C2 dashboard ships **without authentication** for rapid lab use. Before deploying in any real environment, add Flask-Login or HTTP Basic Auth at minimum. Anyone on the management network can currently fire payloads.

---

### Configuration Sanity Check

Run the included pre-flight check before going on-site:

```bash
python3 scripts/preflight.py
```

This will:
- Ping every configured Hak5 device
- Test SSH credentials
- Verify payload callback IPs resolve
- Confirm required services are running
- Validate loot directory is writable

---

## 🎮 Usage

### Start the C2 Dashboard
```bash
sudo python3 ~/hexbox/c2/hexbox_c2.py
```
Browse to `http://<pi-ip>:1337`

### One-Shot Engagement Mode
```bash
sudo ~/hexbox/scripts/engage.sh 10.10.0.0/24
```
This fires up everything — Pineapple, Responder, catchers, dashboard, listeners — in one shot.

### Deploy a Hak5 Payload
1. Plug device into target environment
2. Hit the corresponding button in the dashboard
3. Watch loot stream into `~/hexbox/loot/`

---

## 📁 Project Structure

```
hexbox/
├── setup/
│   └── hexbox_setup.sh          # Base provisioning
├── c2/
│   ├── hexbox_c2.py             # Main Flask dashboard
│   └── catcher.py               # Exfil endpoint
├── payloads/
│   ├── reverse_shell.ducky      # OMG: Win reverse shell
│   ├── browser_exfil.ducky      # OMG: Chrome cred theft
│   ├── wifi_steal.ducky         # OMG: WiFi profile dump
│   ├── chrome.ps1               # PowerShell stager
│   ├── sharkjack_recon.sh       # Shark Jack auto-recon
│   └── squirrel_mitm.sh         # Packet Squirrel MITM
├── scripts/
│   ├── engage.sh                # Master launch script
│   ├── opsec.sh                 # Hardening / MAC rotation
│   ├── pineapple_auto.py        # Pineapple API automation
│   └── preflight.py             # Pre-deployment validation
├── loot/                        # Captured data lands here
│   ├── pcaps/
│   ├── handshakes/
│   ├── creds/
│   └── screenshots/
└── logs/                        # Operational logs
```

---

## 🛡️ OPSEC Notes

- **Always run `scripts/opsec.sh` before deployment** to rotate MACs and harden the hostname
- HexBox encrypts loot at rest using GPG AES-256 — set a strong passphrase
- The C2 dashboard binds to `0.0.0.0:1337` — firewall it to your management interface only
- Consider routing Pi callbacks through Tor or a VPN for off-site C2
- DuckyScript payloads are **plaintext on the OMG Plug** — assume they can be recovered if the device is captured

---

## 🗺️ Roadmap

- [ ] Bash Bunny payload integration
- [ ] Flipper Zero serial bridge
- [ ] Sliver C2 implant generation
- [ ] Mobile companion app (Android)
- [ ] BloodHound auto-ingestion module
- [ ] Custom Evil Portal templates (O365, Okta, Duo)
- [ ] GPS war-driving mode
- [ ] Encrypted loot exfil over DNS

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
