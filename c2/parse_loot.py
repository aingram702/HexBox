#!/usr/bin/env python3
# ~/hexbox/c2/parse_loot.py — Loot intelligence: parsing, aggregation, reporting

import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

def parse_responder_hashes(log_path: Path) -> list[dict]:
    """Extract NTLMv1/NTLMv2 hashes from a Responder log or output file."""
    hashes: list[dict] = []
    if not log_path.exists():
        return hashes

    ntlmv2_re = re.compile(
        r'([^:\s]+)::([^:\s]*):([0-9a-fA-F]{16}):([0-9a-fA-F]{32}):([0-9a-fA-F]+)',
        re.IGNORECASE,
    )
    ntlmv1_re = re.compile(
        r'([^:\s]+)::([^:\s]*):([0-9a-fA-F]{32}):([0-9a-fA-F]{32}):([0-9a-fA-F]{16})',
        re.IGNORECASE,
    )
    try:
        mtime = datetime.fromtimestamp(log_path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
    except OSError:
        mtime = ""

    seen: set[str] = set()
    for line in log_path.read_text(errors="replace").splitlines():
        m2 = ntlmv2_re.search(line)
        if m2:
            user, domain, chall, hmac, blob = m2.groups()
            h = f"{user}::{domain}:{chall}:{hmac}:{blob}"
            if h not in seen:
                seen.add(h)
                hashes.append({"type": "NTLMv2", "user": user,
                                "domain": domain, "hash": h,
                                "ts": mtime, "source": log_path.name})
            continue
        m1 = ntlmv1_re.search(line)
        if m1:
            user, domain, lm, nt, chall = m1.groups()
            h = f"{user}::{domain}:{lm}:{nt}:{chall}"
            if h not in seen:
                seen.add(h)
                hashes.append({"type": "NTLMv1", "user": user,
                                "domain": domain, "hash": h,
                                "ts": mtime, "source": log_path.name})
    return hashes


def parse_wifi_profiles(file_path: Path) -> list[dict]:
    """Parse WiFi credentials from netsh wlan show profile ... key=clear output."""
    profiles: list[dict] = []
    if not file_path.exists():
        return profiles

    current_ssid = None
    for line in file_path.read_text(errors="replace").splitlines():
        ssid_m = re.match(r'\[(.+)\]$', line.strip())
        if ssid_m:
            current_ssid = ssid_m.group(1)
            continue
        key_m = re.search(r'Key Content\s*:\s*(.+)', line)
        if key_m and current_ssid:
            profiles.append({
                "ssid":     current_ssid,
                "password": key_m.group(1).strip(),
                "source":   file_path.name,
            })
    return profiles


def parse_nmap_xml(xml_path: Path) -> list[dict]:
    """Parse nmap XML (-oX) output into structured host/port/service dicts."""
    if not xml_path.exists():
        return []
    try:
        root = ET.parse(str(xml_path)).getroot()
    except ET.ParseError:
        return []

    hosts = []
    for host in root.findall("host"):
        st = host.find("status")
        if st is None or st.get("state") != "up":
            continue

        addr_el = host.find("address[@addrtype='ipv4']") or host.find("address")
        ip = addr_el.get("addr", "?") if addr_el is not None else "?"

        hostname = ""
        for hn in host.findall("hostnames/hostname"):
            hostname = hn.get("name", "")
            if hostname:
                break

        os_str = ""
        for om in host.findall("os/osmatch"):
            os_str = f"{om.get('name','')} ({om.get('accuracy','')}%)"
            break

        ports = []
        for port in host.findall("ports/port"):
            pstate = port.find("state")
            if pstate is None or pstate.get("state") != "open":
                continue
            svc = port.find("service")
            ports.append({
                "port":    int(port.get("portid", 0)),
                "proto":   port.get("protocol", "tcp"),
                "service": svc.get("name", "")    if svc is not None else "",
                "product": svc.get("product", "") if svc is not None else "",
                "version": svc.get("version", "") if svc is not None else "",
            })
        ports.sort(key=lambda p: p["port"])

        hosts.append({
            "ip":         ip,
            "hostname":   hostname,
            "os":         os_str,
            "role":       _guess_role({p["port"] for p in ports}),
            "ports":      ports,
            "open_count": len(ports),
        })

    hosts.sort(key=lambda h: _ip_sort_key(h["ip"]))
    return hosts


def parse_sysinfo(file_path: Path) -> dict | None:
    """Parse JSON sysinfo dump from sysinfo.ps1."""
    if not file_path.exists():
        return None
    try:
        return json.loads(file_path.read_text(errors="replace"))
    except (json.JSONDecodeError, OSError):
        return None


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def aggregate_intel(loot_dir: Path, log_dir: Path) -> dict:
    """Collect and deduplicate all parsed intel from loot + log directories."""
    hashes:   list[dict] = []
    wifi:     list[dict] = []
    hosts:    list[dict] = []
    chrome:   list[dict] = []
    sysinfos: list[dict] = []

    creds_dir = loot_dir / "creds"
    if creds_dir.exists():
        for f in sorted(creds_dir.glob("*_wifi.txt")):
            for p in parse_wifi_profiles(f):
                p["host"] = f.stem.replace("_wifi", "")
                wifi.append(p)
        for f in sorted(creds_dir.glob("*_chrome.db")):
            st = f.stat()
            chrome.append({
                "file":     f.name,
                "size_kb":  round(st.st_size / 1024, 1),
                "captured": datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M"),
            })
        for f in sorted(creds_dir.glob("*_sysinfo.json")):
            d = parse_sysinfo(f)
            if d:
                sysinfos.append(d)

    # Responder logs — check multiple possible locations
    resp_dirs = [
        log_dir,
        Path("/usr/share/responder/logs"),
        Path("/opt/Responder/logs"),
    ]
    seen_hashes: set[str] = set()
    for d in resp_dirs:
        if not d.exists():
            continue
        for f in sorted(d.glob("*.log")) + sorted(d.glob("*.txt")):
            for h in parse_responder_hashes(f):
                if h["hash"] not in seen_hashes:
                    seen_hashes.add(h["hash"])
                    hashes.append(h)

    # nmap XML output
    seen_ips: set[str] = set()
    nmap_dir = loot_dir / "nmap"
    if nmap_dir.exists():
        for xml in sorted(nmap_dir.glob("*.xml")):
            for host in parse_nmap_xml(xml):
                if host["ip"] not in seen_ips:
                    seen_ips.add(host["ip"])
                    hosts.append(host)

    return {
        "hashes":   hashes,
        "wifi":     wifi,
        "hosts":    hosts,
        "chrome":   chrome,
        "sysinfos": sysinfos,
        "summary": {
            "hash_count":   len(hashes),
            "wifi_count":   len(wifi),
            "host_count":   len(hosts),
            "chrome_count": len(chrome),
        },
    }


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def generate_html_report(intel: dict, meta: dict) -> str:
    """Return a self-contained HTML engagement report."""

    def h(s: str) -> str:
        return (str(s)
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;"))

    def hash_rows() -> str:
        if not intel["hashes"]:
            return '<tr><td colspan="5" class="empty">No hashes captured</td></tr>'
        return "\n".join(
            f"<tr><td>{h(x['ts'])}</td><td>{h(x['type'])}</td>"
            f"<td>{h(x['domain'])}</td><td>{h(x['user'])}</td>"
            f"<td class='mono small'>{h(x['hash'])}</td></tr>"
            for x in intel["hashes"]
        )

    def wifi_rows() -> str:
        if not intel["wifi"]:
            return '<tr><td colspan="3" class="empty">No WiFi profiles captured</td></tr>'
        return "\n".join(
            f"<tr><td>{h(w.get('host','?'))}</td>"
            f"<td>{h(w['ssid'])}</td><td class='mono'>{h(w['password'])}</td></tr>"
            for w in intel["wifi"]
        )

    def host_rows() -> str:
        if not intel["hosts"]:
            return '<tr><td colspan="6" class="empty">No hosts discovered</td></tr>'
        rows = []
        for hst in intel["hosts"]:
            ps = ", ".join(
                f"{p['port']}/{p['proto']} {p['service']}" for p in hst["ports"][:12]
            )
            rows.append(
                f"<tr><td>{h(hst['ip'])}</td><td>{h(hst['hostname'])}</td>"
                f"<td><span class='badge'>{h(hst['role'])}</span></td>"
                f"<td class='small'>{h(hst['os'][:50])}</td>"
                f"<td>{hst['open_count']}</td>"
                f"<td class='small mono'>{h(ps)}</td></tr>"
            )
        return "\n".join(rows)

    def chrome_rows() -> str:
        if not intel["chrome"]:
            return '<tr><td colspan="3" class="empty">No Chrome DBs captured</td></tr>'
        return "\n".join(
            f"<tr><td>{h(c['captured'])}</td><td>{h(c['file'])}</td>"
            f"<td>{c['size_kb']} KB</td></tr>"
            for c in intel["chrome"]
        )

    s = intel["summary"]
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    eng_name = h(meta.get("name", "Unnamed"))
    target   = h(meta.get("target", "Unknown"))
    notes    = h(meta.get("notes", ""))

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>HexBox Report — {eng_name}</title>
<style>
body{{font-family:monospace;background:#0a0a0a;color:#ccc;padding:28px;margin:0;line-height:1.4}}
h1{{color:#0f0;border-bottom:2px solid #0f0;padding-bottom:10px;margin-bottom:4px}}
h2{{color:#ff0;margin-top:28px;font-size:1em}}
.meta{{color:#555;font-size:.82em;margin-bottom:20px}}
.stats{{display:flex;gap:16px;margin:18px 0}}
.stat{{border:1px solid #1a1a1a;padding:14px 22px;text-align:center;min-width:80px}}
.stat .num{{font-size:2.2em;color:#0f0;display:block}}
.stat .lbl{{color:#555;font-size:.75em}}
table{{width:100%;border-collapse:collapse;margin:8px 0 20px}}
th{{background:#111;color:#0f0;text-align:left;padding:7px 10px;font-size:.8em}}
td{{padding:6px 10px;border-bottom:1px solid #0d0d0d;font-size:.78em;vertical-align:top}}
tr:hover td{{background:#0d0d0d}}
.mono{{font-family:monospace;word-break:break-all}}
.small{{font-size:.72em;color:#777}}
.empty{{color:#444;font-style:italic}}
.badge{{background:#1a1a1a;border:1px solid #333;padding:1px 5px;font-size:.75em;
        color:#c00;white-space:nowrap}}
@media print{{body{{background:#fff;color:#000}} .stat .num{{color:#000}} h1,h2{{color:#000}}}}
</style></head><body>
<h1>&#x1F5A5; HexBox Engagement Report</h1>
<div class="meta">
  <b>Engagement:</b> {eng_name} &nbsp;|&nbsp;
  <b>Target:</b> {target} &nbsp;|&nbsp;
  <b>Generated:</b> {ts}
  {f'<br><b>Notes:</b> {notes}' if notes else ''}
</div>

<div class="stats">
  <div class="stat"><span class="num">{s['hash_count']}</span><span class="lbl">NTLM Hashes</span></div>
  <div class="stat"><span class="num">{s['wifi_count']}</span><span class="lbl">WiFi Creds</span></div>
  <div class="stat"><span class="num">{s['host_count']}</span><span class="lbl">Hosts Found</span></div>
  <div class="stat"><span class="num">{s['chrome_count']}</span><span class="lbl">Chrome DBs</span></div>
</div>

<h2>Network Map ({len(intel['hosts'])} hosts)</h2>
<table><tr><th>IP</th><th>Hostname</th><th>Role</th><th>OS</th><th>Open Ports</th><th>Services</th></tr>
{host_rows()}
</table>

<h2>NTLM Hashes ({len(intel['hashes'])})</h2>
<table><tr><th>Captured</th><th>Type</th><th>Domain</th><th>User</th><th>Hash</th></tr>
{hash_rows()}
</table>

<h2>WiFi Credentials ({len(intel['wifi'])})</h2>
<table><tr><th>Host</th><th>SSID</th><th>Password</th></tr>
{wifi_rows()}
</table>

<h2>Chrome Databases ({len(intel['chrome'])})</h2>
<table><tr><th>Captured</th><th>File</th><th>Size</th></tr>
{chrome_rows()}
</table>
</body></html>"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _guess_role(port_nums: set) -> str:
    if {88, 389} & port_nums or {88, 636} & port_nums:
        return "Domain Controller"
    if 445 in port_nums and 3389 in port_nums:
        return "Windows Workstation"
    if {445, 139} & port_nums:
        return "Windows Host"
    if {3306, 5432, 1433, 1521, 27017} & port_nums:
        return "Database"
    if {80, 443, 8080, 8443, 8000} & port_nums:
        return "Web Server"
    if {9100, 631, 515} & port_nums:
        return "Printer"
    if {23, 161} & port_nums:
        return "Network Device"
    if 22 in port_nums and len(port_nums) <= 3:
        return "Linux Host"
    return "Unknown"


def aggregate_bloodhound(loot_dir: Path) -> dict:
    """Scan loot/bloodhound/ for BloodHound JSON v5 files and return a summary."""
    bh_dir = loot_dir / "bloodhound"
    summary: list[dict] = []
    total_objects = 0
    if not bh_dir.exists():
        return {"summary": summary, "files": 0, "total_objects": 0}

    seen: dict[str, dict] = {}
    for jf in sorted(bh_dir.glob("*.json")):
        try:
            payload = json.loads(jf.read_text(errors="replace"))
        except (json.JSONDecodeError, OSError):
            continue
        meta = payload.get("meta", {})
        bh_type = meta.get("type", jf.stem.split("_")[-1])
        count = meta.get("count", len(payload.get("data", [])))
        domain = ""
        data = payload.get("data", [])
        if data and isinstance(data[0], dict):
            props = data[0].get("Properties", {})
            domain = props.get("domain", "")

        key = f"{bh_type}:{domain}"
        if key not in seen or jf.stat().st_mtime > seen[key]["_mtime"]:
            seen[key] = {
                "type":     bh_type,
                "count":    count,
                "domain":   domain,
                "captured": datetime.fromtimestamp(jf.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
                "file":     jf.name,
                "_mtime":   jf.stat().st_mtime,
            }
        total_objects += count

    for v in seen.values():
        v.pop("_mtime", None)
        summary.append(v)

    summary.sort(key=lambda x: x.get("type", ""))
    return {
        "summary":       summary,
        "files":         len(list(bh_dir.glob("*.json"))),
        "total_objects": total_objects,
    }


def _ip_sort_key(ip: str) -> tuple:
    try:
        return tuple(int(x) for x in ip.split("."))
    except ValueError:
        return (999, 999, 999, 999)
