import argparse
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

EXAMPLES_DIR = Path(__file__).resolve().parent
NOT_FOUND = str(EXAMPLES_DIR / ".serve-not-found")
CACHEABLE = "public, max-age=31536000, immutable"
PACKAGE_DIR = EXAMPLES_DIR.parent / "rive-wasm" / "js" / "npm" / "webgl2"


def default_mounts():
    return {
        "/pkg/": PACKAGE_DIR,
        "/assets/": EXAMPLES_DIR / "assets",
        "/demo/": EXAMPLES_DIR.parent / "demo",
        "/": EXAMPLES_DIR,
    }


class Handler(SimpleHTTPRequestHandler):
    extensions_map = {
        **SimpleHTTPRequestHandler.extensions_map,
        ".wasm": "application/wasm",
        ".riv": "application/octet-stream",
        ".twno": "application/octet-stream",
        ".mjs": "text/javascript",
        "": "text/plain; charset=utf-8",
    }

    def __init__(self, *args, mounts, **kwargs):
        self.mounts = mounts
        super().__init__(*args, **kwargs)

    def translate_path(self, path):
        decoded = unquote(urlsplit(path).path)
        if "\0" in decoded or "\\" in decoded or ".." in decoded.split("/"):
            return NOT_FOUND
        for prefix, root in self.mounts:
            if decoded.startswith(prefix) or decoded + "/" == prefix:
                target = (root / decoded[len(prefix) :]).resolve()
                if target.is_relative_to(root):
                    return str(target)
                break
        return NOT_FOUND

    def send_response(self, code, message=None):
        self.status = code
        super().send_response(code, message)

    def end_headers(self):
        cacheable = self.server.cache and self.status < 300
        self.send_header("Cache-Control", CACHEABLE if cacheable else "no-store")
        if self.server.cors:
            self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    def log_message(self, format, *args):
        if self.server.verbose:
            super().log_message(format, *args)


def make_server(host, port, mounts, verbose=False, cors=False, cache=False):
    resolved = sorted(
        ((prefix, Path(root).resolve()) for prefix, root in mounts.items()),
        key=lambda item: -len(item[0]),
    )
    server = ThreadingHTTPServer((host, port), partial(Handler, mounts=resolved))
    server.verbose = verbose
    server.cors = cors
    server.cache = cache
    return server


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Serve the examples, the built package (/pkg/) and the "
        "prepared assets (/assets/) on localhost."
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--cors", action="store_true", help="send Access-Control-Allow-Origin: *")
    parser.add_argument("--cache", action="store_true", help="send long-lived immutable cache headers")
    args = parser.parse_args(argv)
    mounts = default_mounts()
    for needed in ("rive.js", "rive.wasm", "rive_fallback.wasm"):
        if not (mounts["/pkg/"] / needed).is_file():
            print(
                f"serve: {mounts['/pkg/'] / needed} is missing, build the package "
                "with web/build_webgl2_package.sh",
                file=sys.stderr,
            )
            return 1
    server = make_server(args.host, args.port, mounts, args.verbose, args.cors, args.cache)
    print(f"http://{args.host}:{server.server_address[1]}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
