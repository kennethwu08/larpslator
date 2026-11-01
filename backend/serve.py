"""Run the backend for the demo: one process, one shared state, two ports.

  http  :8000  for the badge (ESP32s handle plain WebSockets far better than TLS)
  https :8443  for browsers on other devices (phones need https for the microphone)

A self-signed certificate for this laptop's IP is made in backend/certs/ on first run (and again when the IP
changes, e.g. after switching to the phone hotspot). Browsers warn once about it; choose "continue".

Usage:  python serve.py
"""
import asyncio
import os
import subprocess
from pathlib import Path

import uvicorn

HERE = Path(__file__).parent
CERT_DIR = HERE / "certs"
CERT, KEY, CERT_IP = CERT_DIR / "cert.pem", CERT_DIR / "key.pem", CERT_DIR / "ip.txt"
HTTP_PORT, HTTPS_PORT = int(os.getenv("PORT") or 8000), int(os.getenv("LARPSLATOR_HTTPS_PORT") or 8443)


def ensure_cert(ip: str):
    if CERT.exists() and KEY.exists() and CERT_IP.exists() and CERT_IP.read_text() == ip:
        return
    CERT_DIR.mkdir(exist_ok=True)
    subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "30",
                    "-keyout", str(KEY), "-out", str(CERT), "-subj", "/CN=larpslator",
                    "-addext", f"subjectAltName=DNS:localhost,IP:127.0.0.1,IP:{ip}"],
                   check=True, capture_output=True)
    CERT_IP.write_text(ip)
    print(f"made a certificate for {ip}")


async def main():
    os.environ["LARPSLATOR_HTTPS_PORT"] = str(HTTPS_PORT)  # so the dashboard's pairing link points at https
    from main import PAIRING_CODE, app, lan_ip

    ip = lan_ip()
    ensure_cert(ip)
    # Ping every 10 s so a badge that drops off the Wi-Fi is noticed quickly.
    common = dict(app=app, host="0.0.0.0", ws_ping_interval=10, ws_ping_timeout=10, log_level="info")
    servers = [
        uvicorn.Server(uvicorn.Config(port=HTTP_PORT, **common)),
        uvicorn.Server(uvicorn.Config(port=HTTPS_PORT, ssl_certfile=str(CERT), ssl_keyfile=str(KEY),
                                      lifespan="off", **common)),  # startup tasks run once, in the first server
    ]
    print(f"""
  Dashboard on this laptop:   http://localhost:{HTTP_PORT}
  Dashboard on other devices: https://{ip}:{HTTPS_PORT}/?token={PAIRING_CODE}
  Badge config.h server:      ws://{ip}:{HTTP_PORT}/ws/badge?token={PAIRING_CODE}
  Pairing code:               {PAIRING_CODE}
""")
    await asyncio.gather(*(s.serve() for s in servers))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
