"""Start/stop an isolated T04 server behind a temporary Cloudflare Quick Tunnel."""

from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import ssl
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen

from scripts.setup_t04_android import LOCAL, ROOT

PUBLIC = LOCAL / "public"
STATE = PUBLIC / "processes.json"
URL_FILE = PUBLIC / "url.txt"
ACCESS_FILE = PUBLIC / "access-code.txt"
URL_PATTERN = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com(?:\s|$)", re.I)
CREATE_FLAGS = getattr(subprocess, "DETACHED_PROCESS", 0x00000008) | getattr(
    subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_TERMINATE = 0x0001
SYNCHRONIZE = 0x00100000


def windows_process_identity(pid: int) -> dict | None:
    """Read executable and creation time to protect unrelated/reused PIDs."""
    if os.name != "nt":
        raise RuntimeError("Launcher ini dirancang untuk Windows.")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    handle = kernel.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return None
    try:
        creation = wintypes.FILETIME()
        exited = wintypes.FILETIME()
        kernel.GetProcessTimes.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.FILETIME),
                                           ctypes.POINTER(wintypes.FILETIME), ctypes.POINTER(wintypes.FILETIME),
                                           ctypes.POINTER(wintypes.FILETIME)]
        if not kernel.GetProcessTimes(handle, ctypes.byref(creation), ctypes.byref(exited),
                                      ctypes.byref(wintypes.FILETIME()), ctypes.byref(wintypes.FILETIME())):
            return None
        started = (creation.dwHighDateTime << 32) | creation.dwLowDateTime
        path_size = wintypes.DWORD(32768)
        path = ctypes.create_unicode_buffer(path_size.value)
        kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD,
                                                       wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
        if not kernel.QueryFullProcessImageNameW(handle, 0, path, ctypes.byref(path_size)):
            return None
        return {"pid": pid, "created": started, "exe": str(Path(path.value).resolve())}
    finally:
        kernel.CloseHandle(handle)


def recorded_process_is_alive(record: dict) -> bool:
    actual = windows_process_identity(int(record["pid"]))
    return bool(actual and actual["created"] == record["created"]
                and os.path.normcase(actual["exe"]) == os.path.normcase(record["exe"]))


def terminate_recorded_process(record: dict) -> bool:
    """Terminate only a PID whose executable and creation timestamp still match."""
    if not recorded_process_is_alive(record):
        return False
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    handle = kernel.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_TERMINATE | SYNCHRONIZE,
                                False, int(record["pid"]))
    if not handle:
        return False
    try:
        # Check identity a second time immediately before the destructive call.
        if not recorded_process_is_alive(record):
            return False
        if not kernel.TerminateProcess(handle, 1):
            return False
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel.WaitForSingleObject.restype = wintypes.DWORD
        return kernel.WaitForSingleObject(handle, 5000) == 0
    finally:
        kernel.CloseHandle(handle)


def load_state() -> dict | None:
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"File status T04 tidak dapat dibaca: {error}") from error


def port_is_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
        connection.settimeout(0.3)
        return connection.connect_ex(("127.0.0.1", port)) == 0


def https_ready() -> bool:
    try:
        context = ssl.create_default_context(cafile=str(LOCAL / "ca.crt"))
        with urlopen("https://127.0.0.1:8443/", context=context, timeout=2) as response:
            return response.status == 200 and b"data-csrf" in response.read()
    except (OSError, URLError, ssl.SSLError):
        return False


def public_url_is_ready(url: str) -> bool:
    try:
        with urlopen(url, timeout=8) as response:
            page = response.read().decode("utf-8", errors="replace")
            return (response.status == 200 and "name=\"access_code\"" in page
                    and "/static/js/t04-poc.js" in page and "/static/css/app.css" in page)
    except (OSError, URLError, UnicodeError):
        return False


def find_cloudflared() -> str:
    candidate = shutil.which("cloudflared")
    if candidate:
        return str(Path(candidate).resolve())
    for candidate in (Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))
                      / "cloudflared/cloudflared.exe",
                      Path(os.environ.get("ProgramW6432", r"C:\Program Files"))
                      / "cloudflared/cloudflared.exe"):
        if candidate.is_file():
            return str(candidate.resolve())
    raise RuntimeError("cloudflared.exe tidak ditemukan. Periksa instalasi Cloudflare Tunnel.")


def write_state(state: dict) -> None:
    temporary = STATE.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, indent=2), encoding="utf-8")
    temporary.replace(STATE)


def spawn_logged(command: list[str], log_path: Path) -> dict:
    with log_path.open("ab", buffering=0) as log:
        process = subprocess.Popen(command, cwd=ROOT, stdin=subprocess.DEVNULL,
                                   stdout=log, stderr=subprocess.STDOUT,
                                   creationflags=CREATE_FLAGS, close_fds=True)
    # Give Windows a moment to publish the process object before recording identity.
    for _ in range(30):
        identity = windows_process_identity(process.pid)
        if identity:
            return identity
        if process.poll() is not None:
            break
        time.sleep(0.1)
    raise RuntimeError(f"Proses tidak dapat dimulai. Periksa {log_path}.")


def start() -> int:
    if os.name != "nt":
        raise RuntimeError("Launcher ini hanya mendukung Windows.")
    if not (LOCAL / "server.crt").is_file() or not (LOCAL / "ca.crt").is_file():
        raise RuntimeError("Sertifikat origin belum ada. Jalankan scripts.setup_t04_android dahulu.")
    previous = load_state()
    if previous and any(recorded_process_is_alive(record) for record in previous.get("processes", [])):
        raise RuntimeError("Layanan T04 milik launcher ini sudah berjalan. Gunakan perintah status atau stop.")
    if port_is_open(8443):
        raise RuntimeError("Port 8443 sudah dipakai. Launcher tidak akan menghentikan proses yang tidak dibuatnya.")

    PUBLIC.mkdir(parents=True, exist_ok=True)
    cloudflared = find_cloudflared()
    access_code = secrets.token_urlsafe(15)
    ACCESS_FILE.write_text(access_code, encoding="ascii")
    URL_FILE.unlink(missing_ok=True)
    for filename in ("server.log", "cloudflared.log", "launcher.log"):
        (PUBLIC / filename).write_text("", encoding="utf-8")

    state = {"started_at": time.time(), "processes": []}
    write_state(state)
    server = spawn_logged([sys.executable, "-m", "scripts.run_t04_android", "--public"],
                          PUBLIC / "server.log")
    state["processes"].append(server)
    write_state(state)
    for _ in range(80):
        if https_ready():
            break
        if not recorded_process_is_alive(server):
            raise RuntimeError(f"Server T04 berhenti saat startup. Lihat {PUBLIC / 'server.log'}.")
        time.sleep(0.25)
    else:
        stop()
        raise RuntimeError(f"Server T04 tidak menjawab HTTPS. Lihat {PUBLIC / 'server.log'}.")

    tunnel = spawn_logged([
        cloudflared, "tunnel", "--no-autoupdate", "--protocol", "http2",
        "--url", "https://127.0.0.1:8443", "--origin-ca-pool", str(LOCAL / "ca.crt"),
        "--logfile", str(PUBLIC / "cloudflared.log"),
    ], PUBLIC / "launcher.log")
    state["processes"].append(tunnel)
    write_state(state)

    deadline = time.monotonic() + 150
    seen_url = None
    next_wait_notice = time.monotonic() + 10
    while time.monotonic() < deadline:
        if not recorded_process_is_alive(server) or not recorded_process_is_alive(tunnel):
            stop()
            raise RuntimeError(f"Server/tunnel berhenti saat startup. Periksa log dalam {PUBLIC}.")
        try:
            log_text = (PUBLIC / "cloudflared.log").read_text(encoding="utf-8", errors="replace")
        except OSError:
            log_text = ""
        matches = URL_PATTERN.findall(log_text)
        if matches:
            seen_url = matches[-1].strip()
            if public_url_is_ready(seen_url):
                URL_FILE.write_text(seen_url, encoding="ascii")
                print("T04 publik terverifikasi:")
                print(f"  URL: {seen_url}")
                print(f"  Kode akses: {access_code}")
                print(f"  Log lokal: {PUBLIC}")
                print("  Android dapat memakai Wi-Fi atau data seluler; laptop harus tetap menyala.")
                return 0
        if time.monotonic() >= next_wait_notice:
            print("Menunggu tunnel tersambung dan URL publik merespons...", flush=True)
            next_wait_notice = time.monotonic() + 10
        time.sleep(2)

    stop()
    raise RuntimeError(f"Tunnel belum terverifikasi dalam 150 detik. URL terakhir: {seen_url or 'belum ada'}. "
                       f"Periksa log dalam {PUBLIC}.")


def stop() -> int:
    state = load_state()
    if not state:
        print("Tidak ada state launcher T04. Tidak ada proses yang dihentikan.")
        return 0
    for record in reversed(state.get("processes", [])):
        if terminate_recorded_process(record):
            print(f"Dihentikan proses milik T04: PID {record['pid']} ({Path(record['exe']).name}).")
    for path in (STATE, URL_FILE, ACCESS_FILE):
        path.unlink(missing_ok=True)
    print("Tunnel dan server T04 milik launcher sudah dihentikan; kode dan URL aktif dihapus.")
    return 0


def status() -> int:
    state = load_state()
    if not state:
        print("T04 publik berhenti.")
        return 0
    live = [record for record in state.get("processes", []) if recorded_process_is_alive(record)]
    url = URL_FILE.read_text(encoding="ascii").strip() if URL_FILE.exists() else "belum terverifikasi"
    print(f"Proses T04 milik launcher aktif: {len(live)}/{len(state.get('processes', []))}.")
    print(f"URL: {url}")
    if not live:
        print("Jalankan stop untuk membersihkan state usang, kemudian start lagi.")
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("start", "stop", "status"))
    action = parser.parse_args().action
    try:
        return {"start": start, "stop": stop, "status": status}[action]()
    except (OSError, RuntimeError, ValueError) as error:
        print(f"T04: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
