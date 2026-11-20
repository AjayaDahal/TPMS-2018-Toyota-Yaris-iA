"""Serve the TPMS Panel (2018 Yaris iA) viewer from this checkout on localhost."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if urlsplit(self.path).path in ("/viewer", "/viewer/"):
            self.send_response(302)
            self.send_header("Location", self.path.replace("/viewer", "/04-viewer/viewer", 1))
            self.end_headers()
            return
        super().do_GET()

    def translate_path(self, path):
        resolved = Path(super().translate_path(path)).resolve()
        if not resolved.is_relative_to(ROOT) or any(part.startswith(".") for part in resolved.relative_to(ROOT).parts):
            return str(ROOT / ".unavailable")
        return str(resolved)

    def list_directory(self, path):
        self.send_error(404)
        return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("port", type=int, nargs="?", default=28776)
    port = parser.parse_args().port
    with ThreadingHTTPServer(("127.0.0.1", port), partial(Handler, directory=ROOT)) as server:
        print(f"http://127.0.0.1:{server.server_port}/viewer/", flush=True)
        server.serve_forever()
