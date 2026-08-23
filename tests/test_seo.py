"""SEO verification tests for simpleisadvanced.com.

Checks local build output and optionally the live production site.

Usage:
    python3 tests/test_seo.py              # local only
    python3 tests/test_seo.py --live       # local + production
"""

import re
import json
import sys
import urllib.request
import urllib.error
from datetime import date
from pathlib import Path

SITE_DIR = Path(__file__).resolve().parent.parent
DOMAIN = "https://simpleisadvanced.com"

BOOKS = {
    "the-end-of-alignment": {"title": "The End of Alignment", "chapters": 20},
}

RETIRED_BOOKS = ("illusions-of-work", "illusions-in-the-boardroom")


def is_redirect_stub(chapter_dir):
    """A dissolved chapter slug kept as a noindex redirect to its surviving chapter.

    Stubs are deliberately excluded from the sitemap and from the chapter count.
    """
    index = chapter_dir / "index.html"
    if not index.exists():
        return False
    return 'content="noindex"' in index.read_text()


class Results:
    def __init__(self):
        self.checks = []

    def check(self, name, ok, detail=""):
        self.checks.append((name, ok, detail))

    def report(self, heading):
        passed = sum(1 for _, ok, _ in self.checks if ok)
        total = len(self.checks)
        print(f"\n{'=' * 60}")
        print(f"{heading}: {passed}/{total} passed")
        print(f"{'=' * 60}\n")
        for name, ok, detail in self.checks:
            status = "PASS" if ok else "FAIL"
            line = f"  [{status}] {name}"
            if detail:
                line += f"  ({detail})"
            print(line)
        return all(ok for _, ok, _ in self.checks)


def extract_meta(html, name):
    """Extract content attribute from a meta tag."""
    m = re.search(rf'<meta\s+name="{name}"\s+content="(.*?)"', html)
    if not m:
        m = re.search(rf'<meta\s+property="{name}"\s+content="(.*?)"', html)
    return m.group(1) if m else None


def extract_title(html):
    m = re.search(r"<title>(.*?)</title>", html)
    return m.group(1) if m else None


def extract_h1(html):
    m = re.search(r"<h1>(.*?)</h1>", html)
    return m.group(1) if m else None


def has_json_ld_field(html, schema_type, field):
    """Check if a JSON-LD block of a given @type contains a field."""
    for m in re.finditer(r'<script type="application/ld\+json">\s*(.*?)\s*</script>', html, re.DOTALL):
        try:
            data = json.loads(m.group(1))
            if data.get("@type") == schema_type and field in data:
                return True
        except json.JSONDecodeError:
            continue
    return False


def has_json_ld_type(html, schema_type):
    """Check if a JSON-LD block of a given @type exists."""
    for m in re.finditer(r'<script type="application/ld\+json">\s*(.*?)\s*</script>', html, re.DOTALL):
        try:
            data = json.loads(m.group(1))
            if data.get("@type") == schema_type:
                return True
        except json.JSONDecodeError:
            continue
    return False


# ---------------------------------------------------------------------------
# Local checks — verify the build output in site/
# ---------------------------------------------------------------------------

def check_local(r):
    # --- Homepage ---
    hp = (SITE_DIR / "index.html").read_text()
    desc = extract_meta(hp, "description")
    r.check("Homepage: description exists", desc is not None)
    if desc:
        r.check("Homepage: description <= 155 chars", len(desc) <= 155, f"{len(desc)}")
    r.check("Homepage: OG image is /og-image.png",
            'content="https://simpleisadvanced.com/og-image.png"' in hp)
    r.check("Homepage: OG image file exists", (SITE_DIR / "og-image.png").exists())
    r.check("Homepage: promotes the current book", "The End of Alignment" in hp)
    r.check("Homepage: does not promote retired books",
            "Illusions in the Boardroom" not in hp and "Illusions of Work" not in hp)
    r.check("Homepage: uses the shared editorial stylesheet", 'href="/site.css"' in hp)
    r.check("Homepage: carries the current subtitle",
            "Survival Logic for Software-Dependent Corporates in the AI Era" in hp)
    r.check("Homepage: does not claim the book is itself an operating model",
            "An operating model that joins" not in hp)

    # --- Robots.txt ---
    robots = (SITE_DIR / "robots.txt").read_text()
    r.check("Robots: no ai-illusions line", "ai-illusions" not in robots)
    r.check("Robots: blocks /the-end-of-alignment/data/", "/the-end-of-alignment/data/" in robots)
    r.check("Robots: references sitemap", "simpleisadvanced.com/sitemap.xml" in robots)

    # --- Legacy directory deleted ---
    r.check("Legacy: ai-illusions-in-the-boardroom/ gone",
            not (SITE_DIR / "ai-illusions-in-the-boardroom").exists())
    for slug in RETIRED_BOOKS:
        retired = (SITE_DIR / slug / "index.html").read_text()
        r.check(f"Retired book: {slug} is noindex", 'content="noindex,follow"' in retired)
        r.check(f"Retired book: {slug} points to the current book",
                "/the-end-of-alignment/" in retired)
        r.check(f"Retired book: {slug} has no published chapters",
                not (SITE_DIR / slug / "chapters").exists())

    # --- Sitemap ---
    sitemap = (SITE_DIR / "sitemap.xml").read_text()
    r.check("Sitemap: valid XML declaration", sitemap.startswith("<?xml"))
    r.check("Sitemap: no 0.6 priority", "<priority>0.6</priority>" not in sitemap)
    r.check("Sitemap: current preview page at 0.8",
            sitemap.count("<priority>0.8</priority>") >= 1)
    url_count = len(re.findall(r"<url>", sitemap))
    r.check("Sitemap: has 35+ URLs", url_count >= 35, f"{url_count}")
    r.check("Sitemap: retired books are absent",
            all(f"/{slug}/" not in sitemap for slug in RETIRED_BOOKS))

    # --- Sitemap completeness (catches stale fragments) ---
    locs = re.findall(r"<loc>(.*?)</loc>", sitemap)
    r.check("Sitemap: no duplicate URLs", len(locs) == len(set(locs)))

    article_dirs = sorted(d.name for d in (SITE_DIR / "articles").iterdir()
                          if d.is_dir() and (d / "index.html").exists())
    missing = [a for a in article_dirs if f"{DOMAIN}/articles/{a}/" not in locs]
    r.check("Sitemap: every article present", not missing,
            ", ".join(missing) if missing else f"{len(article_dirs)} articles")

    missing_ch = []
    for slug in BOOKS:
        ch_dir = SITE_DIR / slug / "chapters"
        if not ch_dir.exists():
            continue
        for ch_path in sorted(ch_dir.iterdir()):
            if not ch_path.is_dir() or is_redirect_stub(ch_path):
                continue
            if f"{DOMAIN}/{slug}/chapters/{ch_path.name}/" not in locs:
                missing_ch.append(f"{slug}/{ch_path.name}")
    r.check("Sitemap: every chapter present", not missing_ch,
            ", ".join(missing_ch) if missing_ch else "all OK")

    unresolved = []
    for loc in locs:
        rel = loc[len(DOMAIN):].lstrip("/")
        if rel == "" or rel.endswith("/"):
            rel += "index.html"
        if not (SITE_DIR / rel).exists():
            unresolved.append(loc)
    r.check("Sitemap: all URLs resolve to local files", not unresolved,
            ", ".join(unresolved) if unresolved else "all OK")

    lastmods = re.findall(r"<lastmod>(.*?)</lastmod>", sitemap)
    today = date.today().isoformat()
    bad_dates = [d for d in lastmods
                 if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d) or d > today]
    r.check("Sitemap: lastmod dates valid and not in the future", not bad_dates,
            ", ".join(bad_dates) if bad_dates else "all OK")

    # --- RSS feed matches articles/ directory ---
    feed_path = SITE_DIR / "articles" / "feed.xml"
    r.check("Feed: articles/feed.xml exists", feed_path.exists())
    if feed_path.exists():
        feed = feed_path.read_text()
        feed_links = set(re.findall(r"<link>(.*?)</link>", feed))
        missing_feed = [a for a in article_dirs
                        if f"{DOMAIN}/articles/{a}/" not in feed_links]
        r.check("Feed: every article present", not missing_feed,
                "; run scripts/build_articles_feed.py — " + ", ".join(missing_feed)
                if missing_feed else f"{len(article_dirs)} articles")

    # --- Articles fragment matches articles/ directory ---
    frag = (SITE_DIR / "articles" / "sitemap-fragment.xml").read_text()
    frag_locs = set(re.findall(r"<loc>(.*?)</loc>", frag))
    expected = {f"{DOMAIN}/articles/"} | {f"{DOMAIN}/articles/{a}/" for a in article_dirs}
    drift = sorted(frag_locs.symmetric_difference(expected))
    r.check("Articles fragment: matches articles/ directory", not drift,
            "; run scripts/build_articles_sitemap_fragment.py — " + ", ".join(drift)
            if drift else f"{len(article_dirs)} articles")

    stylesheet = (SITE_DIR / "site.css").read_text()
    r.check("Design: editorial fonts are declared",
            '"Instrument Sans"' in stylesheet and '"Newsreader"' in stylesheet)
    r.check("Design: article tables scroll locally",
            ".article-page table.article-table" in stylesheet
            and "overflow-x: auto" in stylesheet)
    article_pages = [(SITE_DIR / "articles" / slug / "index.html").read_text()
                     for slug in article_dirs]
    r.check("Articles: all use the shared stylesheet",
            all('href="/site.css"' in page for page in article_pages))
    r.check("Articles: retired-book promotions are gone",
            all("/illusions-of-work/" not in page
                and "/illusions-in-the-boardroom/" not in page
                for page in article_pages))

    # --- Per-book checks ---
    for slug, info in BOOKS.items():
        book_dir = SITE_DIR / slug
        book_title = info["title"]
        expected_chapters = info["chapters"]

        # Preview page
        preview = (book_dir / "preview.html").read_text()
        pdesc = extract_meta(preview, "description")
        r.check(f"{slug} preview: description exists", pdesc is not None)
        if pdesc:
            r.check(f"{slug} preview: description enriched",
                    "Browse all chapters" in pdesc, f"{len(pdesc)} chars")
            r.check(f"{slug} preview: description <= 160 chars",
                    len(pdesc) <= 160, f"{len(pdesc)}")

        # Contents page
        contents = (book_dir / "contents.html").read_text()
        cdesc = extract_meta(contents, "description")
        if cdesc:
            r.check(f"{slug} contents: description <= 155 chars",
                    len(cdesc) <= 155, f"{len(cdesc)}")

        # Chapter pages
        ch_dir = book_dir / "chapters"
        chapter_dirs = ([d for d in ch_dir.iterdir()
                         if d.is_dir() and not is_redirect_stub(d)]
                        if ch_dir.exists() else [])
        r.check(f"{slug} chapters: {expected_chapters} pages exist",
                len(chapter_dirs) == expected_chapters,
                f"found {len(chapter_dirs)}")

        # Spot-check 3 chapter pages
        for ch_path in sorted(chapter_dirs)[:3]:
            ch_html = (ch_path / "index.html").read_text()
            ch_name = ch_path.name

            title = extract_title(ch_html)
            h1 = extract_h1(ch_html)

            r.check(f"{slug}/{ch_name}: title has no 'Chapter N:'",
                    title is not None and not title.startswith("Chapter "),
                    title or "missing")
            r.check(f"{slug}/{ch_name}: description <= 155 chars",
                    len(extract_meta(ch_html, "description") or "") <= 155)
            r.check(f"{slug}/{ch_name}: BreadcrumbList schema",
                    has_json_ld_type(ch_html, "BreadcrumbList"))
            r.check(f"{slug}/{ch_name}: Chapter schema with description",
                    has_json_ld_field(ch_html, "Chapter", "description"))
            r.check(f"{slug}/{ch_name}: article:published_time",
                    extract_meta(ch_html, "article:published_time") is not None)
            r.check(f"{slug}/{ch_name}: article:author",
                    extract_meta(ch_html, "article:author") is not None)

    # Check ALL chapter descriptions are <= 155
    over = []
    for slug in BOOKS:
        ch_dir = SITE_DIR / slug / "chapters"
        if not ch_dir.exists():
            continue
        for ch_path in ch_dir.iterdir():
            if not ch_path.is_dir():
                continue
            ch_html = (ch_path / "index.html").read_text()
            d = extract_meta(ch_html, "description")
            if d and len(d) > 155:
                over.append(f"{slug}/{ch_path.name}: {len(d)}")
    r.check("All chapter descriptions <= 155 chars",
            len(over) == 0, "; ".join(over) if over else "all OK")


# ---------------------------------------------------------------------------
# Production checks — verify live site matches local
# ---------------------------------------------------------------------------

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(req).read().decode()


def fetch_head(url):
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(req)


def check_production(r):
    # --- Homepage ---
    hp = fetch(f"{DOMAIN}/")
    local_hp = (SITE_DIR / "index.html").read_text()
    r.check("LIVE homepage: description matches local",
            extract_meta(hp, "description") == extract_meta(local_hp, "description"))
    r.check("LIVE homepage: OG image serves OK",
            fetch_head(f"{DOMAIN}/og-image.png").status == 200)

    # --- Robots ---
    live_robots = fetch(f"{DOMAIN}/robots.txt")
    local_robots = (SITE_DIR / "robots.txt").read_text()
    r.check("LIVE robots.txt: matches local", live_robots.strip() == local_robots.strip())

    # --- Legacy 404 ---
    try:
        fetch(f"{DOMAIN}/ai-illusions-in-the-boardroom/")
        r.check("LIVE legacy directory: returns 404", False, "got 200")
    except urllib.error.HTTPError as e:
        r.check("LIVE legacy directory: returns 404", e.code == 404, f"HTTP {e.code}")

    # --- Sitemap ---
    live_sitemap = fetch(f"{DOMAIN}/sitemap.xml")
    r.check("LIVE sitemap: no 0.6 priority", "<priority>0.6</priority>" not in live_sitemap)
    r.check("LIVE sitemap: preview at 0.8", "<priority>0.8</priority>" in live_sitemap)

    # --- Spot-check chapter pages ---
    spot_checks = [
        ("the-end-of-alignment", "the-alignment-industrial-complex"),
        ("the-end-of-alignment", "technical-field-guide-from-milestone-to-production"),
    ]

    for book_slug, ch_slug in spot_checks:
        url = f"{DOMAIN}/{book_slug}/chapters/{ch_slug}/"
        live = fetch(url)
        local = (SITE_DIR / book_slug / "chapters" / ch_slug / "index.html").read_text()

        live_desc = extract_meta(live, "description")
        local_desc = extract_meta(local, "description")
        r.check(f"LIVE {book_slug}/{ch_slug}: description matches local",
                live_desc == local_desc,
                f"live={len(live_desc or '')} local={len(local_desc or '')}")
        r.check(f"LIVE {book_slug}/{ch_slug}: BreadcrumbList present",
                "BreadcrumbList" in live)

    # --- Preview pages ---
    for book_slug in BOOKS:
        live_prev = fetch(f"{DOMAIN}/{book_slug}/preview.html")
        local_prev = (SITE_DIR / book_slug / "preview.html").read_text()
        r.check(f"LIVE {book_slug}/preview: description matches local",
                extract_meta(live_prev, "description") == extract_meta(local_prev, "description"))

    for slug in RETIRED_BOOKS:
        retired = fetch(f"{DOMAIN}/{slug}/")
        r.check(f"LIVE retired book: {slug} is noindex", 'content="noindex,follow"' in retired)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    live = "--live" in sys.argv

    local_results = Results()
    check_local(local_results)
    all_ok = local_results.report("LOCAL CHECKS")

    if live:
        prod_results = Results()
        check_production(prod_results)
        all_ok = prod_results.report("PRODUCTION CHECKS") and all_ok

    if not live:
        print("\n  Run with --live to also check production.")

    sys.exit(0 if all_ok else 1)
