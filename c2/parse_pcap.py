"""
parse_pcap.py — PCAP analysis module using tshark for HexBox C2.
Extracts credentials, DNS queries, HTTP requests, protocol stats, and host lists.
"""

import subprocess
import shutil
import re
import base64
from pathlib import Path
from datetime import datetime


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _run_tshark(args: list, timeout: int = 60) -> tuple[str, str, int]:
    """Run tshark with the given argument list. Returns (stdout, stderr, returncode)."""
    result = subprocess.run(
        ["tshark"] + args,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return result.stdout, result.stderr, result.returncode


def _parse_proto_hierarchy(output: str) -> dict:
    """
    Parse tshark -q -z io,phs output into {protocol: packet_count}.

    Example lines:
      eth                                      frames:1234 bytes:567890
        ip                                   frames:1100 bytes:543210
    """
    protocols: dict = {}
    for line in output.splitlines():
        m = re.search(r"(\w[\w.]*)\s+frames:(\d+)", line)
        if m:
            proto = m.group(1).lower()
            count = int(m.group(2))
            protocols[proto] = protocols.get(proto, 0) + count
    return protocols


def _parse_http_auth(output: str) -> list[dict]:
    """
    Parse tshark HTTP auth field output (ip.src, http.host, http.authorization).
    Decodes Base64 Basic auth into username/password.
    Returns list of credential dicts.
    """
    creds: list[dict] = []
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        src_ip = parts[0].strip()
        host = parts[1].strip()
        auth_header = parts[2].strip()

        if auth_header.lower().startswith("basic "):
            encoded = auth_header[6:].strip()
            try:
                decoded = base64.b64decode(encoded + "==").decode("utf-8", errors="replace")
                if ":" in decoded:
                    username, password = decoded.split(":", 1)
                else:
                    username, password = decoded, ""
            except Exception:
                username, password = encoded, ""
            creds.append({
                "type": "HTTP Basic",
                "src_ip": src_ip,
                "host": host,
                "username": username,
                "password": password,
            })
        elif auth_header.lower().startswith("digest "):
            # Extract username from Digest auth header
            m = re.search(r'username="([^"]+)"', auth_header, re.IGNORECASE)
            username = m.group(1) if m else ""
            creds.append({
                "type": "HTTP Digest",
                "src_ip": src_ip,
                "host": host,
                "username": username,
                "hash": auth_header,
            })
        else:
            creds.append({
                "type": "HTTP Auth",
                "src_ip": src_ip,
                "host": host,
                "username": "",
                "password": auth_header,
            })
    return creds


def _parse_ftp_creds(output: str) -> list[dict]:
    """
    Parse FTP USER/PASS pairs from tshark field output.
    Lines: ip.src, ftp.request.command, ftp.request.arg
    Pairs consecutive USER + PASS lines from the same source IP.
    """
    creds: list[dict] = []
    pending: dict = {}  # src_ip -> partial cred

    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        src_ip, command, arg = parts[0].strip(), parts[1].strip().upper(), parts[2].strip()
        if command == "USER":
            pending[src_ip] = {"type": "FTP", "src_ip": src_ip, "username": arg, "password": ""}
        elif command == "PASS":
            if src_ip in pending:
                pending[src_ip]["password"] = arg
                creds.append(pending.pop(src_ip))
            else:
                creds.append({"type": "FTP", "src_ip": src_ip, "username": "", "password": arg})

    # Flush any USER-only entries
    for entry in pending.values():
        creds.append(entry)

    return creds


def _parse_smtp_auth(output: str) -> list[dict]:
    """
    Parse SMTP AUTH lines.
    Lines: ip.src, smtp.req.command, smtp.req.parameter
    """
    creds: list[dict] = []
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        src_ip, command, param = parts[0].strip(), parts[1].strip().upper(), parts[2].strip()
        if command == "AUTH" and param:
            # param may be "PLAIN <base64>" or "LOGIN"
            tokens = param.split()
            mechanism = tokens[0] if tokens else "UNKNOWN"
            encoded = tokens[1] if len(tokens) > 1 else ""
            username, password = "", ""
            if mechanism == "PLAIN" and encoded:
                try:
                    raw = base64.b64decode(encoded + "==").decode("utf-8", errors="replace")
                    # PLAIN format: \x00user\x00pass or user\x00pass
                    chunks = raw.split("\x00")
                    chunks = [c for c in chunks if c]
                    if len(chunks) >= 2:
                        username, password = chunks[-2], chunks[-1]
                    elif chunks:
                        username = chunks[0]
                except Exception:
                    pass
            creds.append({
                "type": "SMTP",
                "src_ip": src_ip,
                "host": "",
                "username": username,
                "password": password or encoded,
            })
    return creds


def _parse_telnet(output: str) -> list[dict]:
    """
    Extract telnet data snippets (raw keystrokes).
    Lines: ip.src, ip.dst, telnet.data
    Returns a deduplicated list.
    """
    entries: list[dict] = []
    seen: set = set()
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        src_ip, dst_ip, data = parts[0].strip(), parts[1].strip(), parts[2].strip()
        key = (src_ip, dst_ip, data)
        if key not in seen:
            seen.add(key)
            entries.append({"type": "Telnet", "src_ip": src_ip, "dst_ip": dst_ip, "data": data})
    return entries


def _parse_io_stat(output: str) -> dict:
    """
    Parse tshark -q -z io,stat,0 output for basic stats.
    Looks for a summary line with total frames/bytes and capture duration.
    """
    stats: dict = {
        "packet_count": 0,
        "bytes": 0,
        "duration_sec": 0.0,
        "start_time": "",
    }
    for line in output.splitlines():
        # "Captured on '...' (... packets)" style
        m = re.search(r"(\d+)\s+packet", line, re.IGNORECASE)
        if m:
            stats["packet_count"] = max(stats["packet_count"], int(m.group(1)))

        # io,stat row: interval | frames | bytes
        m2 = re.match(r"\s*[\d.]+\s*<>\s*[\d.]+\s*\|\s*(\d+)\s*\|\s*(\d+)", line)
        if m2:
            stats["packet_count"] = int(m2.group(1))
            stats["bytes"] = int(m2.group(2))

        # Duration line
        m3 = re.search(r"Duration:\s*([\d.]+)", line, re.IGNORECASE)
        if m3:
            stats["duration_sec"] = float(m3.group(1))

        # Start time line
        m4 = re.search(r"First packet time:\s*(.+)", line, re.IGNORECASE)
        if not m4:
            m4 = re.search(r"Start time:\s*(.+)", line, re.IGNORECASE)
        if m4:
            stats["start_time"] = m4.group(1).strip()

    return stats


def _dedup_list(items: list[dict], key_fields: list[str]) -> list[dict]:
    """Return deduplicated list of dicts based on specified key fields."""
    seen: set = set()
    result: list[dict] = []
    for item in items:
        key = tuple(item.get(f, "") for f in key_fields)
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyze_pcap(pcap_path: Path) -> dict:
    """
    Run tshark against a PCAP file and return a structured analysis dict.

    Returns keys:
        file, size_kb, protocols, credentials, dns_queries,
        http_requests, hosts, stats, error (on failure)
    """
    pcap_path = Path(pcap_path)
    result: dict = {
        "file": pcap_path.name,
        "size_kb": 0.0,
        "protocols": {},
        "credentials": [],
        "dns_queries": [],
        "http_requests": [],
        "hosts": [],
        "stats": {},
        "error": None,
    }

    if not shutil.which("tshark"):
        result["error"] = "tshark not installed or not in PATH"
        return result

    if not pcap_path.exists():
        result["error"] = f"File not found: {pcap_path}"
        return result

    result["size_kb"] = round(pcap_path.stat().st_size / 1024, 2)
    r = pcap_path.resolve()

    # ------------------------------------------------------------------
    # 1. Protocol hierarchy
    # ------------------------------------------------------------------
    try:
        stdout, stderr, rc = _run_tshark(["-r", str(r), "-q", "-z", "io,phs"])
        if rc == 0:
            result["protocols"] = _parse_proto_hierarchy(stdout)
    except subprocess.TimeoutExpired:
        result["error"] = "tshark timed out on protocol hierarchy"
        return result
    except Exception as e:
        result["error"] = f"tshark error (proto hierarchy): {e}"
        return result

    # ------------------------------------------------------------------
    # 2. Basic stats
    # ------------------------------------------------------------------
    try:
        stdout, _, rc = _run_tshark(["-r", str(r), "-q", "-z", "io,stat,0"])
        if rc == 0:
            result["stats"] = _parse_io_stat(stdout)
    except Exception:
        pass  # stats are optional

    # Fallback packet count from capinfos if available
    if not result["stats"].get("packet_count") and shutil.which("capinfos"):
        try:
            ci = subprocess.run(
                ["capinfos", "-c", "-u", "-a", str(r)],
                capture_output=True, text=True, timeout=30,
            )
            for line in ci.stdout.splitlines():
                m = re.search(r"Number of packets:\s*(\d+)", line)
                if m:
                    result["stats"]["packet_count"] = int(m.group(1))
                m2 = re.search(r"Capture duration:\s*([\d.]+)", line)
                if m2:
                    result["stats"]["duration_sec"] = float(m2.group(1))
                m3 = re.search(r"First packet time:\s*(.+)", line)
                if m3:
                    result["stats"]["start_time"] = m3.group(1).strip()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # 3. HTTP Basic / Digest auth credentials
    # ------------------------------------------------------------------
    try:
        stdout, _, rc = _run_tshark([
            "-r", str(r),
            "-Y", "http.authorization",
            "-T", "fields",
            "-e", "ip.src",
            "-e", "http.host",
            "-e", "http.authorization",
        ])
        if rc == 0 and stdout.strip():
            result["credentials"].extend(_parse_http_auth(stdout))
    except Exception:
        pass

    # ------------------------------------------------------------------
    # 4. HTTP POST form data (potential credential fields)
    # ------------------------------------------------------------------
    try:
        stdout, _, rc = _run_tshark([
            "-r", str(r),
            "-Y", 'http.request.method == "POST"',
            "-T", "fields",
            "-e", "ip.src",
            "-e", "http.host",
            "-e", "http.request.uri",
            "-e", "urlencoded-form.value",
        ])
        if rc == 0:
            for line in stdout.splitlines():
                line = line.strip()
                if not line:
                    continue
                parts = line.split("\t")
                if len(parts) < 4:
                    continue
                src_ip, host, uri, form_value = parts[0], parts[1], parts[2], parts[3]
                # Record as HTTP request
                result["http_requests"].append({
                    "method": "POST",
                    "src_ip": src_ip,
                    "host": host,
                    "uri": uri,
                    "form_data": form_value,
                })
                # Heuristic: flag form submissions that look like credentials
                lower_val = form_value.lower()
                if any(kw in lower_val for kw in ("password", "passwd", "pass=", "pwd=")):
                    result["credentials"].append({
                        "type": "HTTP POST Form",
                        "src_ip": src_ip,
                        "host": host,
                        "username": "",
                        "password": form_value,
                    })
    except Exception:
        pass

    # ------------------------------------------------------------------
    # 5. General HTTP requests (GET/POST)
    # ------------------------------------------------------------------
    try:
        stdout, _, rc = _run_tshark([
            "-r", str(r),
            "-Y", "http.request",
            "-T", "fields",
            "-e", "ip.src",
            "-e", "http.host",
            "-e", "http.request.uri",
            "-e", "http.request.method",
        ])
        if rc == 0:
            for line in stdout.splitlines():
                line = line.strip()
                if not line:
                    continue
                parts = line.split("\t")
                if len(parts) < 4:
                    continue
                result["http_requests"].append({
                    "method": parts[3],
                    "src_ip": parts[0],
                    "host": parts[1],
                    "uri": parts[2],
                })
    except Exception:
        pass

    # Dedup and cap http_requests
    result["http_requests"] = _dedup_list(
        result["http_requests"], ["src_ip", "host", "uri", "method"]
    )[:100]

    # ------------------------------------------------------------------
    # 6. FTP credentials
    # ------------------------------------------------------------------
    try:
        stdout, _, rc = _run_tshark([
            "-r", str(r),
            "-Y", 'ftp.request.command == "USER" || ftp.request.command == "PASS"',
            "-T", "fields",
            "-e", "ip.src",
            "-e", "ftp.request.command",
            "-e", "ftp.request.arg",
        ])
        if rc == 0 and stdout.strip():
            result["credentials"].extend(_parse_ftp_creds(stdout))
    except Exception:
        pass

    # ------------------------------------------------------------------
    # 7. SMTP auth
    # ------------------------------------------------------------------
    try:
        stdout, _, rc = _run_tshark([
            "-r", str(r),
            "-Y", 'smtp.req.command == "AUTH" || smtp.req.command == "EHLO"',
            "-T", "fields",
            "-e", "ip.src",
            "-e", "smtp.req.command",
            "-e", "smtp.req.parameter",
        ])
        if rc == 0 and stdout.strip():
            result["credentials"].extend(_parse_smtp_auth(stdout))
    except Exception:
        pass

    # ------------------------------------------------------------------
    # 8. Telnet data
    # ------------------------------------------------------------------
    try:
        stdout, _, rc = _run_tshark([
            "-r", str(r),
            "-Y", "telnet",
            "-T", "fields",
            "-e", "ip.src",
            "-e", "ip.dst",
            "-e", "telnet.data",
        ])
        if rc == 0 and stdout.strip():
            telnet_entries = _parse_telnet(stdout)
            # Represent telnet sessions as credential hints
            for entry in telnet_entries:
                result["credentials"].append({
                    "type": "Telnet",
                    "src_ip": entry["src_ip"],
                    "host": entry.get("dst_ip", ""),
                    "username": "",
                    "password": entry.get("data", ""),
                })
    except Exception:
        pass

    # Dedup credentials on meaningful fields
    result["credentials"] = _dedup_list(
        result["credentials"], ["type", "src_ip", "host", "username"]
    )

    # ------------------------------------------------------------------
    # 9. DNS queries
    # ------------------------------------------------------------------
    try:
        stdout, _, rc = _run_tshark([
            "-r", str(r),
            "-Y", "dns.flags.response == 0",
            "-T", "fields",
            "-e", "ip.src",
            "-e", "dns.qry.name",
        ])
        if rc == 0:
            for line in stdout.splitlines():
                line = line.strip()
                if not line:
                    continue
                parts = line.split("\t")
                if len(parts) < 2:
                    continue
                result["dns_queries"].append({
                    "src_ip": parts[0].strip(),
                    "query": parts[1].strip(),
                })
    except Exception:
        pass

    result["dns_queries"] = _dedup_list(result["dns_queries"], ["src_ip", "query"])[:50]

    # ------------------------------------------------------------------
    # 10. All IP hosts seen
    # ------------------------------------------------------------------
    try:
        stdout, _, rc = _run_tshark([
            "-r", str(r),
            "-T", "fields",
            "-e", "ip.src",
            "-e", "ip.dst",
        ])
        if rc == 0:
            ips: set = set()
            for line in stdout.splitlines():
                for ip in line.split("\t"):
                    ip = ip.strip()
                    if ip and re.match(r"^\d{1,3}(\.\d{1,3}){3}$", ip):
                        ips.add(ip)
            result["hosts"] = sorted(ips)
    except Exception:
        pass

    return result


def list_pcaps(loot_dir: Path) -> list[dict]:
    """
    Scan loot/pcaps/ under loot_dir for .pcap and .pcapng files.
    Returns a list of {name, size_kb, mtime} dicts sorted by mtime descending.
    """
    loot_dir = Path(loot_dir)
    pcap_dir = loot_dir / "pcaps"
    results: list[dict] = []

    if not pcap_dir.is_dir():
        return results

    for f in pcap_dir.iterdir():
        if f.is_file() and f.suffix.lower() in (".pcap", ".pcapng"):
            stat = f.stat()
            results.append({
                "name": f.name,
                "path": str(f.resolve()),
                "size_kb": round(stat.st_size / 1024, 2),
                "mtime": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            })

    results.sort(key=lambda x: x["mtime"], reverse=True)
    return results


# ---------------------------------------------------------------------------
# CLI test entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) < 2:
        print("Usage: python parse_pcap.py <path-to-pcap>")
        sys.exit(1)

    target = Path(sys.argv[1])
    print(f"[*] Analyzing: {target}")
    data = analyze_pcap(target)

    if data.get("error"):
        print(f"[!] Error: {data['error']}")
        sys.exit(1)

    print(f"\n=== PCAP Summary: {data['file']} ===")
    print(f"  Size       : {data['size_kb']} KB")

    stats = data.get("stats", {})
    print(f"  Packets    : {stats.get('packet_count', 'N/A')}")
    print(f"  Bytes      : {stats.get('bytes', 'N/A')}")
    print(f"  Duration   : {stats.get('duration_sec', 'N/A')} sec")
    print(f"  Start time : {stats.get('start_time', 'N/A')}")

    print(f"\n--- Protocols ({len(data['protocols'])}) ---")
    for proto, count in sorted(data["protocols"].items(), key=lambda x: -x[1])[:15]:
        print(f"  {proto:<20} {count} frames")

    print(f"\n--- Hosts ({len(data['hosts'])}) ---")
    for host in data["hosts"][:30]:
        print(f"  {host}")
    if len(data["hosts"]) > 30:
        print(f"  ... and {len(data['hosts']) - 30} more")

    print(f"\n--- Credentials ({len(data['credentials'])}) ---")
    for cred in data["credentials"]:
        ctype = cred.get("type", "?")
        src = cred.get("src_ip", "?")
        host = cred.get("host", "?")
        user = cred.get("username", "")
        pwd = cred.get("password", cred.get("hash", ""))
        print(f"  [{ctype}] {src} -> {host}  user={user!r}  pass/hash={pwd!r}")

    print(f"\n--- DNS Queries ({len(data['dns_queries'])}) ---")
    for q in data["dns_queries"][:20]:
        print(f"  {q['src_ip']:<18} {q['query']}")

    print(f"\n--- HTTP Requests ({len(data['http_requests'])}) ---")
    for req in data["http_requests"][:20]:
        print(f"  [{req.get('method','?')}] {req.get('src_ip','?')} -> {req.get('host','?')}{req.get('uri','')}")

    # Optionally dump full JSON
    if "--json" in sys.argv:
        print("\n--- Full JSON ---")
        print(json.dumps(data, indent=2))
