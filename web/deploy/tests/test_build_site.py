import hashlib
import io
import json
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

DEPLOY_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = DEPLOY_DIR.parents[1]
sys.path.insert(0, str(DEPLOY_DIR))

import build_site

sys.path.insert(0, str(REPO_DIR / "web" / "examples"))
import prepare_assets

GOOD_RIV = b"RIVE-good"
BAD_RIV = b"RIVE-bad"

INDEX = (
    '<a href="/pkg/THIRD_PARTY_NOTICES">notices</a>'
    '<script src="/pkg/rive.js"></script><script src="demo.js"></script>'
)


def digest(data):
    return hashlib.sha256(data).hexdigest()[:16]


def provenance_text(good_status="yes", good_digest=None):
    good_digest = good_digest or digest(GOOD_RIV)
    return (
        "# Provenance\n\n"
        "| File | Folder | Author | License | Proof | Publishable | SHA-256 |\n"
        "|---|---|---|---|---|---|---|\n"
        f"| `good.riv` | `x` | a | b | written proof | {good_status} | `{good_digest}` |\n"
        f"| `bad.riv` | `x` | a | b | None | to verify | `{digest(BAD_RIV)}` |\n"
    )


def make_inputs(root, examples, provenance=None):
    package = root / "package"
    demo = root / "demo"
    assets = root / "assets"
    for directory in (package, demo, assets):
        directory.mkdir(exist_ok=True)
    (package / "package.json").write_text(json.dumps({"name": "@tweenora/webgl2", "version": "1.2.3"}))
    for name in ("rive.js", "rive.wasm", "rive_fallback.wasm", "LICENSE", "THIRD_PARTY_NOTICES"):
        (package / name).write_bytes(name.encode("utf-8"))
    (package / "rive.js.map").write_text("map")
    (package / "rive.d.ts").write_text("types")
    (demo / "index.html").write_text(INDEX)
    (demo / "demo.js").write_text("var a = 1;")
    (demo / "demo.css").write_text("a{}")
    (demo / "favicon.svg").write_text("<svg/>")
    (demo / "README.md").write_text("readme")
    (demo / "examples.json").write_text(json.dumps(examples))
    (assets / "good.riv").write_bytes(GOOD_RIV)
    (assets / "good.twno").write_bytes(b"TWNO-good")
    (assets / "bad.riv").write_bytes(BAD_RIV)
    (assets / "bad.twno").write_bytes(b"TWNO-bad")
    path = root / "ASSETS_PROVENANCE.md"
    path.write_text(provenance or provenance_text(), encoding="utf-8")
    return package, demo, assets, path


def example(identifier, name, publishable, directory="/assets"):
    return {
        "id": identifier,
        "title": identifier,
        "description": identifier,
        "file": f"{directory}/{name}.twno",
        "publishable": publishable,
    }


def parse_headers(text):
    blocks = {}
    current = None
    for line in text.splitlines():
        if line and not line.startswith(" "):
            current = line.strip()
            blocks[current] = []
        elif line.strip() and current:
            blocks[current].append(line.strip())
    return blocks


class BuildSiteTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.out = self.root / "site"

    def tearDown(self):
        self._tmp.cleanup()

    def inputs(self, examples, provenance=None):
        return make_inputs(self.root, examples, provenance)

    def build(self, examples, provenance=None, clean=False):
        package, demo, assets, path = self.inputs(examples, provenance)
        return build_site.build_site(self.out, package, demo, assets, path, clean)

    def relative_files(self):
        return sorted(p.relative_to(self.out).as_posix() for p in self.out.rglob("*") if p.is_file())

    def test_only_publishable_examples_are_kept_and_copied(self):
        self.build([example("a", "good", True), example("b", "bad", False)])
        public = json.loads((self.out / "demo" / "examples.json").read_text())
        self.assertEqual([item["id"] for item in public], ["a"])
        self.assertTrue((self.out / "assets" / "good.twno").is_file())
        self.assertFalse((self.out / "assets" / "bad.twno").exists())

    def test_the_site_holds_nothing_but_the_expected_files(self):
        result = self.build([example("a", "good", True), example("b", "bad", False)])
        tag = result["tag"]
        self.assertEqual(
            self.relative_files(),
            sorted(
                [
                    ".tweenora-site",
                    "404.html",
                    "_headers",
                    "assets/good.twno",
                    "demo/demo.css",
                    "demo/demo.js",
                    "demo/examples.json",
                    "demo/favicon.svg",
                    "demo/index.html",
                    "index.html",
                    "robots.txt",
                    "sitemap.xml",
                    "social-preview.png",
                    f"pkg/{tag}/LICENSE",
                    f"pkg/{tag}/THIRD_PARTY_NOTICES",
                    f"pkg/{tag}/rive.js",
                    f"pkg/{tag}/rive.wasm",
                    f"pkg/{tag}/rive_fallback.wasm",
                ]
            ),
        )

    def test_no_publishable_example_gives_an_empty_list_and_no_assets_folder(self):
        self.build([example("b", "bad", False)])
        self.assertEqual(json.loads((self.out / "demo" / "examples.json").read_text()), [])
        self.assertFalse((self.out / "assets").exists())

    def test_a_publishable_example_without_a_proof_is_refused(self):
        with self.assertRaises(build_site.BuildError):
            self.build([example("b", "bad", True)])

    def test_a_publishable_example_missing_from_the_table_is_refused(self):
        with self.assertRaises(build_site.BuildError):
            self.build([example("c", "unknown", True)])

    def test_a_row_marked_no_is_refused(self):
        with self.assertRaises(build_site.BuildError):
            self.build([example("a", "good", True)], provenance_text(good_status="no"))

    def test_a_riv_that_no_longer_matches_its_digest_is_refused(self):
        with self.assertRaises(build_site.BuildError):
            self.build([example("a", "good", True)], provenance_text(good_digest="0" * 16))

    def test_a_publishable_flag_that_is_not_true_is_ignored(self):
        self.build([dict(example("a", "bad", True), publishable="true")])
        self.assertEqual(json.loads((self.out / "demo" / "examples.json").read_text()), [])

    def test_an_example_outside_the_assets_folder_is_refused(self):
        with self.assertRaises(build_site.BuildError):
            self.build([example("a", "good", True, directory="/other")])
        with self.assertRaises(build_site.BuildError):
            self.build([example("a", "good", True, directory="/assets/sub")])

    def test_the_package_folder_name_follows_the_version_and_the_content(self):
        package, demo, assets, path = self.inputs([])
        first = build_site.package_tag(package)
        self.assertRegex(first, r"^1\.2\.3-[0-9a-f]{8}$")
        (package / "rive.wasm").write_bytes(b"changed")
        self.assertNotEqual(build_site.package_tag(package), first)

    def test_the_package_goes_under_its_tag_without_maps_or_types(self):
        result = self.build([])
        package = self.out / "pkg" / result["tag"]
        for name in ("rive.js", "rive.wasm", "rive_fallback.wasm", "LICENSE", "THIRD_PARTY_NOTICES"):
            self.assertTrue((package / name).is_file(), name)
        self.assertFalse((package / "rive.js.map").exists())
        self.assertFalse((package / "rive.d.ts").exists())

    def test_the_demo_page_points_at_the_tagged_package(self):
        result = self.build([])
        tag = result["tag"]
        html = (self.out / "demo" / "index.html").read_text()
        self.assertIn(f'src="/pkg/{tag}/rive.js"', html)
        self.assertIn(f'href="/pkg/{tag}/THIRD_PARTY_NOTICES"', html)
        self.assertNotIn('"/pkg/rive.js"', html)
        self.assertFalse((self.out / "demo" / "README.md").exists())

    def test_the_root_and_not_found_pages_lead_to_the_demo(self):
        self.build([])
        self.assertIn("/demo/", (self.out / "index.html").read_text())
        self.assertIn("/demo/", (self.out / "404.html").read_text())

    def test_the_root_page_is_a_real_page_and_not_a_redirect(self):
        result = self.build([])
        html = (self.out / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("http-equiv", html)
        self.assertIn("<h1", html)
        self.assertIn('href="/demo/"', html)
        self.assertIn("https://github.com/fiaaaansoo/tweenora", html)
        self.assertIn(f'href="/pkg/{result["tag"]}/THIRD_PARTY_NOTICES"', html)
        self.assertIn("not affiliated with or endorsed by its authors", html)
        self.assertIn(f'<link rel="canonical" href="{build_site.BASE_URL}/">', html)
        description = re.search(r'<meta name="description" content="([^"]+)"', html).group(1)
        self.assertTrue(120 <= len(description) <= 160, len(description))
        title = re.search(r"<title>([^<]+)</title>", html).group(1)
        self.assertLessEqual(len(title), 60)
        self.assertIn(f'<meta property="og:image" content="{build_site.BASE_URL}/social-preview.png">', html)
        self.assertIn('<meta name="twitter:card" content="summary_large_image">', html)
        data = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S).group(1))
        self.assertEqual(data["@type"], "SoftwareApplication")
        self.assertEqual(data["url"], build_site.BASE_URL + "/")
        self.assertTrue(data["isAccessibleForFree"])

    def test_the_sitemap_and_robots_describe_the_two_pages(self):
        self.build([])
        sitemap = (self.out / "sitemap.xml").read_text(encoding="utf-8")
        self.assertEqual(re.findall(r"<loc>([^<]+)</loc>", sitemap), [build_site.BASE_URL + "/", build_site.BASE_URL + "/demo/"])
        robots = (self.out / "robots.txt").read_text(encoding="utf-8")
        self.assertIn(f"Sitemap: {build_site.BASE_URL}/sitemap.xml", robots)
        self.assertNotIn("Disallow: /" + chr(10), robots)

    def test_the_package_and_assets_are_kept_out_of_the_index(self):
        result = self.build([example("a", "good", True)])
        blocks = parse_headers((self.out / "_headers").read_text())
        self.assertIn("X-Robots-Tag: noindex", blocks["/pkg/*"])
        self.assertIn("X-Robots-Tag: noindex", blocks["/assets/*"])

    def test_the_social_image_is_the_one_of_the_repository(self):
        self.build([])
        data = (self.out / "social-preview.png").read_bytes()
        self.assertEqual(data[1:4], b"PNG")
        self.assertEqual(int.from_bytes(data[16:20], "big"), 1280)
        self.assertEqual(int.from_bytes(data[20:24], "big"), 640)

    def test_the_headers_file_sets_wasm_notices_and_cache_rules(self):
        result = self.build([example("a", "good", True)])
        tag = result["tag"]
        blocks = parse_headers((self.out / "_headers").read_text())
        self.assertIn("Content-Type: application/wasm", blocks[f"/pkg/{tag}/*.wasm"])
        self.assertIn("Content-Type: text/plain; charset=utf-8", blocks[f"/pkg/{tag}/THIRD_PARTY_NOTICES"])
        self.assertIn("Content-Type: text/plain; charset=utf-8", blocks[f"/pkg/{tag}/LICENSE"])
        self.assertIn("Cache-Control: public, max-age=31536000, immutable", blocks[f"/pkg/{tag}/*"])
        self.assertIn("Cache-Control: public, max-age=0, must-revalidate", blocks["/demo/*"])
        self.assertIn("X-Content-Type-Options: nosniff", blocks["/*"])
        self.assertIn("/assets/*", blocks)

    def test_each_missing_package_file_is_refused(self):
        for name in build_site.PACKAGE_FILES:
            with self.subTest(name=name):
                package, demo, assets, path = self.fresh()
                (package / name).unlink()
                with self.assertRaises(build_site.BuildError):
                    build_site.build_site(self.out, package, demo, assets, path)

    def test_a_missing_demo_file_is_refused_before_anything_is_written(self):
        package, demo, assets, path = self.inputs([])
        (demo / "demo.css").unlink()
        with self.assertRaises(build_site.BuildError):
            build_site.build_site(self.out, package, demo, assets, path)
        self.assertFalse(self.out.exists())

    def test_a_demo_page_without_the_package_script_is_refused_before_anything_is_written(self):
        package, demo, assets, path = self.inputs([])
        (demo / "index.html").write_text("<p>no script</p>")
        with self.assertRaises(build_site.BuildError):
            build_site.build_site(self.out, package, demo, assets, path)
        self.assertFalse(self.out.exists())

    def test_a_non_empty_output_folder_is_refused(self):
        package, demo, assets, path = self.inputs([])
        self.out.mkdir()
        (self.out / "stale.txt").write_text("old")
        with self.assertRaises(build_site.BuildError):
            build_site.build_site(self.out, package, demo, assets, path)
        self.assertTrue((self.out / "stale.txt").exists())

    def test_clean_replaces_only_a_folder_the_script_built(self):
        self.build([])
        package, demo, assets, path = self.root / "package", self.root / "demo", self.root / "assets", self.root / "ASSETS_PROVENANCE.md"
        build_site.build_site(self.out, package, demo, assets, path, clean=True)
        self.assertTrue((self.out / "_headers").is_file())
        (self.out / build_site.MARKER).unlink()
        with self.assertRaises(build_site.BuildError):
            build_site.build_site(self.out, package, demo, assets, path, clean=True)
        self.assertTrue((self.out / "_headers").is_file())

    def test_main_returns_a_failure_code_and_a_message(self):
        package, demo, assets, path = self.inputs([example("b", "bad", True)])
        argv = ["--out", str(self.out), "--package", str(package), "--demo", str(demo), "--assets", str(assets), "--provenance", str(path)]
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            self.assertEqual(build_site.main(argv), 1)
        self.assertIn("build_site:", stderr.getvalue())
        self.assertFalse(self.out.exists())

    def test_main_returns_zero_when_the_site_is_built(self):
        package, demo, assets, path = self.inputs([])
        argv = ["--out", str(self.out), "--package", str(package), "--demo", str(demo), "--assets", str(assets), "--provenance", str(path)]
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            self.assertEqual(build_site.main(argv), 0)
        self.assertIn("0 public example(s)", stdout.getvalue())

    def fresh(self):
        case = Path(tempfile.mkdtemp(dir=self.root))
        return make_inputs(case, [])


class RealFilesTest(unittest.TestCase):
    def test_the_real_demo_page_has_the_two_references_the_build_rewrites(self):
        html = (REPO_DIR / "web" / "demo" / "index.html").read_text(encoding="utf-8")
        self.assertIn('"/pkg/rive.js"', html)
        self.assertIn('"/pkg/THIRD_PARTY_NOTICES"', html)

    def test_the_real_demo_page_is_ready_for_search_engines_and_link_previews(self):
        html = (REPO_DIR / "web" / "demo" / "index.html").read_text(encoding="utf-8")
        title = re.search(r"<title>([^<]+)</title>", html).group(1)
        self.assertLessEqual(len(title), 60)
        description = re.search(r'<meta name="description" content="([^"]+)"', html).group(1)
        self.assertTrue(120 <= len(description) <= 160, len(description))
        self.assertIn(f'<link rel="canonical" href="{build_site.BASE_URL}/demo/">', html)
        self.assertIn(f'<meta property="og:url" content="{build_site.BASE_URL}/demo/">', html)
        self.assertIn(f'<meta property="og:image" content="{build_site.BASE_URL}/social-preview.png">', html)
        self.assertIn('<meta name="twitter:card" content="summary_large_image">', html)
        self.assertIn('<link rel="icon" type="image/svg+xml" href="favicon.svg">', html)
        self.assertNotIn('href="data:,"', html)
        self.assertTrue((REPO_DIR / "web" / "demo" / "favicon.svg").is_file())

    def test_every_real_publishable_example_has_a_matching_proof(self):
        examples = json.loads((REPO_DIR / "web" / "demo" / "examples.json").read_text(encoding="utf-8"))
        rows = build_site.provenance_rows(REPO_DIR / "web" / "examples" / "ASSETS_PROVENANCE.md")
        for item in examples:
            if item["publishable"] is True:
                stem = item["file"].rsplit("/", 1)[1].rsplit(".", 1)[0]
                self.assertIn(stem + ".riv", rows, item["id"])
                self.assertTrue(rows[stem + ".riv"][5].startswith("yes"), item["id"])


class RealOriginalExamplesSiteTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.assets = self.root / "assets"
        self.originals = sorted((REPO_DIR / "docs" / "examples").glob("*.riv"))
        prepare_assets.prepare(prepare_assets.ASSET_SOURCES, self.assets)
        case = self.root / "case"
        case.mkdir()
        self.package = make_inputs(case, [])[0]

    def build(self):
        out = self.root / "site"
        demo = REPO_DIR / "web" / "demo"
        provenance = REPO_DIR / "web" / "examples" / "ASSETS_PROVENANCE.md"
        return build_site.build_site(out, self.package, demo, self.assets, provenance), out

    def test_the_site_holds_the_original_examples_and_only_them(self):
        result, out = self.build()
        stems = [path.stem for path in self.originals]
        public = json.loads((out / "demo" / "examples.json").read_text(encoding="utf-8"))
        self.assertEqual(sorted(item["file"] for item in public), sorted(f"/assets/{stem}.twno" for stem in stems))
        self.assertEqual(len(result["examples"]), len(stems))
        self.assertEqual(sorted(p.name for p in (out / "assets").iterdir()), sorted(f"{stem}.twno" for stem in stems))
        self.assertGreater(len(list(self.assets.glob("*.twno"))), len(stems))

    def test_no_upstream_entry_reaches_the_site(self):
        _, out = self.build()
        upstream = [
            item["file"]
            for item in json.loads((REPO_DIR / "web" / "demo" / "examples.json").read_text(encoding="utf-8"))
            if item["publishable"] is False
        ]
        self.assertTrue(upstream)
        published = {item["file"] for item in json.loads((out / "demo" / "examples.json").read_text(encoding="utf-8"))}
        self.assertFalse(published & set(upstream))
        shipped = {f"/assets/{path.name}" for path in (out / "assets").iterdir()}
        self.assertFalse(shipped & set(upstream))

    def test_an_original_example_changed_after_its_digest_was_recorded_stops_the_build(self):
        (self.assets / self.originals[0].name).write_bytes(b"RIVE-changed")
        with self.assertRaises(build_site.BuildError) as raised:
            self.build()
        self.assertIn("digest", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
