import argparse
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

DEPLOY_DIR = Path(__file__).resolve().parent
WEB_DIR = DEPLOY_DIR.parent
DEFAULT_OUT_DIR = DEPLOY_DIR / "site"
DEFAULT_PACKAGE_DIR = WEB_DIR / "rive-wasm" / "js" / "npm" / "webgl2"
DEFAULT_DEMO_DIR = WEB_DIR / "demo"
DEFAULT_ASSETS_DIR = WEB_DIR / "examples" / "assets"
DEFAULT_PROVENANCE = WEB_DIR / "examples" / "ASSETS_PROVENANCE.md"

PACKAGE_FILES = ("rive.js", "rive.wasm", "rive_fallback.wasm", "LICENSE", "THIRD_PARTY_NOTICES")
DEMO_FILES = ("index.html", "demo.css", "demo.js", "favicon.svg")
MARKER = ".tweenora-site"
IMMUTABLE = "public, max-age=31536000, immutable"
REVALIDATE = "public, max-age=0, must-revalidate"
ASSET_CACHE = "public, max-age=3600"

BASE_URL = "https://tweenora-demo.pages.dev"
REPO_URL = "https://github.com/fiaaaansoo/tweenora"
DEFAULT_SOCIAL_IMAGE = WEB_DIR.parent / "docs" / "images" / "social-preview.png"
ROOT_TITLE = "Tweenora: open source vector animation runtime"
ROOT_DESCRIPTION = (
    "Open source runtime that plays interactive vector animations with state machines "
    "in the browser (WebAssembly, WebGL2). Reads .twno and .riv files."
)
ROOT_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>{title}</title>
<meta name="description" content="{description}">
<link rel="canonical" href="{base}/">
<link rel="icon" type="image/svg+xml" href="/demo/favicon.svg">
<meta property="og:type" content="website">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{description}">
<meta property="og:url" content="{base}/">
<meta property="og:image" content="{base}/social-preview.png">
<meta name="twitter:card" content="summary_large_image">
<script type="application/ld+json">{ld}</script>
<style>
body{{font:1rem/1.6 system-ui,sans-serif;max-width:40rem;margin:0 auto;padding:2rem 1rem;color:#1d2b2a;background:#f4f1ea}}
@media(prefers-color-scheme:dark){{body{{color:#e8efed;background:#0f2b2a}}a{{color:#7fd0c3}}}}
.cta{{display:inline-block;margin:.5rem 0;padding:.6rem 1.2rem;border-radius:.5rem;background:#0f6b5e;color:#fff;text-decoration:none}}
footer{{margin-top:2rem;font-size:.875rem}}
</style>
</head>
<body>
<main>
<h1>Tweenora</h1>
<p>Tweenora is an open source vector animation runtime. It plays interactive animations driven by state machines in the browser (WebAssembly, WebGL2) and reads <code>.twno</code> and <code>.riv</code> files.</p>
<p><a class="cta" href="/demo/">Open the demo</a> or read the code on <a href="{repo}">GitHub</a>.</p>
</main>
<footer>
<p>Derived from an MIT-licensed upstream runtime; independent project, not affiliated with or endorsed by its authors.</p>
<p><a href="/pkg/{tag}/THIRD_PARTY_NOTICES">Licenses and third-party notices</a></p>
</footer>
</body>
</html>
"""
NOT_FOUND_PAGE = (
    '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
    "<title>Page not found</title>\n</head>\n"
    '<body>\n<p>Page not found. <a href="/demo/">Open the Tweenora demo</a></p>\n</body>\n</html>\n'
)


class BuildError(Exception):
    pass


def provenance_rows(path):
    rows = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        match = re.match(r"^\| `([^`]+)` \|", line)
        if match:
            rows[match.group(1)] = [cell.strip() for cell in line.strip().strip("|").split("|")]
    return rows


def package_tag(package_dir):
    package_dir = Path(package_dir)
    version = json.loads((package_dir / "package.json").read_text(encoding="utf-8"))["version"]
    digest = hashlib.sha256()
    for name in PACKAGE_FILES:
        digest.update(name.encode("utf-8"))
        digest.update((package_dir / name).read_bytes())
    return f"{version}-{digest.hexdigest()[:8]}"


def file_digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:16]


def publishable_examples(examples, rows, assets_dir):
    assets_dir = Path(assets_dir)
    kept = []
    for item in examples:
        if item.get("publishable") is not True:
            continue
        file = item["file"]
        if not file.startswith("/assets/") or file.count("/") != 2:
            raise BuildError(f"{item['id']}: {file} must be a file directly under /assets/")
        name = file.rsplit("/", 1)[1]
        stem = name.rsplit(".", 1)[0]
        row = rows.get(stem + ".riv")
        if row is None or not row[5].startswith("yes"):
            raise BuildError(f"{item['id']}: {stem}.riv is not marked publishable in the provenance table")
        source = assets_dir / (stem + ".riv")
        if not source.is_file() or not (assets_dir / name).is_file():
            raise BuildError(f"{item['id']}: {stem}.riv or {name} is missing, run web/examples/prepare_assets.py")
        if file_digest(source) != row[6].strip("`"):
            raise BuildError(f"{item['id']}: {source.name} does not match the digest in the provenance table")
        kept.append(item)
    return kept


def headers_text(tag, with_assets):
    rules = [
        ("/*", ["X-Content-Type-Options: nosniff"]),
        (f"/pkg/{tag}/*", [f"Cache-Control: {IMMUTABLE}"]),
        (f"/pkg/{tag}/*.wasm", ["Content-Type: application/wasm"]),
        (f"/pkg/{tag}/THIRD_PARTY_NOTICES", ["Content-Type: text/plain; charset=utf-8"]),
        (f"/pkg/{tag}/LICENSE", ["Content-Type: text/plain; charset=utf-8"]),
        ("/pkg/*", ["X-Robots-Tag: noindex"]),
        ("/demo/*", [f"Cache-Control: {REVALIDATE}"]),
        ("/", [f"Cache-Control: {REVALIDATE}"]),
    ]
    if with_assets:
        rules.append(("/assets/*", [f"Cache-Control: {ASSET_CACHE}", "X-Robots-Tag: noindex"]))
    return "\n\n".join(path + "\n" + "\n".join("  " + line for line in lines) for path, lines in rules) + "\n"


def root_page(tag):
    data = {
        "@context": "https://schema.org",
        "@type": "SoftwareApplication",
        "name": "Tweenora",
        "description": ROOT_DESCRIPTION,
        "applicationCategory": "DeveloperApplication",
        "operatingSystem": "Web",
        "url": BASE_URL + "/",
        "license": "https://opensource.org/licenses/MIT",
        "isAccessibleForFree": True,
    }
    return ROOT_PAGE.format(
        title=ROOT_TITLE,
        description=ROOT_DESCRIPTION,
        base=BASE_URL,
        repo=REPO_URL,
        tag=tag,
        ld=json.dumps(data, ensure_ascii=False),
    )


def sitemap_text():
    urls = "".join(f"  <url><loc>{BASE_URL}{path}</loc></url>\n" for path in ("/", "/demo/"))
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{urls}</urlset>\n"
    )


def robots_text():
    return f"User-agent: *\nAllow: /\n\nSitemap: {BASE_URL}/sitemap.xml\n"


def rewrite_page(html, tag):
    for old, new in (
        ('"/pkg/rive.js"', f'"/pkg/{tag}/rive.js"'),
        ('"/pkg/THIRD_PARTY_NOTICES"', f'"/pkg/{tag}/THIRD_PARTY_NOTICES"'),
    ):
        if old not in html:
            raise BuildError(f"the demo page does not contain {old}")
        html = html.replace(old, new)
    return html


def prepare_output(out_dir, clean):
    out_dir = Path(out_dir)
    if out_dir.exists() and any(out_dir.iterdir()):
        if clean and (out_dir / MARKER).is_file():
            shutil.rmtree(out_dir)
        else:
            raise BuildError(f"{out_dir} is not empty (use --clean on a folder this script built)")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / MARKER).write_text("built by web/deploy/build_site.py\n", encoding="utf-8", newline="\n")
    return out_dir


def write_text(path, text):
    Path(path).write_text(text, encoding="utf-8", newline="\n")


def build_site(out_dir, package_dir, demo_dir, assets_dir, provenance, clean=False, social_image=DEFAULT_SOCIAL_IMAGE):
    package_dir, demo_dir, assets_dir = Path(package_dir), Path(demo_dir), Path(assets_dir)
    for name in PACKAGE_FILES:
        if not (package_dir / name).is_file():
            raise BuildError(f"{package_dir / name} is missing, build the package first")
    for name in DEMO_FILES + ("examples.json",):
        if not (demo_dir / name).is_file():
            raise BuildError(f"{demo_dir / name} is missing")
    tag = package_tag(package_dir)
    examples = json.loads((demo_dir / "examples.json").read_text(encoding="utf-8"))
    public = publishable_examples(examples, provenance_rows(provenance), assets_dir)
    page = rewrite_page((demo_dir / "index.html").read_text(encoding="utf-8"), tag)

    out = prepare_output(out_dir, clean)
    pkg_out = out / "pkg" / tag
    pkg_out.mkdir(parents=True)
    for name in PACKAGE_FILES:
        shutil.copyfile(package_dir / name, pkg_out / name)

    demo_out = out / "demo"
    demo_out.mkdir()
    for name in DEMO_FILES:
        shutil.copyfile(demo_dir / name, demo_out / name)
    write_text(demo_out / "index.html", page)
    write_text(demo_out / "examples.json", json.dumps(public, indent=2, ensure_ascii=False) + "\n")

    if public:
        assets_out = out / "assets"
        assets_out.mkdir()
        for item in public:
            name = item["file"].rsplit("/", 1)[1]
            shutil.copyfile(assets_dir / name, assets_out / name)

    shutil.copyfile(social_image, out / "social-preview.png")
    write_text(out / "index.html", root_page(tag))
    write_text(out / "sitemap.xml", sitemap_text())
    write_text(out / "robots.txt", robots_text())
    write_text(out / "404.html", NOT_FOUND_PAGE)
    write_text(out / "_headers", headers_text(tag, bool(public)))
    return {"tag": tag, "examples": [item["id"] for item in public], "out": str(out)}


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Assemble the static folder to publish for the Tweenora demo. Nothing is deployed."
    )
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--package", type=Path, default=DEFAULT_PACKAGE_DIR)
    parser.add_argument("--demo", type=Path, default=DEFAULT_DEMO_DIR)
    parser.add_argument("--assets", type=Path, default=DEFAULT_ASSETS_DIR)
    parser.add_argument("--provenance", type=Path, default=DEFAULT_PROVENANCE)
    parser.add_argument("--clean", action="store_true", help="replace a folder this script built earlier")
    args = parser.parse_args(argv)
    try:
        result = build_site(args.out, args.package, args.demo, args.assets, args.provenance, args.clean)
    except BuildError as error:
        print(f"build_site: {error}", file=sys.stderr)
        return 1
    print(f"{result['out']}: package {result['tag']}, {len(result['examples'])} public example(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
