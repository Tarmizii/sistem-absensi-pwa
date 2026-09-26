"""Render role shells and take headless screenshots for the T31 visual audit.

Authenticated pages are produced through the Flask test client with synthetic
fixtures, written to a temporary HTML file that inlines the compiled CSS and
copies the local font/illustrations next to it. Headless Chrome then screenshots
the static file at the PRD breakpoints so the result is a real browser render,
not a guess. The temporary tree is removed at the end.
"""

from __future__ import annotations

import base64
import re
import shutil
import subprocess
import sys
import tempfile
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from app import create_app
from app.services.auth_service import credential_stamp

REPO = Path(__file__).resolve().parent.parent
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
OUT = REPO / "docs" / "visual-audit"

USERS = {
    "admin": {
        "id": 1, "user_id": 1, "username": "demo.admin", "role": "admin",
        "password_hash": "unused", "is_active": 1, "must_change_password": 0,
        "full_name": "Admin Demo", "teacher_id": None, "student_id": None, "class_name": None,
    },
    "teacher": {
        "id": 2, "user_id": 2, "username": "demo.guru", "role": "teacher",
        "password_hash": "unused", "is_active": 1, "must_change_password": 0,
        "full_name": "Guru Demo", "teacher_id": 1, "student_id": None, "class_name": "X-1",
    },
    "student": {
        "id": 3, "user_id": 3, "username": "90000001", "role": "student",
        "password_hash": "unused", "is_active": 1, "must_change_password": 0,
        "face_registered": 1, "student_id": 1, "full_name": "Siswa Demo",
        "teacher_id": None, "class_name": "X-1",
    },
}

STUDENT_STATE = {
    "student_id": 1, "full_name": "Siswa Demo", "face_registered": True,
    "class_name": "X-1", "today": "2026-09-26", "server_time": "07:00",
    "state": "can_checkin", "cta_label": "Check-in", "cta_action": "checkin",
    "status_label": "Belum absen", "checkin_time": None, "checkout_time": None,
    "checkin_start": "07:00", "late_after": "07:15", "checkin_cutoff": "08:30",
    "checkout_start": "13:00", "message": "Silakan check-in dalam area sekolah.",
    "distance_meters": None, "accuracy": None, "location_ok": None,
    "geofence_radius": 75, "schedule_times": "07:00 - 13:00",
}

VIEWPORTS = {"mobile-360": 360, "tablet-768": 768, "desktop-1440": 1440}


def stub_state():
    return patch(
        "app.services.attendance_state_service.get_student_day_state",
        return_value=STUDENT_STATE,
    )


def render(app, role, path):
    client = app.test_client()
    user = USERS[role]
    with patch("app.services.auth_service.fetch_active_user", return_value=user):
        ctx = stub_state() if (role == "student" and "dashboard" in path) else nullcontext()
        with app.app_context():
            with client.session_transaction() as session:
                session["user_id"] = user["id"]
                session["credential_stamp"] = credential_stamp(user["password_hash"])
            with ctx:
                response = client.get(path, follow_redirects=False)
    if response.status_code in (301, 302):
        return None, f"redirect {response.headers.get('Location')}"
    if response.status_code != 200:
        return None, f"HTTP {response.status_code}"
    return response.get_data(as_text=True), None


def inline_assets(html: str) -> str:
    css = (REPO / "app/static/css/app.css").read_text(encoding="utf-8")
    font_b64 = base64.b64encode(
        (REPO / "app/static/fonts/plus-jakarta-sans-variable.ttf").read_bytes()
    ).decode("ascii")
    html = html.replace(
        '<link rel="stylesheet" href="/static/css/app.css">',
        f'<style>{css}\n@font-face{{font-family:"Plus Jakarta Sans";src:url(data:font/ttf;base64,{font_b64}) format("truetype");font-weight:200 800;}}</style>',
    )
    # Serve remaining /static references from the repo so illustrations resolve.
    html = html.replace('src="/static/', f'src="{REPO.as_uri()}/app/static/')
    return html


OVERFLOW_PROBE = """
<script>
window.addEventListener("load", () => setTimeout(() => {
  const vw = document.documentElement.clientWidth;
  const out = [];
  document.querySelectorAll("*").forEach((el) => {
    const r = el.getBoundingClientRect();
    if (r.width === 0 && r.height === 0) return;
    if (r.right > vw + 1 || r.left < -1) {
      out.push(el.tagName.toLowerCase() + "|" + String(el.className).slice(0, 45)
        + "|" + Math.round(r.left) + ".." + Math.round(r.right));
    }
  });
  const report = "VW=" + vw + " SCROLLW=" + document.documentElement.scrollWidth
    + " ## " + out.slice(0, 20).join(" ;; ");
  try { parent.postMessage({ audit: report }, "*"); } catch (e) {}
  document.title = report;
}, 700));
</script>
"""

WRAPPER = """<!doctype html>
<html><head><meta charset="utf-8"><title>x</title>
<style>html,body{{margin:0;padding:0;background:#fff;overflow:hidden}}
iframe{{display:block;width:{width}px;height:{height}px;border:0}}</style>
</head><body>
<iframe src="{src}"></iframe>
<script>
window.addEventListener("message", (event) => {{
  if (event.data && event.data.audit) document.title = event.data.audit;
}});
</script>
</body></html>
"""


def _wrap(page_html: str, width: int, height: int) -> tuple[str, str]:
    """Write page + wrapper into a temp dir; return (wrapper_html, wrapper_uri)."""
    tmp = tempfile.mkdtemp()
    page_path = Path(tmp) / "page.html"
    page_path.write_text(
        page_html.replace("</body>", OVERFLOW_PROBE + "</body>"), encoding="utf-8"
    )
    wrapper = WRAPPER.format(width=width, height=height, src=page_path.as_uri())
    wrapper_path = Path(tmp) / "wrapper.html"
    wrapper_path.write_text(wrapper, encoding="utf-8")
    return tmp, wrapper_path.as_uri()


def audit_overflow(page_html: str, width: int) -> str:
    """Render inside a fixed-width iframe so media queries see a real phone width."""
    tmp, uri = _wrap(page_html, width, 1600)
    try:
        result = subprocess.run(
            [CHROME, "--headless=new", "--disable-gpu", "--no-sandbox",
             "--allow-file-access-from-files", "--hide-scrollbars",
             "--virtual-time-budget=6000",
             f"--window-size={max(width + 40, 520)},1700", "--dump-dom", uri],
            capture_output=True, timeout=120, text=True, errors="replace",
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    match = re.search(r"<title>(.*?)</title>", result.stdout, re.S)
    return match.group(1).strip() if match else "(no title)"


def shoot(page_html: str, name: str, width: int) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    height = 1600
    tmp, uri = _wrap(page_html, width, height)
    try:
        raw = Path(tmp) / "raw.png"
        result = subprocess.run(
            [CHROME, "--headless=new", "--disable-gpu", "--no-sandbox",
             "--allow-file-access-from-files", "--hide-scrollbars",
             "--virtual-time-budget=6000",
             f"--window-size={max(width + 40, 520)},{height + 40}",
             f"--screenshot={raw}", uri],
            capture_output=True, timeout=120,
        )
        if not raw.exists():
            raise RuntimeError(f"chrome produced no screenshot for {name}: {result.stderr[:300]}")
        target = OUT / f"{name}-{width}.png"
        with Image.open(raw) as image:
            image.crop((0, 0, width, min(height, image.size[1]))).save(target)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"  {target.name}")


ROUTES = [
    ("admin", "/admin/dashboard", "admin-dashboard"),
    ("admin", "/admin/attendance", "admin-attendance"),
    ("admin", "/admin/analytics", "admin-analytics"),
    ("admin", "/admin/audit-logs", "admin-audit"),
    ("admin", "/admin/students", "admin-students"),
    ("teacher", "/teacher/dashboard", "teacher-dashboard"),
    ("teacher", "/teacher/attendance", "teacher-attendance"),
    ("teacher", "/teacher/students", "teacher-students"),
    ("student", "/student/dashboard", "student-dashboard"),
    ("student", "/student/history", "student-history"),
    ("student", "/profile", "student-profile"),
]

PUBLIC = [("/login", "login"), ("/", "home")]


def widths_for(role: str) -> dict[str, int]:
    """PRD viewport plus a 200% zoom pass (1280 and 1440 at 200% == 640 and 720)."""
    if role == "student":
        return {"mobile-360": 360, "zoom200-640": 640}
    if role == "teacher":
        return {"tablet-768": 768, "zoom200-640": 640}
    return {"desktop-1440": 1440, "zoom200-720": 720}


def main() -> int:
    if not Path(CHROME).exists():
        print("chrome not found", file=sys.stderr)
        return 1
    app = create_app({"TESTING": True, "SECRET_KEY": "audit-secret"})

    print("public routes")
    client = app.test_client()
    for path, name in PUBLIC:
        response = client.get(path)
        if response.status_code != 200:
            print(f"  skip {name}: HTTP {response.status_code}")
            continue
        html = inline_assets(response.get_data(as_text=True))
        for label, width in VIEWPORTS.items():
            shoot(html, f"{name}-{label}", width)

    print("role routes")
    for role, path, name in ROUTES:
        html, problem = render(app, role, path)
        if html is None:
            print(f"  skip {name}: {problem}")
            continue
        html = inline_assets(html)
        for label, width in widths_for(role).items():
            shoot(html, f"{name}-{label}", width)
            report = audit_overflow(html, width)
            match = re.search(r"SCROLLW=(\d+)", report)
            scroll = int(match.group(1)) if match else 0
            flag = "ok" if scroll <= width + 1 else "OVERFLOW"
            print(f"      {width}px {flag}: {report[:230]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
