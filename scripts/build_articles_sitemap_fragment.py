"""Generate articles/sitemap-fragment.xml from the article pages.

Scans articles/*/index.html and writes one entry per article plus the
articles hub. Entries carry loc and priority only: lastmod is assigned
by scripts/assemble_sitemap.py from content hashes, so dates reflect
real page changes rather than build runs.

Run after adding or removing an article, then reassemble the sitemap:

    python3 scripts/build_articles_sitemap_fragment.py
    python3 scripts/assemble_sitemap.py

tests/test_seo.py fails if the fragment does not match the articles/
directory, so a forgotten run is caught before publish.
"""

import json
import re
from pathlib import Path

SITE_DIR = Path(__file__).resolve().parent.parent
ARTICLES_DIR = SITE_DIR / "articles"
OUT_PATH = ARTICLES_DIR / "sitemap-fragment.xml"

DOMAIN = "https://simpleisadvanced.com"


def date_published(html):
    """Read datePublished from the Article JSON-LD block (used for ordering)."""
    for m in re.finditer(r'<script type="application/ld\+json">\s*(.*?)\s*</script>',
                         html, re.DOTALL):
        try:
            data = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        if data.get("@type") == "Article" and data.get("datePublished"):
            return data["datePublished"]
    return "9999-12-31"


def build_fragment():
    articles = []
    for page in sorted(ARTICLES_DIR.glob("*/index.html")):
        slug = page.parent.name
        articles.append((date_published(page.read_text()), slug))
    articles.sort()

    entries = [f"""  <url>
    <loc>{DOMAIN}/articles/</loc>
    <priority>0.8</priority>
  </url>"""]

    for _, slug in articles:
        entries.append(f"""  <url>
    <loc>{DOMAIN}/articles/{slug}/</loc>
    <priority>0.7</priority>
  </url>""")

    OUT_PATH.write_text("\n".join(entries) + "\n")
    print(f"Articles sitemap fragment: {len(articles)} articles -> {OUT_PATH.relative_to(SITE_DIR)}")


if __name__ == "__main__":
    build_fragment()
