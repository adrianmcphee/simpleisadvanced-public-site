#!/usr/bin/env python3
"""Generate chapter landing pages for SEO.

Each chapter gets a lightweight HTML page with:
- 2-3 paragraph excerpt
- Proper meta tags and JSON-LD
- CTA to the interactive reader
- Prev/next navigation
"""

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


def words_to_paragraphs(words, max_paragraphs=3):
    """Convert word array to list of paragraph strings."""
    paragraphs = []
    current = []
    in_heading = False

    for obj in words:
        w = obj.get("w", "")
        p = obj.get("p", "")

        if p == "heading":
            # If we've accumulated words, flush them
            if current:
                text = " ".join(current).strip()
                if text:
                    paragraphs.append(text)
                current = []
                if len(paragraphs) >= max_paragraphs:
                    break
            in_heading = True
            continue

        in_heading = False
        current.append(w)

        if p == "paragraph":
            text = " ".join(current).strip()
            if text:
                paragraphs.append(text)
            current = []
            if len(paragraphs) >= max_paragraphs:
                break

    if current and len(paragraphs) < max_paragraphs:
        text = " ".join(current).strip()
        if text:
            paragraphs.append(text)

    return paragraphs[:max_paragraphs]


def make_description(paragraphs, max_len=155):
    if not paragraphs:
        return ""
    text = re.sub(r'\s+', ' ', paragraphs[0]).strip()
    # Escape HTML entities for meta tags
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

    if ch_num:
        display_title = f"Chapter {ch_num}: {title}"
    else:
        display_title = title

    page_title = html.escape(f"{display_title} — {book_title} by {author}")
    desc = make_description(paragraphs)
    ch_slug = slugify(title)
    canonical = f"{DOMAIN}/{book_slug}/chapters/{ch_slug}/"
    reader_url = f"/{book_slug}/?ch={ch_id}"
    og_image = f"{DOMAIN}/{book_slug}/og-image.png"

    excerpt_html = "\n".join(f"<p>{html.escape(p)}</p>" for p in paragraphs)

    part_html = f'\n  <p class="part">{html.escape(part)}</p>' if part else ''

    # Navigation
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

    nav_html = f'<div class="nav">{nav_links[0]}{nav_links[1]}</div>'

    json_ld = json.dumps({
        "@context": "https://schema.org",
        "@type": "Chapter",
        "name": display_title,
        "isPartOf": {
            "@type": "Book",
            "name": book_title,
            "author": {
                "@type": "Person",
                "name": author,
                "url": "https://www.linkedin.com/in/adrianmcphee/"
            },
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

  {nav_html}

  <footer>
    <p>&copy; {html.escape(author)} 2026 &middot;
    <a href="https://www.linkedin.com/in/adrianmcphee/">Contact</a></p>
  </footer>
</body>
</html>
"""


def generate_sitemap_entries(all_chapters):
    """Return list of (url, priority) tuples for sitemap."""
    entries = []
    for url in all_chapters:
        entries.append((url, "0.7"))
    return entries


def main():
    all_chapter_urls = []

    for book in BOOKS:
        slug = book["slug"]
        data_dir = os.path.join(SITE_DIR, slug, "data")
        chapters_dir = os.path.join(SITE_DIR, slug, "chapters")

        with open(os.path.join(data_dir, "meta.json")) as f:
            meta = json.load(f)

        chapters = meta["chapters"]

        # Skip "About the Author" - too short, just a bio
        chapters_to_generate = [c for c in chapters if c["title"] != "About the Author"]

        os.makedirs(chapters_dir, exist_ok=True)

        for i, ch in enumerate(chapters_to_generate):
            ch_file = os.path.join(data_dir, f"ch{ch['id']:02d}.json")
            if not os.path.exists(ch_file):
                print(f"  Skipping {ch['title']}: no data file")
                continue

            with open(ch_file) as f:
                words = json.load(f)

            paragraphs = words_to_paragraphs(words, max_paragraphs=3)
            if not paragraphs:
                print(f"  Skipping {ch['title']}: no paragraphs extracted")
                continue

            prev_ch = chapters_to_generate[i - 1] if i > 0 else None
            next_ch = chapters_to_generate[i + 1] if i < len(chapters_to_generate) - 1 else None

            ch_slug = slugify(ch["title"])
            ch_dir = os.path.join(chapters_dir, ch_slug)
            os.makedirs(ch_dir, exist_ok=True)

            html_content = generate_chapter_html(meta, ch, paragraphs, prev_ch, next_ch, slug)
            out_path = os.path.join(ch_dir, "index.html")
            with open(out_path, "w") as f:
                f.write(html_content)

            url = f"{DOMAIN}/{slug}/chapters/{ch_slug}/"
            all_chapter_urls.append(url)
            print(f"  Generated: {slug}/chapters/{ch_slug}/")

    # Write chapter URLs to a file for sitemap integration
    urls_file = os.path.join(SITE_DIR, ".chapter-urls.txt")
    with open(urls_file, "w") as f:
        for url in all_chapter_urls:
            f.write(url + "\n")

    print(f"\nGenerated {len(all_chapter_urls)} chapter pages.")
    print(f"Chapter URLs written to .chapter-urls.txt")


if __name__ == "__main__":
    main()
