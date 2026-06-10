"""Generate articles/feed.xml (RSS 2.0) from the article pages.

Reads headline, description, url, and datePublished from each article's
Article JSON-LD block. Run after adding or editing an article:

    python3 scripts/build_articles_feed.py

tests/test_seo.py fails if the feed does not match the articles/
directory, so a forgotten run is caught before publish.
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

SITE_DIR = Path(__file__).resolve().parent.parent
ARTICLES_DIR = SITE_DIR / "articles"
OUT_PATH = ARTICLES_DIR / "feed.xml"

DOMAIN = "https://simpleisadvanced.com"
CHANNEL_DESCRIPTION = (
    "How software-dependent corporates built structures that reward the "
    "appearance of productivity over actual productivity, and why AI "
    "changes the economics. Articles by Adrian McPhee."
)


def article_meta(html_text):
    for m in re.finditer(r'<script type="application/ld\+json">\s*(.*?)\s*</script>',
                         html_text, re.DOTALL):
        try:
            data = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        if data.get("@type") == "Article":
            return data
    return None


def rfc822(day):
    dt = datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return dt.strftime("%a, %d %b %Y 00:00:00 +0000")


def build_feed():
    articles = []
    for page in sorted(ARTICLES_DIR.glob("*/index.html")):
        meta = article_meta(page.read_text())
        if not meta:
            raise SystemExit(f"No Article JSON-LD in {page}")
        articles.append(meta)
    articles.sort(key=lambda a: (a["datePublished"], a["url"]), reverse=True)

    items = []
    for a in articles:
        items.append(f"""    <item>
      <title>{escape(a["headline"])}</title>
      <link>{escape(a["url"])}</link>
      <guid isPermaLink="true">{escape(a["url"])}</guid>
      <pubDate>{rfc822(a["datePublished"])}</pubDate>
      <description>{escape(a["description"])}</description>
    </item>""")

    OUT_PATH.write_text(f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>Simple is Advanced — Articles</title>
    <link>{DOMAIN}/articles/</link>
    <atom:link href="{DOMAIN}/articles/feed.xml" rel="self" type="application/rss+xml"/>
    <description>{escape(CHANNEL_DESCRIPTION)}</description>
    <language>en</language>
{chr(10).join(items)}
  </channel>
</rss>
""")
    print(f"RSS feed: {len(articles)} articles -> {OUT_PATH.relative_to(SITE_DIR)}")


if __name__ == "__main__":
    build_feed()
