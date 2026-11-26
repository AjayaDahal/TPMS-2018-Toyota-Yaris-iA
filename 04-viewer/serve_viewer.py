"""Serve the TPMS Panel (2018 Yaris iA) viewer from this checkout on localhost.

Only files that belong to the repository are served: tracked files and new files git doesn't ignore
(`git ls-files --cached --others --exclude-standard`). Git-ignored personal files and build output are never served,
and requests must carry a localhost Host header (a web page can't read the files through DNS rebinding).
"""
import argparse
import socket
import subprocess
import sys
import threading
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
# Without git (a zip download): serve only these folders and top-level files.
FALLBACK_DIRS = ("00-project-management", "01-hardware", "02-firmware", "03-manufacturing", "04-viewer",
                 "05-Audit-Subsystems")
FALLBACK_FILES = ("README.md", "index.html")
FALLBACK_SKIP = ("build", "git_ignore")


class RepoFiles:
    """The set of servable paths (relative, POSIX), refreshed on a miss at most every 2 s."""

    def __init__(self):
        self.lock = threading.Lock()
        self.files, self.stamp, self.git = set(), 0.0, True
        self.refresh()

    def refresh(self):
        try:
            out = subprocess.run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=ROOT,
                                 capture_output=True, check=True).stdout.decode("utf-8", "replace")
            files = {p for p in out.split("\0") if p}
        except (OSError, subprocess.CalledProcessError):
            self.git = False
            files = set()
        with self.lock:
            self.files, self.stamp = files, time.monotonic()

    def allowed(self, rel):
        if not self.git:
            parts = rel.split("/")
            if any(p.startswith(".") or p.startswith(FALLBACK_SKIP) for p in parts):
                return False
            return rel in FALLBACK_FILES or (len(parts) > 1 and parts[0] in FALLBACK_DIRS)
        with self.lock:
            if rel in self.files:
                return True
            stale = time.monotonic() - self.stamp > 2.0
        if stale:
            self.refresh()
            with self.lock:
                return rel in self.files
        return False


class Handler(SimpleHTTPRequestHandler):
    repo = None
    port = 0
    extensions_map = {
        **SimpleHTTPRequestHandler.extensions_map,
        # Explicit: Python reads the Windows registry, where .js is sometimes text/plain (module scripts then fail)
        ".js": "text/javascript", ".mjs": "text/javascript", ".json": "application/json", ".css": "text/css",
        ".html": "text/html", ".svg": "image/svg+xml", ".md": "text/plain; charset=utf-8",
        ".csv": "text/plain; charset=utf-8", ".stl": "model/stl",
    }

    def host_ok(self):
        host = (self.headers.get("Host") or "").lower()
        return host in {f"127.0.0.1:{self.port}", f"localhost:{self.port}", f"[::1]:{self.port}"}

    def send_head(self):
        if not self.host_ok():
            self.send_error(421, "Misdirected request: use http://127.0.0.1:%d/viewer/" % self.port)
            return None
        path = urlsplit(self.path).path
        if path in ("/viewer", "/viewer/"):
            self.send_response(302)
            self.send_header("Location", self.path.replace("/viewer", "/04-viewer/viewer", 1))
            self.end_headers()
            return None
        rel = unquote(path).lstrip("/")
        if rel.endswith("/") or rel == "":
            rel += "index.html"
        target = (ROOT / rel).resolve()
        if not target.is_relative_to(ROOT) or not self.repo.allowed(target.relative_to(ROOT).as_posix()):
            self.send_error(404)
            return None
        return super().send_head()

    def list_directory(self, path):
        self.send_error(404)
        return None


class Server(ThreadingHTTPServer):
    # On Windows SO_REUSEADDR lets a second server bind the same port and the two answer at random (or not at all):
    # bind exclusively, so a port in use is an error.
    allow_reuse_address = sys.platform != "win32"

    def server_bind(self):
        if sys.platform == "win32" and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("port", type=int, nargs="?", default=28776)
    port = parser.parse_args().port
    Handler.repo, Handler.port = RepoFiles(), port
    if not Handler.repo.git:
        print("git not found: serving only the project folders", file=sys.stderr)
    try:
        server = Server(("127.0.0.1", port), partial(Handler, directory=str(ROOT)))
    except OSError as err:
        sys.exit(f"Port {port} is in use ({err.strerror}): another viewer may still be running. Stop it, or pass "
                 f"another port (python 04-viewer/serve_viewer.py {port + 2}). Checklist ticks are stored per "
                 f"address, so they show again only on the same port.")
    with server:
        print(f"http://127.0.0.1:{server.server_port}/viewer/", flush=True)
        server.serve_forever()


if __name__ == "__main__":
    main()
