#!/usr/bin/env python3
# =============================================================================
# HexBox Preflight Validation Script
# Author: HexBox Project
# Description: Pre-deployment validation for all HexBox components.
#              Run this before every engagement to ensure all systems
#              are operational. Fix any RED items before deploying.
#
# USAGE: sudo python3 preflight.py
#
# ⚠️  AUTHORIZED USE ONLY - See README.md for legal disclaimer
# =============================================================================

import os
import sys
import socket
import subprocess
import requests
import json
import shutil
from datetime import datetime
from colorama import Fore, Back, Style, init

# =============================================================================
# !! CONFIGURATION - EDIT THESE BEFORE DEPLOYMENT !!
# =============================================================================

CONFIG = {
    # --- Raspberry Pi / HexBox ---
    "hexbox": {
        "hostname":         "DESKTOP-WIN10",       # Spoofed hostname
        "mgmt_interface":   "wlan0",               # Management interface
        "mgmt_ip":          "10.0.0.1",            # HexBox management IP
        "dashboard_port":   1337,                  # Flask dashboard port
        "loot_dir":         "/home/pi/hexbox/loot",
        "log_dir":          "/home/pi/hexbox/logs",
        "gpg_key_id":       "YOUR_GPG_KEY_ID",     # GPG key for loot encryption
    },

    # --- WiFi Pineapple ---
    # Default Pineapple management IP is 172.16.42.1
    # Connect Pi to Pineapple AP or management ethernet
    "pineapple": {
        "enabled":          True,
        "ip":               "172.16.42.1",         # !! CHANGE IF DIFFERENT !!
        "port":             1471,                  # Pineapple web UI port
        "api_port":         1471,
        "api_key":          "YOUR_PINEAPPLE_API_KEY",  # !! SET YOUR API KEY !!
        "interface":        "wlan1",               # Pi interface facing Pineapple
        "ssid":             "HexBox-Pine",         # Management SSID
    },

    # --- Shark Jack ---
    # SharkJack creates 172.16.24.1 when connected via USB-C ethernet
    "sharkjack": {
        "enabled":          True,
        "ip":               "172.16.24.1",         # !! CHANGE IF DIFFERENT !!
        "ssh_port":         22,
        "ssh_user":         "root",
        "ssh_key":          "/home/pi/.ssh/sharkjack_rsa",  # !! SET KEY PATH !!
        "interface":        "eth1",                # Pi interface facing SharkJack
    },

    # --- Packet Squirrel ---
    # Squirrel default IP when in arming mode
    "squirrel": {
        "enabled":          True,
        "ip":               "172.16.32.1",         # !! CHANGE IF DIFFERENT !!
        "ssh_port":         22,
        "ssh_user":         "root",
        "ssh_key":          "/home/pi/.ssh/squirrel_rsa",   # !! SET KEY PATH !!
        "interface":        "eth2",                # Pi interface facing Squirrel
    },

    # --- LAN Turtle ---
    # Turtle default IP in arming mode
    "turtle": {
        "enabled":          True,
        "ip":               "172.16.84.1",         # !! CHANGE IF DIFFERENT !!
        "ssh_port":         22,
        "ssh_user":         "root",
        "ssh_key":          "/home/pi/.ssh/turtle_rsa",     # !! SET KEY PATH !!
        "interface":        "eth3",                # Pi interface facing Turtle
    },

    # --- OMG Plug ---
    # OMG connects back to HexBox over WiFi
    "omg": {
        "enabled":          True,
        "callback_ip":      "10.0.0.1",            # HexBox IP OMG calls back to
        "callback_port":    8443,                  # Callback listener port
        "wifi_ssid":        "HexBox-OMG",          # WiFi SSID OMG connects to
        "wifi_pass":        "YOUR_OMG_WIFI_PASS",  # !! SET WIFI PASSWORD !!
    },

    # --- C2 / External ---
    "c2": {
        "enabled":          True,
        "external_ip":      "YOUR.C2.IP.HERE",     # !! SET YOUR C2 SERVER IP !!
        "external_port":    443,                   # C2 listener port
        "protocol":         "https",               # http or https
        "tor_enabled":      False,                 # Route through Tor
        "tor_proxy":        "socks5://127.0.0.1:9050",
        "vpn_interface":    "tun0",                # VPN tunnel interface name
    },

    # --- Required Services ---
    "services": [
        "ssh",
        "tor",
        "nginx",
        "hexbox-dashboard",   # Systemd service name for Flask dashboard
    ],

    # --- Required Tools ---
    "tools": [
        "nmap",
        "responder",
        "tcpdump",
        "aircrack-ng",
        "hashcat",
        "hydra",
        "curl",
        "gpg",
        "ssh",
        "macchanger",
        "python3",
        "pip3",
    ],

    # --- Required Python Packages ---
    "python_packages": [
        "flask",
        "requests",
        "paramiko",
        "colorama",
        "scapy",
        "impacket",
    ],

    # --- Loot Subdirectories ---
    "loot_dirs": [
        "pcaps",
        "handshakes",
        "creds",
        "screenshots",
        "nmap",
        "hashes",
        "exfil",
    ],
}

# =============================================================================
# GLOBALS
# =============================================================================

init(autoreset=True)  # Colorama

PASS  = f"{Fore.GREEN}[  PASS  ]{Style.RESET_ALL}"
FAIL  = f"{Fore.RED}[  FAIL  ]{Style.RESET_ALL}"
WARN  = f"{Fore.YELLOW}[  WARN  ]{Style.RESET_ALL}"
INFO  = f"{Fore.CYAN}[  INFO  ]{Style.RESET_ALL}"
SKIP  = f"{Fore.WHITE}[  SKIP  ]{Style.RESET_ALL}"

results = {
    "passed":  [],
    "failed":  [],
    "warned":  [],
    "skipped": [],
}

start_time = datetime.now()

# =============================================================================
# HELPERS
# =============================================================================

def banner():
    print(f"""
{Fore.RED}
██╗  ██╗███████╗██╗  ██╗██████╗  ██████╗ ██╗  ██╗
██║  ██║██╔════╝╚██╗██╔╝██╔══██╗██╔═══██╗╚██╗██╔╝
███████║█████╗   ╚███╔╝ ██████╔╝██║   ██║ ╚███╔╝ 
██╔══██║██╔══╝   ██╔██╗ ██╔══██╗██║   ██║ ██╔██╗ 
██║  ██║███████╗██╔╝ ██╗██████╔╝╚██████╔╝██╔╝ ██╗
╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚═════╝  ╚═════╝ ╚═╝  ╚═╝
{Style.RESET_ALL}
{Fore.WHITE}         PRE-FLIGHT VALIDATION SYSTEM{Style.RESET_ALL}
{Fore.RED}         !! AUTHORIZED USE ONLY !!{Style.RESET_ALL}
{Fore.WHITE}         {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{Style.RESET_ALL}
    """)


def section(title):
    print(f"\n{Fore.YELLOW}{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}{Style.RESET_ALL}")


def log_result(status, check, detail=""):
    detail_str = f" — {detail}" if detail else ""
    if status == "PASS":
        print(f"  {PASS} {check}{detail_str}")
        results["passed"].append(check)
    elif status == "FAIL":
        print(f"  {FAIL} {check}{detail_str}")
        results["failed"].append(check)
    elif status == "WARN":
        print(f"  {WARN} {check}{detail_str}")
        results["warned"].append(check)
    elif status == "SKIP":
        print(f"  {SKIP} {check}{detail_str}")
        results["skipped"].append(check)
    else:
        print(f"  {INFO} {check}{detail_str}")


def ping_host(ip, count=2, timeout=2):
    """Returns True if host responds to ping."""
    try:
        result = subprocess.run(
            ["ping", "-c", str(count), "-W", str(timeout), ip],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return result.returncode == 0
    except Exception:
        return False


def check_port(ip, port, timeout=3):
    """Returns True if TCP port is open."""
    try:
        sock = socket.create_connection((ip, port), timeout=timeout)
        sock.close()
        return True
    except Exception:
        return False


def check_service(service):
    """Returns True if systemd service is active."""
    try:
        result = subprocess.run(
            ["systemctl", "is-active", "--quiet", service]
        )
        return result.returncode == 0
    except Exception:
        return False


def check_tool(tool):
    """Returns True if tool exists in PATH."""
    return shutil.which(tool) is not None


def check_python_package(package):
    """Returns True if Python package is importable."""
    try:
        result = subprocess.run(
            [sys.executable, "-c", f"import {package}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return result.returncode == 0
    except Exception:
        return False


def check_ssh(ip, port, user, key_path, timeout=5):
    """Returns True if SSH connection succeeds."""
    try:
        import paramiko
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            hostname=ip,
            port=port,
            username=user,
            key_filename=key_path,
            timeout=timeout,
            banner_timeout=timeout,
        )
        client.close()
        return True
    except Exception:
        return False


def get_interface_ip(interface):
    """Returns IP of a network interface."""
    try:
        result = subprocess.run(
            ["ip", "-4", "addr", "show", interface],
            capture_output=True, text=True
        )
        for line in result.stdout.split("\n"):
            if "inet " in line:
                return line.strip().split()[1].split("/")[0]
        return None
    except Exception:
        return None


def check_internet(host="8.8.8.8", port=53, timeout=3):
    """Check internet connectivity."""
    try:
        s = socket.create_connection((host, port), timeout=timeout)
        s.close()
        return True
    except Exception:
        return False


def check_placeholder(value, placeholder):
    """Warn if a config value is still a placeholder."""
    return value == placeholder or value.startswith("YOUR")


# =============================================================================
# CHECK FUNCTIONS
# =============================================================================

def check_root():
    section("PERMISSIONS CHECK")
    if os.geteuid() == 0:
        log_result("PASS", "Running as root")
    else:
        log_result("FAIL", "Not running as root",
                   "Run: sudo python3 preflight.py")


def check_config_placeholders():
    section("CONFIGURATION VALIDATION")

    checks = [
        ("Pineapple API Key",    CONFIG["pineapple"]["api_key"],     "YOUR_PINEAPPLE_API_KEY"),
        ("SharkJack SSH Key",    CONFIG["sharkjack"]["ssh_key"],      "/home/pi/.ssh/sharkjack_rsa"),
        ("Squirrel SSH Key",     CONFIG["squirrel"]["ssh_key"],       "/home/pi/.ssh/squirrel_rsa"),
        ("Turtle SSH Key",       CONFIG["turtle"]["ssh_key"],         "/home/pi/.ssh/turtle_rsa"),
        ("OMG WiFi Password",    CONFIG["omg"]["wifi_pass"],          "YOUR_OMG_WIFI_PASS"),
        ("C2 External IP",       CONFIG["c2"]["external_ip"],         "YOUR.C2.IP.HERE"),
        ("GPG Key ID",           CONFIG["hexbox"]["gpg_key_id"],      "YOUR_GPG_KEY_ID"),
    ]

    for name, value, placeholder in checks:
        if check_placeholder(value, placeholder):
            log_result("FAIL", f"{name} not configured",
                       f"Edit CONFIG in preflight.py — still set to placeholder")
        else:
            log_result("PASS", f"{name} configured")


def check_loot_dirs():
    section("LOOT DIRECTORY STRUCTURE")

    base = CONFIG["hexbox"]["loot_dir"]
    log_dir = CONFIG["hexbox"]["log_dir"]

    for d in [base, log_dir]:
        if os.path.exists(d):
            log_result("PASS", f"Directory exists: {d}")
        else:
            try:
                os.makedirs(d, exist_ok=True)
                log_result("WARN", f"Created missing directory: {d}")
            except Exception as e:
                log_result("FAIL", f"Cannot create directory: {d}", str(e))

    for subdir in CONFIG["loot_dirs"]:
        path = os.path.join(base, subdir)
        if os.path.exists(path):
            log_result("PASS", f"Loot subdir: {subdir}/")
        else:
            try:
                os.makedirs(path, exist_ok=True)
                log_result("WARN", f"Created loot subdir: {subdir}/")
            except Exception as e:
                log_result("FAIL", f"Cannot create loot subdir: {subdir}/", str(e))


def check_tools_installed():
    section("REQUIRED TOOLS")

    for tool in CONFIG["tools"]:
        if check_tool(tool):
            log_result("PASS", f"Tool found: {tool}")
        else:
            log_result("FAIL", f"Tool missing: {tool}",
                       f"Install with: sudo apt install {tool}")


def check_python_packages():
    section("PYTHON PACKAGES")

    # Map import names to pip names where they differ
    import_map = {
        "flask":    "flask",
        "requests": "requests",
        "paramiko": "paramiko",
        "colorama": "colorama",
        "scapy":    "scapy",
        "impacket": "impacket",
    }

    for package, pip_name in import_map.items():
        if check_python_package(package):
            log_result("PASS", f"Package found: {package}")
        else:
            log_result("FAIL", f"Package missing: {package}",
                       f"Install with: pip3 install {pip_name}")


def check_services_running():
    section("SYSTEM SERVICES")

    for service in CONFIG["services"]:
        if check_service(service):
            log_result("PASS", f"Service active: {service}")
        else:
            log_result("WARN", f"Service not active: {service}",
                       f"Start with: sudo systemctl start {service}")


def check_network_interfaces():
    section("NETWORK INTERFACES")

    interfaces = [
        CONFIG["hexbox"]["mgmt_interface"],
        CONFIG["pineapple"]["interface"],
        CONFIG["sharkjack"]["interface"],
        CONFIG["squirrel"]["interface"],
        CONFIG["turtle"]["interface"],
    ]

    for iface in interfaces:
        ip = get_interface_ip(iface)
        if ip:
            log_result("PASS", f"Interface {iface} is up", f"IP: {ip}")
        else:
            log_result("WARN", f"Interface {iface} has no IP or is down",
                       "Check USB hub / device connections")


def check_pineapple():
    section("WIFI PINEAPPLE")

    if not CONFIG["pineapple"]["enabled"]:
        log_result("SKIP", "Pineapple disabled in config")
        return

    ip   = CONFIG["pineapple"]["ip"]
    port = CONFIG["pineapple"]["api_port"]

    # Ping check
    if ping_host(ip):
        log_result("PASS", f"Pineapple reachable", f"ICMP ping to {ip}")
    else:
        log_result("FAIL", f"Pineapple unreachable",
                   f"Cannot ping {ip} — check connection to Pineapple AP")
        return

    # Port check
    if check_port(ip, port):
        log_result("PASS", f"Pineapple API port open", f"{ip}:{port}")
    else:
        log_result("FAIL", f"Pineapple API port closed", f"{ip}:{port}")
        return

    # API key check
    if check_placeholder(CONFIG["pineapple"]["api_key"], "YOUR_PINEAPPLE_API_KEY"):
        log_result("FAIL", "Pineapple API key not set")
        return

    # Live API call
    try:
        url = f"http://{ip}:{port}/api/system/info"
        headers = {"Authorization": f"Bearer {CONFIG['pineapple']['api_key']}"}
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            fw = data.get("firmware_version", "unknown")
            log_result("PASS", f"Pineapple API responding", f"Firmware: {fw}")
        else:
            log_result("WARN", f"Pineapple API returned {resp.status_code}",
                       "Check API key in CONFIG")
    except Exception as e:
        log_result("FAIL", "Pineapple API call failed", str(e))


def check_sharkjack():
    section("SHARK JACK")

    if not CONFIG["sharkjack"]["enabled"]:
        log_result("SKIP", "SharkJack disabled in config")
        return

    ip      = CONFIG["sharkjack"]["ip"]
    port    = CONFIG["sharkjack"]["ssh_port"]
    user    = CONFIG["sharkjack"]["ssh_user"]
    key     = CONFIG["sharkjack"]["ssh_key"]

    if ping_host(ip):
        log_result("PASS", f"SharkJack reachable", f"ICMP ping to {ip}")
    else:
        log_result("FAIL", f"SharkJack unreachable",
                   f"Cannot ping {ip} — is it plugged into USB hub?")
        return

    if check_port(ip, port):
        log_result("PASS", f"SharkJack SSH port open", f"{ip}:{port}")
    else:
        log_result("FAIL", f"SharkJack SSH port closed", f"{ip}:{port}")
        return

    if not os.path.exists(key):
        log_result("FAIL", f"SharkJack SSH key not found", f"Path: {key}")
        return

    if check_ssh(ip, port, user, key):
        log_result("PASS", "SharkJack SSH authentication successful")
    else:
        log_result("FAIL", "SharkJack SSH authentication failed",
                   "Check SSH key path and permissions (chmod 600)")


def check_squirrel():
    section("PACKET SQUIRREL")

    if not CONFIG["squirrel"]["enabled"]:
        log_result("SKIP", "Packet Squirrel disabled in config")
        return

    ip   = CONFIG["squirrel"]["ip"]
    port = CONFIG["squirrel"]["ssh_port"]
    user = CONFIG["squirrel"]["ssh_user"]
    key  = CONFIG["squirrel"]["ssh_key"]

    if ping_host(ip):
        log_result("PASS", f"Packet Squirrel reachable", f"ICMP ping to {ip}")
    else:
        log_result("FAIL", f"Packet Squirrel unreachable",
                   f"Cannot ping {ip} — set switch to ARMING position")
        return

    if check_port(ip, port):
        log_result("PASS", f"Packet Squirrel SSH port open", f"{ip}:{port}")
    else:
        log_result("FAIL", f"Packet Squirrel SSH port closed", f"{ip}:{port}")
        return

    if not os.path.exists(key):
        log_result("FAIL", f"Packet Squirrel SSH key not found", f"Path: {key}")
        return

    if check_ssh(ip, port, user, key):
        log_result("PASS", "Packet Squirrel SSH authentication successful")
    else:
        log_result("FAIL", "Packet Squirrel SSH authentication failed",
                   "Check SSH key path and permissions (chmod 600)")


def check_turtle():
    section("LAN TURTLE")

    if not CONFIG["turtle"]["enabled"]:
        log_result("SKIP", "LAN Turtle disabled in config")
        return

    ip   = CONFIG["turtle"]["ip"]
    port = CONFIG["turtle"]["ssh_port"]
    user = CONFIG["turtle"]["ssh_user"]
    key  = CONFIG["turtle"]["ssh_key"]

    if ping_host(ip):
        log_result("PASS", f"LAN Turtle reachable", f"ICMP ping to {ip}")
    else:
        log_result("FAIL", f"LAN Turtle unreachable",
                   f"Cannot ping {ip} — check USB connection")
        return

    if check_port(ip, port):
        log_result("PASS", f"LAN Turtle SSH port open", f"{ip}:{port}")
    else:
        log_result("FAIL", f"LAN Turtle SSH port closed", f"{ip}:{port}")
        return

    if not os.path.exists(key):
        log_result("FAIL", f"LAN Turtle SSH key not found", f"Path: {key}")
        return

    if check_ssh(ip, port, user, key):
        log_result("PASS", "LAN Turtle SSH authentication successful")
    else:
        log_result("FAIL", "LAN Turtle SSH authentication failed",
                   "Check SSH key path and permissions (chmod 600)")


def check_omg():
    section("OMG PLUG")

    if not CONFIG["omg"]["enabled"]:
        log_result("SKIP", "OMG Plug disabled in config")
        return

    cb_ip   = CONFIG["omg"]["callback_ip"]
    cb_port = CONFIG["omg"]["callback_port"]
    wifi    = CONFIG["omg"]["wifi_ssid"]
    passwd  = CONFIG["omg"]["wifi_pass"]

    # Check our own listener port is open
    if check_port(cb_ip, cb_port):
        log_result("PASS", f"OMG callback listener active", f"{cb_ip}:{cb_port}")
    else:
        log_result("WARN", f"OMG callback port not listening", 
                   f"Start listener on {cb_ip}:{cb_port} before deploying OMG")

    if check_placeholder(passwd, "YOUR_OMG_WIFI_PASS"):
        log_result("FAIL", "OMG WiFi password not configured",
                   "Set wifi_pass in CONFIG")
    else:
        log_result("PASS", f"OMG WiFi configured", f"SSID: {wifi}")


def check_c2():
    section("C2 CONNECTIVITY")

    if not CONFIG["c2"]["enabled"]:
        log_result("SKIP", "C2 disabled in config")
        return

    ext_ip   = CONFIG["c2"]["external_ip"]
    ext_port = CONFIG["c2"]["external_port"]
    proto    = CONFIG["c2"]["protocol"]

    if check_placeholder(ext_ip, "YOUR.C2.IP.HERE"):
        log_result("FAIL", "C2 external IP not configured",
                   "Set external_ip in CONFIG c2 section")
        return

    # Internet connectivity
    if check_internet():
        log_result("PASS", "Internet connectivity confirmed")
    else:
        log_result("FAIL", "No internet connectivity",
                   "Check VPN / Tor / network routing")
        return

    # VPN check
    vpn_iface = CONFIG["c2"]["vpn_interface"]
    vpn_ip    = get_interface_ip(vpn_iface)
    if vpn_ip:
        log_result("PASS", f"VPN tunnel active", f"{vpn_iface} → {vpn_ip}")
    else:
        log_result("WARN", f"VPN tunnel ({vpn_iface}) not detected",
                   "Consider routing traffic through VPN for OPSEC")

    # Tor check
    if CONFIG["c2"]["tor_enabled"]:
        if check_port("127.0.0.1", 9050):
            log_result("PASS", "Tor SOCKS proxy reachable", "127.0.0.1:9050")
        else:
            log_result("FAIL", "Tor SOCKS proxy not available",
                       "sudo systemctl start tor")

    # C2 server reachability
    if check_port(ext_ip, ext_port):
        log_result("PASS", f"C2 server reachable", f"{proto}://{ext_ip}:{ext_port}")
    else:
        log_result("FAIL", f"C2 server unreachable",
                   f"Cannot reach {ext_ip}:{ext_port} — check firewall / listener")


def check_gpg():
    section("ENCRYPTION / GPG")

    if check_tool("gpg"):
        log_result("PASS", "GPG installed")
    else:
        log_result("FAIL", "GPG not installed", "sudo apt install gpg")
        return

    key_id = CONFIG["hexbox"]["gpg_key_id"]
    if check_placeholder(key_id, "YOUR_GPG_KEY_ID"):
        log_result("FAIL", "GPG key ID not configured",
                   "Generate a key: gpg --full-generate-key")
        return

    try:
        result = subprocess.run(
            ["gpg", "--list-keys", key_id],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            log_result("PASS", f"GPG key found", f"Key ID: {key_id}")
        else:
            log_result("FAIL", f"GPG key not found",
                       f"Import or generate key: {key_id}")
    except Exception as e:
        log_result("FAIL", "GPG key check failed", str(e))


def check_opsec():
    section("OPSEC POSTURE")

    # Bash history disabled
    histfile = os.environ.get("HISTFILE", "")
    histsize = os.environ.get("HISTSIZE", "1000")
    if histfile == "" and histsize == "0":
        log_result("PASS", "Bash history suppressed")
    else:
        log_result("WARN", "Bash history may be active",
                   "Run: unset HISTFILE && export HISTSIZE=0")

    # Hostname check
    try:
        current_hostname = socket.gethostname()
        expected         = CONFIG["hexbox"]["hostname"]
        if current_hostname == expected:
            log_result("PASS", f"Hostname spoofed", f"{current_hostname}")
        else:
            log_result("WARN", f"Hostname not spoofed",
                       f"Current: {current_hostname} | Expected: {expected}")
    except Exception:
        log_result("WARN", "Could not verify hostname")

    # MAC address randomization check (basic)
    try:
        result = subprocess.run(
            ["macchanger", "-s", CONFIG["hexbox"]["mgmt_interface"]],
            capture_output=True, text=True
        )
        if "Permanent" in result.stdout and "Current" in result.stdout:
            lines = result.stdout.strip().split("\n")
            perm  = [l for l in lines if "Permanent" in l]
            curr  = [l for l in lines if "Current" in l]
            if perm and curr:
                perm_mac = perm[0].split()[-1]
                curr_mac  = curr[0].split()[-1]
                if perm_mac != curr_mac:
                    log_result("PASS", "MAC address randomized",
                               f"{CONFIG['hexbox']['mgmt_interface']}: {curr_mac}")
                else:
                    log_result("WARN", "MAC not randomized",
                               "Run: scripts/opsec.sh")
    except Exception:
        log_result("WARN", "Could not verify MAC randomization",
                   "Ensure macchanger is installed")

    # Check UFW / iptables for dashboard port exposure
    try:
        result = subprocess.run(
            ["ufw", "status"],
            capture_output=True, text=True
        )
        if "active" in result.stdout.lower():
            log_result("PASS", "UFW firewall is active")
        else:
            log_result("WARN", "UFW firewall is inactive",
                       "Run: sudo ufw enable")
    except Exception:
        log_result("WARN", "Could not check UFW status")


# =============================================================================
# SUMMARY REPORT
# =============================================================================

def print_summary():
    elapsed = (datetime.now() - start_time).seconds

    total   = (len(results["passed"]) + len(results["failed"]) +
               len(results["warned"]) + len(results["skipped"]))

    print(f"\n{Fore.YELLOW}{'='*60}")
    print(f"  PREFLIGHT SUMMARY")
    print(f"{'='*60}{Style.RESET_ALL}")
    print(f"  {Fore.GREEN}PASSED : {len(results['passed'])}{Style.RESET_ALL}")
    print(f"  {Fore.RED}FAILED : {len(results['failed'])}{Style.RESET_ALL}")
    print(f"  {Fore.YELLOW}WARNED : {len(results['warned'])}{Style.RESET_ALL}")
    print(f"  {Fore.WHITE}SKIPPED: {len(results['skipped'])}{Style.RESET_ALL}")
    print(f"  TOTAL  : {total}")
    print(f"  TIME   : {elapsed}s")
    print(f"{Fore.YELLOW}{'='*60}{Style.RESET_ALL}")

    # Save report to log dir
    report_path = os.path.join(
        CONFIG["hexbox"]["log_dir"],
        f"preflight_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    try:
        os.makedirs(CONFIG["hexbox"]["log_dir"], exist_ok=True)
        with open(report_path, "w") as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "results":   results,
                "config_snapshot": {
                    "pineapple_ip":  CONFIG["pineapple"]["ip"],
                    "sharkjack_ip":  CONFIG["sharkjack"]["ip"],
                    "squirrel_ip":   CONFIG["squirrel"]["ip"],
                    "turtle_ip":     CONFIG["turtle"]["ip"],
                    "c2_ip":         CONFIG["c2"]["external_ip"],
                },
            }, f, indent=2)
        print(f"\n  {INFO} Report saved to: {report_path}")
    except Exception as e:
        print(f"\n  {WARN} Could not save report: {e}")

    # Go / No-Go decision
    if len(results["failed"]) == 0:
        print(f"""
{Fore.GREEN}
  ██████╗  ██████╗     ██╗     ██╗██╗   ██╗███████╗
 ██╔════╝ ██╔═══██╗   ██║     ██║██║   ██║██╔════╝
 ██║  ███╗██║   ██║   ██║     ██║██║   ██║█████╗  
 ██║   ██║██║   ██║   ██║     ██║╚██╗ ██╔╝██╔══╝  
 ╚██████╔╝╚██████╔╝   ███████╗██║ ╚████╔╝ ███████╗
  ╚═════╝  ╚═════╝    ╚══════╝╚═╝  ╚═══╝  ╚══════╝
  HexBox is GO for deployment. Stay authorized.
{Style.RESET_ALL}""")
    else:
        print(f"""
{Fore.RED}
 ███╗   ██╗ ██████╗      ██████╗  ██████╗ 
 ████╗  ██║██╔═══██╗    ██╔════╝ ██╔═══██╗
 ██╔██╗ ██║██║   ██║    ██║  ███╗██║   ██║
 ██║╚██╗██║██║   ██║    ██║   ██║██║   ██║
 ██║ ╚████║╚██████╔╝    ╚██████╔╝╚██████╔╝
 ╚═╝  ╚═══╝ ╚═════╝      ╚═════╝  ╚═════╝
  {len(results['failed'])} check(s) FAILED. Fix before deployment.
{Style.RESET_ALL}""")

        print(f"{Fore.RED}  Failed checks:{Style.RESET_ALL}")
        for item in results["failed"]:
            print(f"    {Fore.RED}✗{Style.RESET_ALL} {item}")


# =============================================================================
# CONFIG BRIDGE — overlay config.json values onto CONFIG dict
# =============================================================================

def _apply_config_json():
    """Read config.json (if present) and overlay its values onto CONFIG."""
    cfg_path = os.path.join(os.path.dirname(__file__), "..", "config.json")
    cfg_path = os.path.abspath(cfg_path)
    if not os.path.exists(cfg_path):
        return
    try:
        with open(cfg_path) as f:
            c = json.load(f)
    except Exception:
        return

    hb = c.get("hexbox", {})
    if hb.get("ip"):
        CONFIG["hexbox"]["mgmt_ip"] = hb["ip"]
    if hb.get("dashboard_port"):
        CONFIG["hexbox"]["dashboard_port"] = hb["dashboard_port"]
    if hb.get("loot_dir"):
        CONFIG["hexbox"]["loot_dir"] = os.path.expanduser(hb["loot_dir"])
    if hb.get("log_dir"):
        CONFIG["hexbox"]["log_dir"] = os.path.expanduser(hb["log_dir"])

    devmap = {
        "pineapple":      "pineapple",
        "sharkjack":      "sharkjack",
        "packetsquirrel": "squirrel",
        "lanturtle":      "turtle",
        "omgplug":        "omg",
    }
    for cfg_key, local_key in devmap.items():
        dev = c.get("devices", {}).get(cfg_key, {})
        if dev.get("ip") and local_key in CONFIG:
            CONFIG[local_key]["ip"] = dev["ip"]

    c2 = c.get("c2", {})
    if c2.get("external_ip"):
        CONFIG["c2"]["external_ip"] = c2["external_ip"]
    if c2.get("port"):
        CONFIG["c2"]["external_port"] = c2["port"]


# =============================================================================
# MAIN
# =============================================================================

def main():
    _apply_config_json()
    banner()

    print(f"{INFO} Starting preflight checks...")
    print(f"{WARN} Ensure all Hak5 devices are connected before running\n")

    # Run all checks
    check_root()
    check_config_placeholders()
    check_loot_dirs()
    check_tools_installed()
    check_python_packages()
    check_services_running()
    check_network_interfaces()
    check_pineapple()
    check_sharkjack()
    check_squirrel()
    check_turtle()
    check_omg()
    check_c2()
    check_gpg()
    check_opsec()

    print_summary()


if __name__ == "__main__":
    main()
