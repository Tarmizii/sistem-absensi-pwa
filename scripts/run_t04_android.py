"""Start isolated T04 HTTPS and a public-certificate-only HTTP setup page."""

import json
from threading import Thread

from flask import Flask, render_template, send_file
from werkzeug.serving import make_server

from scripts.setup_t04_android import LOCAL, ROOT
from scripts.t04_web import create_poc_app


def create_setup_app(config):
    bootstrap = Flask("t04_setup", template_folder=str(ROOT / "app/templates"), static_folder=None)

    @bootstrap.get("/")
    def setup_page():
        return render_template("poc/setup.html", **config)

    @bootstrap.get("/ca.crt")
    def certificate():
        # Exact public certificate only. Private keys and access code never served.
        return send_file(LOCAL / "ca.crt", mimetype="application/x-x509-ca-cert",
                         as_attachment=True, download_name="SMA4-T04-CA.crt")

    @bootstrap.after_request
    def headers(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    return bootstrap


def main():
    if not (LOCAL / "config.json").exists():
        raise SystemExit("Jalankan python -m scripts.setup_t04_android terlebih dahulu.")
    config = json.loads((LOCAL / "config.json").read_text())
    access_code = (LOCAL / "access-code.txt").read_text().strip()
    https = make_server("0.0.0.0", 8443, create_poc_app(access_code), threaded=True,
                        ssl_context=(str(LOCAL / "server.crt"), str(LOCAL / "server.key")))
    setup = make_server("0.0.0.0", 8084, create_setup_app(config), threaded=True)
    Thread(target=setup.serve_forever, daemon=True).start()
    print(f"Panduan Android: http://{config['ip']}:8084", flush=True)
    print(f"Kamera T04: https://{config['ip']}:8443", flush=True)
    print(f"Kode akses: {access_code}", flush=True)
    print("Ctrl+C untuk berhenti; sampel/model sementara hilang saat server berhenti.", flush=True)
    try:
        https.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        setup.shutdown()
        setup.server_close()
        https.server_close()


if __name__ == "__main__":
    main()
