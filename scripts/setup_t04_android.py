"""Generate local-only TLS material using OpenSSL (bundled with Git on Windows)."""

import argparse
import ipaddress
import json
from pathlib import Path
import secrets
import shutil
import socket
import subprocess

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / "instance/t04"


def detect_ip():
    # UDP connect selects the route; no packet is sent.
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as connection:
        connection.connect(("192.0.2.1", 80))
        return connection.getsockname()[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ip", help="IP Wi-Fi laptop; otomatis jika tidak diisi")
    args = parser.parse_args()
    address = str(ipaddress.IPv4Address(args.ip or detect_ip()))
    openssl = shutil.which("openssl") or "C:/Program Files/Git/usr/bin/openssl.exe"
    if not Path(openssl).is_file():
        raise SystemExit("OpenSSL tidak ditemukan. Pasang Git for Windows, lalu ulangi setup.")
    LOCAL.mkdir(parents=True, exist_ok=True)

    def run(*arguments):
        result = subprocess.run([openssl, *arguments], cwd=LOCAL, capture_output=True, text=True)
        if result.returncode:
            raise SystemExit(result.stderr)
        return result.stdout.strip()

    # Reuse the CA when the Wi-Fi IP changes, so Android need not reinstall it.
    if not (LOCAL / "ca.crt").exists():
        run("req", "-x509", "-newkey", "rsa:2048", "-nodes", "-sha256", "-days", "365",
            "-keyout", "ca.key", "-out", "ca.crt", "-subj", "/CN=SMA4 T04 Local Test CA",
            "-addext", "basicConstraints=critical,CA:TRUE,pathlen:0",
            "-addext", "keyUsage=critical,keyCertSign,cRLSign")
    run("req", "-new", "-newkey", "rsa:2048", "-nodes", "-keyout", "server.key",
        "-out", "server.csr", "-subj", "/CN=SMA4 T04 Local Test")
    (LOCAL / "server.ext").write_text(
        "basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\n"
        "extendedKeyUsage=serverAuth\nsubjectKeyIdentifier=hash\nauthorityKeyIdentifier=keyid,issuer\n"
        f"subjectAltName=DNS:localhost,IP:127.0.0.1,IP:{address}\n", encoding="ascii")
    run("x509", "-req", "-in", "server.csr", "-CA", "ca.crt", "-CAkey", "ca.key",
        "-CAcreateserial", "-out", "server.crt", "-days", "30", "-sha256", "-extfile", "server.ext")
    run("verify", "-CAfile", "ca.crt", "-purpose", "sslserver", "-verify_ip", address, "server.crt")
    fingerprint = run("x509", "-in", "ca.crt", "-noout", "-fingerprint", "-sha256")
    code_file = LOCAL / "access-code.txt"
    if not code_file.exists():
        code_file.write_text(secrets.token_hex(8), encoding="ascii")
    (LOCAL / "config.json").write_text(json.dumps({"ip": address, "fingerprint": fingerprint}, indent=2))
    print(f"Sertifikat siap. Panduan Android: http://{address}:8084")
    print(f"Kamera HTTPS: https://{address}:8443")
    print(f"Kode akses tersimpan lokal: {code_file}")
    print(fingerprint)
    print("Jalankan: .venv\\Scripts\\python.exe -m scripts.run_t04_android")


if __name__ == "__main__":
    main()
