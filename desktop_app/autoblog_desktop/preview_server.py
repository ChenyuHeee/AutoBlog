from __future__ import annotations

import contextlib
import socket
import threading
from dataclasses import dataclass
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


@dataclass
class PreviewServer:
    public_dir: Path
    host: str = "127.0.0.1"
    port: int = 0

    _thread: threading.Thread | None = None
    _httpd: ThreadingHTTPServer | None = None

    def start(self) -> None:
        self.public_dir.mkdir(parents=True, exist_ok=True)

        handler = self._make_handler(self.public_dir)
        httpd = ThreadingHTTPServer((self.host, self.port), handler)
        self._httpd = httpd
        self.port = httpd.server_address[1]

        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        self._thread = thread
        thread.start()

    def stop(self) -> None:
        if self._httpd is not None:
            with contextlib.suppress(Exception):
                self._httpd.shutdown()
            with contextlib.suppress(Exception):
                self._httpd.server_close()
        self._httpd = None
        self._thread = None

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}/"

    @staticmethod
    def _make_handler(public_dir: Path):
        class Handler(SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=str(public_dir), **kwargs)

            def log_message(self, format, *args):
                # Silence noisy logs; UI will show build logs separately.
                return

        return Handler
