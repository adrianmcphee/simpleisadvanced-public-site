#!/usr/bin/env python3
"""Generate chapter landing pages for SEO."""

import json
import os
import re
import html

SITE_DIR = os.path.dirname(os.path.abspath(__file__))
DOMAIN = "https://simpleisadvanced.com"

BOOKS = [
    {"slug": "illusions-of-work"},
    {"slug": "ai-illusions-in-the-boardroom"},
]


def slugify(title):
    s = title.lower()
    s = re.sub(r'[^\w\s-]', '', s)
    s = re.sub(r'[\s_]+', '-', s)
    s = re.sub(r'-+', '-', s)
    return s.strip('-')


def fix_hyphens(text):
    """Fix broken hyphens from word-by-word format: 'software- dependent' -> 'software-dependent'."""
    return re.sub(r'(\w)- (\w)', r'\1-\2', text)


def words_to_paragraphs(words, max_paragraphs=3):
    """Convert word array to list of paragraph strings.

    p:heading marks the last word of a heading block.
    p:paragraph marks the last word of a paragraph block.
    """
    paragraphs = []
    current = []

    for obj in words:
        w = obj.get("w", "")
        p = obj.get("p", "")

        current.append(w)

        if p == "heading":
            # Everything accumulated is heading text — discard
            current = []
        elif p == "paragraph":
            text = fix_hyphens(" ".join(current).strip())
            if text:
                paragraphs.append(text)
            current = []
            if len(paragraphs) >= max_paragraphs:
                break

    return paragraphs[:max_paragraphs]


def make_description(paragraphs, max_len=155):
    if not paragraphs:
        return ""
    text = re.sub(r'\s+', ' ', paragraphs[0]).strip()
    text = html.escape(text, quote=True)
    if len(text) > max_len:
        text = text[:max_len - 3].rsplit(' ', 1)[0] + "..."
    return text


def generate_chapter_html(book_meta, chapter, paragraphs, prev_ch, next_ch, book_slug):
    title = chapter["title"]
    ch_num = chapter.get("chapterNum")
    part = chapter.get("part", "")
    book_title = book_meta["title"]
    author = book_meta["author"]
    ch_id = chapter["id"]

    display_title = f"Chapter {ch_num}: {title}" if ch_num else title
    page_title = html.escape(f"{display_title} — {book_title} by {author}")
    desc = make_description(paragraphs)
    ch_slug = chapter.get("slug") or slugify(title)
    canonical = f"{DOMAIN}/{book_slug}/chapters/{ch_slug}/"
    reader_url = f"/{book_slug}/#{ch_slug}"
    og_image = f"{DOMAIN}/{book_slug}/og-image.png"

    excerpt_html = "\n".join(f"<p>{html.escape(p)}</p>" for p in paragraphs)
    part_html = f'\n  <p class="part">{html.escape(part)}</p>' if part else ''

    nav_links = []
    if prev_ch:
        ps = slugify(prev_ch["title"])
        pl = f'Chapter {prev_ch["chapterNum"]}' if prev_ch.get("chapterNum") else prev_ch["title"]
        nav_links.append(f'<a href="../{ps}/">&larr; {html.escape(pl)}</a>')
    else:
        nav_links.append('<span></span>')
    if next_ch:
        ns = slugify(next_ch["title"])
        nl = f'Chapter {next_ch["chapterNum"]}' if next_ch.get("chapterNum") else next_ch["title"]
        nav_links.append(f'<a href="../{ns}/">{html.escape(nl)} &rarr;</a>')
    else:
        nav_links.append('<span></span>')

    json_ld = json.dumps({
        "@context": "https://schema.org",
        "@type": "Chapter",
        "name": display_title,
        "isPartOf": {
            "@type": "Book",
            "name": book_title,
            "author": {"@type": "Person", "name": author, "url": "https://www.linkedin.com/in/adrianmcphee/"},
            "url": f"{DOMAIN}/{book_slug}/"
        },
        "url": canonical,
        "position": ch_id
    }, indent=4)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{page_title}</title>
  <meta name="description" content="{desc}">
  <meta name="author" content="{html.escape(author)}">
  <meta name="robots" content="max-snippet:300">
  <link rel="canonical" href="{canonical}">
  <meta property="og:type" content="article">
  <meta property="og:title" content="{page_title}">
  <meta property="og:description" content="{desc}">
  <meta property="og:image" content="{og_image}">
  <meta property="og:url" content="{canonical}">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{page_title}">
  <meta name="twitter:description" content="{desc}">
  <meta name="twitter:image" content="{og_image}">
  <script type="application/ld+json">
  {json_ld}
  </script>
  <script async src="https://plausible.io/js/pa-0ytLBSTECJdL8sUA_8nHO.js"></script>
  <script>
    window.plausible=window.plausible||function(){{(plausible.q=plausible.q||[]).push(arguments)}},plausible.init=plausible.init||function(i){{plausible.o=i||{{}}}};
    plausible.init()
  </script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    body {{ max-width: 42em; margin: 2em auto; padding: 0 1.5em; font-family: Georgia, serif;
           line-height: 1.7; color: #222; background: #fff; }}
    h1 {{ font-family: 'Inter', system-ui, sans-serif; font-size: 1.6em; margin-bottom: 0.3em;
          letter-spacing: -0.02em; }}
    .part {{ font-size: 0.8em; text-transform: uppercase; letter-spacing: 0.1em;
             color: #999; margin-bottom: 0; font-family: 'Inter', system-ui, sans-serif; }}
    .book-link {{ font-size: 0.85em; color: #999; text-decoration: none;
                  font-family: 'Inter', system-ui, sans-serif; display: inline-block; margin-bottom: 2em; }}
    .book-link:hover {{ color: #222; }}
    p {{ margin: 0.8em 0; }}
    .ellipsis {{ color: #999; font-size: 1.2em; letter-spacing: 0.3em; margin: 1.5em 0; }}
    .cta {{ text-align: center; margin: 2.5em 0; padding: 1.5em; background: #f9f9f9;
            border-radius: 8px; font-family: 'Inter', system-ui, sans-serif; }}
    .cta a {{ display: inline-block; padding: 0.7em 2em; background: #222; color: #fff;
             text-decoration: none; border-radius: 4px; font-weight: 600; font-size: 0.9em; }}
    .cta a:hover {{ background: #444; }}
    .cta p {{ font-size: 0.85em; color: #666; margin-bottom: 0.8em; }}
    .nav {{ display: flex; justify-content: space-between; margin-top: 2em; padding-top: 1.5em;
            border-top: 1px solid #e5e5e5; font-family: 'Inter', system-ui, sans-serif; font-size: 0.85em; }}
    .nav a {{ color: #999; text-decoration: none; }}
    .nav a:hover {{ color: #222; }}
    footer {{ text-align: center; color: #999; font-size: 0.85em; margin-top: 2em;
             padding-top: 1.5em; border-top: 1px solid #e5e5e5; }}
    footer a {{ color: #999; }}
  </style>
</head>
<body>
  <a class="book-link" href="/{book_slug}/">&larr; {html.escape(book_title)}</a>{part_html}
  <h1>{html.escape(display_title)}</h1>

  {excerpt_html}
  <p class="ellipsis">...</p>

  <div class="cta">
    <p>Continue reading in the interactive reader</p>
    <a href="{reader_url}">Read this chapter</a>
  </div>

  <div class="nav">{nav_links[0]}{nav_links[1]}</div>

  <footer>
    <p>&copy; {html.escape(author)} 2026 &middot;
    <a href="https://www.linkedin.com/in/adrianmcphee/">Contact</a></p>
  </footer>
</body>
</html>
"""


def main():
    for book in BOOKS:
        slug = book["slug"]
        data_dir = os.path.join(SITE_DIR, slug, "data")
        chapters_dir = os.path.join(SITE_DIR, slug, "chapters")

        with open(os.path.join(data_dir, "meta.json")) as f:
            meta = json.load(f)

        chapters = [c for c in meta["chapters"] if c["title"] != "About the Author"]
        os.makedirs(chapters_dir, exist_ok=True)

        for i, ch in enumerate(chapters):
            ch_file = os.path.join(data_dir, f"ch{ch['id']:02d}.json")
            if not os.path.exists(ch_file):
                continue
            with open(ch_file) as f:
                words = json.load(f)
            paragraphs = words_to_paragraphs(words, max_paragraphs=4)
            if not paragraphs:
                continue

            prev_ch = chapters[i - 1] if i > 0 else None
            next_ch = chapters[i + 1] if i < len(chapters) - 1 else None

            ch_slug = ch.get("slug") or slugify(ch["title"])
            ch_dir = os.path.join(chapters_dir, ch_slug)
            os.makedirs(ch_dir, exist_ok=True)

            content = generate_chapter_html(meta, ch, paragraphs, prev_ch, next_ch, slug)
            with open(os.path.join(ch_dir, "index.html"), "w") as f:
                f.write(content)
            print(f"  {slug}/chapters/{ch_slug}/")

    print("Done.")


if __name__ == "__main__":
    main()
