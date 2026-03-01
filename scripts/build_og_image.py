"""Build site-level OG image from site/src/og-image.tex.

Renders the TikZ composition of both book covers to a 2400x1260 PNG
(Retina/HiDPI; meta tags declare 1200x630).

Requires:
  - pdflatex  (TeX Live or similar)
  - pdftoppm  (poppler-utils)
  - Pillow    (pip install Pillow)
  - Both front-cover PNGs already built:
      book1/marketing/front-cover.png
      book2/marketing/front-cover.png

Usage: python3 site/scripts/build_og_image.py   (from repo root)
"""

import subprocess
import tempfile
from pathlib import Path

from PIL import Image

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
TEX_SRC = REPO_ROOT / "site" / "src" / "og-image.tex"
OG_OUT = REPO_ROOT / "site" / "og-image.png"

# Final dimensions: 2x for Retina (meta tags declare 1200x630)
OG_W, OG_H = 2400, 1260

RENDER_DPI = 400


def main():
    # Verify cover PNGs exist
    for book in ("book1", "book2"):
        cover = REPO_ROOT / book / "marketing" / "front-cover.png"
        if not cover.exists():
            raise FileNotFoundError(
                f"Missing {cover}\n"
                f"Run: cd {book} && make cover-assets"
            )

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)

        # 1. pdflatex → PDF (run from site/src/ so relative paths resolve)
        subprocess.run(
            ["pdflatex", "-interaction=nonstopmode",
             f"-output-directory={tmp}", str(TEX_SRC)],
            cwd=REPO_ROOT / "site" / "src",
            capture_output=True, check=True,
        )
        pdf = tmp / "og-image.pdf"
        print(f"PDF:         {pdf}")

        # 2. pdftoppm → high-res PNG
        stem = tmp / "og-render"
        subprocess.run(
            ["pdftoppm", "-png", "-r", str(RENDER_DPI), "-singlefile",
             str(pdf), str(stem)],
            capture_output=True, check=True,
        )
        raw = Image.open(f"{stem}.png")
        print(f"Raw render:  {raw.size[0]}x{raw.size[1]}")

        # 3. Resize to exact OG dimensions
        final = raw.resize((OG_W, OG_H), Image.LANCZOS)
        final.save(str(OG_OUT), "PNG", optimize=True)
        print(f"OG image:    {OG_OUT}  ({OG_W}x{OG_H})")


if __name__ == "__main__":
    main()
