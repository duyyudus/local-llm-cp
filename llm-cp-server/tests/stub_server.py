#!/usr/bin/env python3
"""Stand-in for llama-server and ComfyUI's main.py: logs a few lines and answers health checks."""
from __future__ import annotations

import argparse
import os
from http.server import BaseHTTPRequestHandler, HTTPServer


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self.send_response(200 if self.path in ("/health", "/system_stats") else 404)
        self.end_headers()
        self.wfile.write(b'{"status":"ok"}')

    def log_message(self, *_args: object) -> None:
        return None


parser = argparse.ArgumentParser()
parser.add_argument("--host", "--listen", default="127.0.0.1")
parser.add_argument("--port", type=int, default=8080)
args, extra = parser.parse_known_args()
print(f"stub starting on {args.host}:{args.port}", flush=True)
print(f"extra args: {extra}", flush=True)
print(f"STUB_ENV={os.environ.get('STUB_ENV', '')}", flush=True)
server = HTTPServer((args.host, args.port), Handler)
print("server is listening", flush=True)
server.serve_forever()
