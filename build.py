#!/usr/bin/env python3
"""Build the Left Main Help Center static site from content/ + categories.json.

Usage:
    python3 build.py            # builds into _site/
    python3 build.py --out DIR  # builds into a custom output directory
                                 # (never the project root - see safety check below)

No third-party dependencies - stdlib only, so this runs anywhere, including
in the GitHub Actions workflow with no pip install step.

How to edit content:
  - To change an existing article: edit its file under content/<category>/<article>.html.
    The top of the file is a small front-matter comment (title / order / optional
    subcat); everything after the closing "-->" is the article body, written as
    plain HTML (headings, paragraphs, lists, tables, images...).
  - To add a new article: create a new .html file in the right content/<category>/
    folder, following the same front-matter + body pattern. Pick an `order` number
    to control where it sits in that category's article list.
  - To add a brand-new category: create a new folder under content/, add an entry
    for its slug to categories.json ({"title": "...", "order": N}), then add article
    files to it as above.
  - Images/screenshots go in assets/images/ (or assets/files/ for non-image
    attachments like PDFs/videos); reference them from an article body as
    "assets/images/your-file.png" (same path from every article - the build
    script rewrites it to the right relative depth automatically).
  - Commit and push. GitHub Actions rebuilds and redeploys the site automatically
    within about a minute - no local build step required.
"""
import argparse, json, re, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONTENT_DIR = ROOT / "content"
CATEGORIES_FILE = ROOT / "categories.json"

FRONT_MATTER_RE = re.compile(r"^<!--\s*(.*?)\s*-->\s*", re.S)
HEADING_RE = re.compile(r'<h2[^>]*\bid="([^"]*)"[^>]*>(.*?)</h2>', re.S)
TAG_RE = re.compile(r"<[^<]+?>")
ASSET_SRC_RE = re.compile(r'(src|href)="assets/')

HAMBURGER_SVG = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>'


def parse_front_matter(text):
    m = FRONT_MATTER_RE.match(text)
    meta = {}
    body = text
    if m:
        for line in m.group(1).splitlines():
            line = line.strip()
            if ":" in line:
                k, _, v = line.partition(":")
                meta[k.strip()] = v.strip()
        body = text[m.end():]
    return meta, body.strip()


def load_categories():
    cats_meta = json.loads(CATEGORIES_FILE.read_text())
    categories = []
    for cat_dir in sorted(CONTENT_DIR.iterdir()):
        if not cat_dir.is_dir():
            continue
        slug = cat_dir.name
        meta = cats_meta.get(slug, {"title": slug.replace("-", " ").title(), "order": 999})
        articles = []
        for art_file in sorted(cat_dir.glob("*.html")):
            fm, body = parse_front_matter(art_file.read_text())
            articles.append({
                "slug": art_file.stem,
                "title": fm.get("title", art_file.stem.replace("-", " ").title()),
                "order": int(fm.get("order", 999)) if fm.get("order", "").strip().lstrip("-").isdigit() else 999,
                "subcat": fm.get("subcat") or None,
                "html": body,
            })
        if not articles:
            continue
        categories.append({
            "slug": slug, "title": meta["title"], "order": meta.get("order", 999),
            "articles": sorted(articles, key=lambda a: a["order"]),
        })
    categories.sort(key=lambda c: c["order"])
    return categories


def build_toc(html):
    return [(TAG_RE.sub("", text).strip(), hid) for hid, text in HEADING_RE.findall(html)]


STYLES = (ROOT / "styles.css").read_text() if (ROOT / "styles.css").exists() else ""
SCRIPT_JS = (ROOT / "script.js").read_text() if (ROOT / "script.js").exists() else ""


def render_sidebar(categories, prefix, active_cat_slug=None, active_art_slug=None):
    out = ['<nav class="sidebar" id="sidebar">']
    out.append('<div class="brand-mark"><span class="word">Left&nbsp;Main</span><span class="tag">Help Center</span></div>')
    home_active = " active" if active_cat_slug is None else ""
    out.append(f'<a class="sidebar-home{home_active}" href="{prefix}index.html">Overview</a>')
    for cat in categories:
        is_current = cat["slug"] == active_cat_slug
        open_attr = " open" if is_current else ""
        cur_class = " current-category" if is_current else ""
        out.append(f'<details class="{cur_class.strip()}"{open_attr}>')
        out.append(f'<summary><a href="{prefix}{cat["slug"]}/index.html" style="color:inherit;text-decoration:none;flex:1;">{cat["title"]}</a></summary>')
        out.append('<ul class="cat-articles">')
        for art in cat["articles"]:
            cls = " active" if (is_current and art["slug"] == active_art_slug) else ""
            out.append(f'<li><a class="{cls.strip()}" href="{prefix}{cat["slug"]}/{art["slug"]}.html">{art["title"]}</a></li>')
        out.append("</ul></details>")
    out.append(f'<div class="sidebar-footer"><a href="{prefix}editor/index.html" style="color:inherit;">Edit this site</a></div>')
    out.append("</nav>")
    return "\n".join(out)


def page_shell(categories, title, description, prefix, active_cat_slug, active_art_slug, body_html, crumb_html=""):
    sidebar = render_sidebar(categories, prefix, active_cat_slug, active_art_slug)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{title}</title>
<meta name="description" content="{description}">
<link rel="stylesheet" href="{prefix}styles.css">
</head>
<body>
<div class="topbar">
  <button class="hamburger" id="menuBtn" aria-label="Open navigation" aria-expanded="false">{HAMBURGER_SVG}</button>
  <span class="word">Left Main Help Center</span>
</div>
<div class="scrim" id="scrim"></div>
<div class="shell">
{sidebar}
<main class="main"><div class="main-inner">
{crumb_html}
{body_html}
</div></main>
</div>
<script src="{prefix}script.js"></script>
</body>
</html>
"""


def rewrite_asset_paths(html, prefix):
    """Article bodies always reference assets as 'assets/...'; rewrite to the
    right relative depth for where the page actually lives."""
    return ASSET_SRC_RE.sub(lambda m: f'{m.group(1)}="{prefix}assets/', html)


# Paths the build is never allowed to delete, even if passed as --out: the
# project root itself, or anything that looks like the project (has a
# content/ folder or a .git folder of its own). This script only ever
# deletes directories it is about to fully regenerate as a build artifact.
def assert_safe_output_dir(out_dir):
    if out_dir == ROOT:
        raise SystemExit(f"Refusing to build into the project root ({ROOT}). Use --out to pick a build directory, e.g. _site.")
    if (out_dir / "content").is_dir() or (out_dir / ".git").is_dir() or (out_dir / "build.py").exists():
        raise SystemExit(f"Refusing to build into {out_dir}: it looks like a source directory, not a build output directory.")


def build(out_dir):
    categories = load_categories()
    assert_safe_output_dir(out_dir)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    (out_dir / "styles.css").write_text(STYLES)
    (out_dir / "script.js").write_text(SCRIPT_JS)
    if (ROOT / "assets").exists():
        shutil.copytree(ROOT / "assets", out_dir / "assets")
    if (ROOT / "editor").exists():
        shutil.copytree(ROOT / "editor", out_dir / "editor")

    (out_dir / "content-index.json").write_text(json.dumps({
        "categories": [
            {
                "slug": c["slug"], "title": c["title"],
                "articles": [{"slug": a["slug"], "title": a["title"]} for a in c["articles"]],
            }
            for c in categories
        ]
    }, indent=2))

    total_articles = sum(len(c["articles"]) for c in categories)
    cards = []
    for cat in categories:
        n = len(cat["articles"])
        cards.append(
            f'<a class="cat-card" href="{cat["slug"]}/index.html"><h3>{cat["title"]}</h3>'
            f'<div class="count">{n} article{"s" if n != 1 else ""}</div></a>'
        )
    home_body = f"""
<div class="hero">
  <span class="eyebrow">Left Main Help Center</span>
  <h1>Everything you need to run your deals in Left Main</h1>
  <p class="lede">{total_articles} articles across {len(categories)} topics &mdash; browse by category below.</p>
</div>
<div class="cat-grid">
{''.join(cards)}
</div>
"""
    (out_dir / "index.html").write_text(
        page_shell(categories, "Left Main Help Center", "Help center for the Left Main REI Salesforce product.",
                   "", None, None, home_body)
    )

    for cat in categories:
        cat_dir = out_dir / cat["slug"]
        cat_dir.mkdir(parents=True, exist_ok=True)

        groups, order_list = {}, []
        for art in cat["articles"]:
            key = art["subcat"]
            if key not in groups:
                groups[key] = []
                order_list.append(key)
            groups[key].append(art)

        listing = []
        for key in order_list:
            if key:
                listing.append(f'<div class="subcat-label">{key}</div>')
            listing.append('<ul class="article-list">')
            for art in groups[key]:
                listing.append(f'<li><a href="{art["slug"]}.html">{art["title"]}</a></li>')
            listing.append("</ul>")

        n = len(cat["articles"])
        cat_body = f"""
<span class="eyebrow">Category</span>
<h1>{cat["title"]}</h1>
<p class="lede" style="color:var(--fg-muted);">{n} article{"s" if n != 1 else ""} in this section.</p>
{''.join(listing)}
"""
        crumb = f'<div class="crumb"><a href="../index.html">Overview</a> / {cat["title"]}</div>'
        (cat_dir / "index.html").write_text(
            page_shell(categories, f'{cat["title"]} — Left Main Help Center',
                       f'{cat["title"]} articles in the Left Main help center.',
                       "../", cat["slug"], None, cat_body, crumb)
        )

        for art in cat["articles"]:
            body = rewrite_asset_paths(art["html"], "../")
            toc = build_toc(body)
            toc_html = ""
            if len(toc) > 2:
                links = "".join(f'<a href="#{hid}">{txt}</a>' for txt, hid in toc)
                toc_html = f'<nav class="toc"><span class="label">On this page</span>{links}</nav>'
            art_body = f"""
<span class="eyebrow">{cat["title"]}</span>
<h1>{art["title"]}</h1>
{toc_html}
{body}
"""
            crumb = f'<div class="crumb"><a href="../index.html">Overview</a> / <a href="index.html">{cat["title"]}</a> / {art["title"]}</div>'
            (cat_dir / f'{art["slug"]}.html').write_text(
                page_shell(categories, f'{art["title"]} — Left Main Help Center',
                           f'{art["title"]} — Left Main help center.',
                           "../", cat["slug"], art["slug"], art_body, crumb)
            )

    print(f"Built {total_articles} article pages + {len(categories)} category indexes + home page -> {out_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="_site")
    args = parser.parse_args()
    build((ROOT / args.out).resolve())
