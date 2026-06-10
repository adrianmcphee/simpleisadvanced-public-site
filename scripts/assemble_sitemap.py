"""Assemble sitemap.xml from the per-section sitemap fragments.

Reads */sitemap-fragment.xml (articles plus one per book), takes loc and
priority from each entry, and computes lastmod from page content: a URL's
lastmod only advances when its file actually changes. The book-version
meta line is ignored when hashing, because every book publish rewrites it
in every chapter page; without that, all ~50 book URLs would claim
modification on every release and Google learns to distrust lastmod.

State lives in scripts/sitemap-state.json (committed). Pages not yet in
the state file are seeded from git history: the most recent commit whose
normalised content differs from its predecessor.

Called by each book's `make web-publish` after copying built pages, and
manually after regenerating the articles fragment. Run from the site
repo root:

    python3 scripts/assemble_sitemap.py
"""

import hashlib
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

SITE_DIR = Path(__file__).resolve().parent.parent
STATE_PATH = SITE_DIR / "scripts" / "sitemap-state.json"
OUT_PATH = SITE_DIR / "sitemap.xml"

DOMAIN = "https://simpleisadvanced.com"

# Rewritten on every book publish; not a content change.
VERSION_META = re.compile(rb'^\s*<meta name="book-version".*$\n?', re.MULTILINE)


def normalised_hash(data):
    return hashlib.sha256(VERSION_META.sub(b"", data)).hexdigest()


def url_to_path(loc):
    rel = loc[len(DOMAIN):].lstrip("/")
    if rel == "" or rel.endswith("/"):
        rel += "index.html"
    return rel


def parse_fragment(text):
    """Yield (loc, priority) per entry; any lastmod in the fragment is ignored."""
    for block in re.findall(r"<url>(.*?)</url>", text, re.DOTALL):
        loc = re.search(r"<loc>(.*?)</loc>", block)
        priority = re.search(r"<priority>(.*?)</priority>", block)
        if loc:
            yield loc.group(1).strip(), priority.group(1).strip() if priority else "0.7"


def git_show_hash(commit, path):
    out = subprocess.run(["git", "show", f"{commit}:{path}"],
                         cwd=SITE_DIR, capture_output=True)
    return normalised_hash(out.stdout) if out.returncode == 0 else None


def seed_lastmod(path, current_hash, today):
    """Date of the most recent real (normalised) content change, from git."""
    out = subprocess.run(["git", "log", "--format=%H %cs", "--", path],
                         cwd=SITE_DIR, capture_output=True, text=True)
    commits = [line.split() for line in out.stdout.splitlines() if line.strip()]
    if not commits:
        return today  # untracked: brand new page
    if git_show_hash(commits[0][0], path) != current_hash:
        return today  # uncommitted changes in the working tree
    for (sha, day), (older_sha, _) in zip(commits, commits[1:]):
        if git_show_hash(sha, path) != git_show_hash(older_sha, path):
            return day
    return commits[-1][1]  # never changed since creation


def assemble():
    fragments = sorted(SITE_DIR.glob("*/sitemap-fragment.xml"))
    if not fragments:
        sys.exit("No sitemap fragments found.")

    entries = [(f"{DOMAIN}/", "1.0")]
    for frag in fragments:
        entries.extend(parse_fragment(frag.read_text()))

    locs = [loc for loc, _ in entries]
    dupes = {loc for loc in locs if locs.count(loc) > 1}
    if dupes:
        sys.exit(f"Duplicate sitemap URLs: {', '.join(sorted(dupes))}")

    state = json.loads(STATE_PATH.read_text()) if STATE_PATH.exists() else {}
    today = date.today().isoformat()
    new_state, urls, changed, seeded = {}, [], 0, 0

    for loc, priority in entries:
        path = url_to_path(loc)
        file_path = SITE_DIR / path
        if not file_path.exists():
            sys.exit(f"Sitemap URL has no local file: {loc} -> {path}")
        current = normalised_hash(file_path.read_bytes())

        prev = state.get(path)
        if prev and prev["hash"] == current:
            lastmod = prev["lastmod"]
        elif prev:
            lastmod = today
            changed += 1
        else:
            lastmod = seed_lastmod(path, current, today)
            seeded += 1

        new_state[path] = {"hash": current, "lastmod": lastmod}
        urls.append(f"""  <url>
    <loc>{loc}</loc>
    <lastmod>{lastmod}</lastmod>
    <priority>{priority}</priority>
  </url>""")

    OUT_PATH.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(urls) + "\n</urlset>\n"
    )
    STATE_PATH.write_text(json.dumps(new_state, indent=2, sort_keys=True) + "\n")
    print(f"Sitemap: {len(urls)} URLs from {len(fragments)} fragments "
          f"({changed} changed, {seeded} seeded from git history)")


if __name__ == "__main__":
    assemble()
