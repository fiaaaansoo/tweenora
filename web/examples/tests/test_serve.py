import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

EXAMPLES_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXAMPLES_DIR))

import serve


class ServeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        tmp = Path(cls._tmp.name)
        cls.examples = tmp / "examples"
        cls.package = tmp / "package"
        cls.assets = tmp / "assets"
        for directory in (cls.examples, cls.package, cls.assets):
            directory.mkdir()
        (cls.examples / "index.html").write_text("<p>home</p>")
        (cls.package / "rive.js").write_text("var rive = 1;")
        (cls.package / "THIRD_PARTY_NOTICES").write_text("notices")
        (cls.package / "rive.wasm").write_bytes(b"\0asm\1\0\0\0")
        (cls.assets / "a.twno").write_bytes(b"TWNR1234")
        (cls.assets / "a.riv").write_bytes(b"RIVE1234")
        (cls.examples / "secret.txt").write_text("secret")
        (cls.examples / "pkg").mkdir()
        (cls.examples / "pkg" / "rive.js").write_text("shadow")
        cls.server = serve.make_server(
            "127.0.0.1",
            0,
            {"/pkg/": cls.package, "/assets/": cls.assets, "/": cls.examples},
        )
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls._tmp.cleanup()

    def get(self, path):
        with urllib.request.urlopen(self.base + path) as response:
            return response.status, response.headers, response.read()

    def test_serves_each_mount(self):
        self.assertEqual(self.get("/")[2], b"<p>home</p>")
        self.assertEqual(self.get("/pkg/rive.js")[2], b"var rive = 1;")
        self.assertEqual(self.get("/assets/a.twno")[2], b"TWNR1234")

    def test_wasm_has_the_wasm_mime_type(self):
        self.assertEqual(
            self.get("/pkg/rive.wasm")[1].get_content_type(), "application/wasm"
        )

    def test_the_notices_file_without_extension_is_shown_as_text(self):
        self.assertEqual(
            self.get("/pkg/THIRD_PARTY_NOTICES")[1].get_content_type(), "text/plain"
        )

    def test_riv_and_twno_are_binary(self):
        for path in ("/assets/a.riv", "/assets/a.twno"):
            self.assertEqual(
                self.get(path)[1].get_content_type(), "application/octet-stream"
            )

    def test_responses_are_never_cached(self):
        self.assertIn("no-store", self.get("/pkg/rive.js")[1]["Cache-Control"])

    def test_no_cors_header_by_default(self):
        self.assertIsNone(self.get("/pkg/rive.wasm")[1].get("Access-Control-Allow-Origin"))

    def test_missing_file_is_404(self):
        with self.assertRaises(urllib.error.HTTPError) as raised:
            self.get("/assets/absent.riv")
        self.assertEqual(raised.exception.code, 404)

    def test_does_not_escape_a_mount(self):
        for path in (
            "/pkg/../secret.txt",
            "/pkg/%2e%2e/secret.txt",
            "/assets/..%2fsecret.txt",
            "/pkg/..%5csecret.txt",
            "/pkg/rive.js%00.txt",
            "/pkgx/rive.js",
        ):
            with self.subTest(path=path):
                with self.assertRaises(urllib.error.HTTPError) as raised:
                    self.get(path)
                self.assertEqual(raised.exception.code, 404)

    def test_the_root_mount_serves_what_is_not_traversal(self):
        self.assertEqual(self.get("/secret.txt")[2], b"secret")

    def test_most_specific_mount_wins(self):
        self.assertEqual(self.get("/pkg/rive.js")[2], b"var rive = 1;")

    def test_default_mounts_point_to_the_built_package_and_assets(self):
        mounts = serve.default_mounts()
        self.assertEqual(mounts["/"], EXAMPLES_DIR)
        self.assertEqual(mounts["/assets/"], EXAMPLES_DIR / "assets")
        self.assertEqual(mounts["/demo/"], EXAMPLES_DIR.parent / "demo")
        self.assertEqual(
            mounts["/pkg/"],
            EXAMPLES_DIR.parent / "rive-wasm" / "js" / "npm" / "webgl2",
        )



class DeploymentHeadersTest(unittest.TestCase):
    def serve(self, **options):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        (root / "rive.wasm").write_bytes(b"\0asm\1\0\0\0")
        server = serve.make_server("127.0.0.1", 0, {"/": root}, **options)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        def stop():
            server.shutdown()
            server.server_close()
            thread.join()

        self.addCleanup(stop)
        url = f"http://127.0.0.1:{server.server_address[1]}/rive.wasm"
        with urllib.request.urlopen(url) as response:
            return response.headers

    def test_cors_flag_allows_any_origin(self):
        self.assertEqual(self.serve(cors=True)["Access-Control-Allow-Origin"], "*")

    def test_cache_flag_makes_files_cacheable(self):
        headers = self.serve(cache=True)
        self.assertIn("max-age=", headers["Cache-Control"])
        self.assertNotIn("no-store", headers["Cache-Control"])

    def test_default_is_no_store(self):
        self.assertEqual(self.serve()["Cache-Control"], "no-store")

    def test_errors_are_never_cached_even_with_the_cache_flag(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        server = serve.make_server("127.0.0.1", 0, {"/": Path(tmp.name)}, cache=True)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        url = f"http://127.0.0.1:{server.server_address[1]}/absent.wasm"
        with self.assertRaises(urllib.error.HTTPError) as raised:
            urllib.request.urlopen(url)
        self.assertEqual(raised.exception.headers["Cache-Control"], "no-store")


if __name__ == "__main__":
    unittest.main()
