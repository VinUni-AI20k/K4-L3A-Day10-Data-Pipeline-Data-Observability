"""Local pipeline dashboard; serving the UI requires only Python's standard library."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import threading
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
TOKEN = secrets.token_urlsafe(32)
LOCK = threading.Lock()
JOB = {"status": "idle", "phase": None, "exit_code": None}
LOG: deque[str] = deque(maxlen=600)


def snapshot(root=ROOT):
    errors = []

    def read(relative):
        path = root / "data" / relative
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError) as exc:
            errors.append(f"{relative}: {exc}")
            return None

    states = {}
    for state in ("baseline", "corrupted", "repaired"):
        suffix = "" if state == "baseline" else f"_{state}"
        states[state] = {
            "records": read(f"clean/papers_clean{suffix}.json"),
            "metrics": read(f"results/{state}_metrics.json"),
            "quality": read(f"quality/{state}_quality_report.json"),
            "freshness": read(f"quality/freshness_report{suffix}.json"),
        }
    with LOCK:
        job = {**JOB, "log": list(LOG)}
    return {"raw": read("raw/crossref_records.json"), "states": states,
            "corruption": read("results/corruption_log.json"),
            "errors": errors, "job": job, "token": TOKEN}


def run_pipeline(phase):
    try:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
        env["PYTHONIOENCODING"] = "utf-8"
        script = "run_phase1.py" if phase == "baseline" else "run_corruption_flow.py"
        with subprocess.Popen([sys.executable, "-u", str(ROOT / "script" / script)],
                              cwd=ROOT, env=env, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                              errors="replace", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)) as process:
            for line in process.stdout:
                with LOCK:
                    LOG.append(line.rstrip())
            code = process.wait()
        with LOCK:
            JOB.update(status="completed" if code == 0 else "failed", exit_code=code)
    except Exception as exc:
        with LOCK:
            LOG.append(str(exc))
            JOB.update(status="failed", exit_code=-1)


class Handler(BaseHTTPRequestHandler):
    def send(self, status, body, content_type="application/json; charset=utf-8"):
        if not isinstance(body, bytes):
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def valid_host(self):
        return self.headers.get("Host") in {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}

    def do_GET(self):
        if not self.valid_host():
            return self.send(403, {"error": "Local access only"})
        path = urlparse(self.path).path
        if path == "/api/snapshot":
            return self.send(200, snapshot())
        assets = {"/": ("index.html", "text/html"), "/app.js": ("app.js", "text/javascript"),
                  "/style.css": ("style.css", "text/css")}
        if path in assets:
            name, mime = assets[path]
            return self.send(200, (ROOT / "ui" / name).read_bytes(), mime + "; charset=utf-8")
        return self.send(404, {"error": "Not found"})

    def do_POST(self):
        if not self.valid_host() or self.headers.get("X-UI-Token") != TOKEN:
            return self.send(403, {"error": "Phiên không hợp lệ. Hãy tải lại trang."})
        phase = {"/api/run/baseline": "baseline", "/api/run/corruption": "corruption"}.get(self.path)
        if not phase:
            return self.send(404, {"error": "Not found"})
        with LOCK:
            if JOB["status"] == "running":
                return self.send(409, {"error": "Pipeline đang chạy."})
            if phase == "corruption" and not all((ROOT / "data" / p).exists() for p in
                    ("results/baseline_metrics.json", "clean/papers_clean.json", "eval/test_set.json")):
                return self.send(409, {"error": "Hãy chạy baseline thành công trước."})
            JOB.update(status="running", phase=phase, exit_code=None)
            LOG.clear()
        threading.Thread(target=run_pipeline, args=(phase,), daemon=True).start()
        self.send(202, {"status": "running"})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Pipeline UI: http://127.0.0.1:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
