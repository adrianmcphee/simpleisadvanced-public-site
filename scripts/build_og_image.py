"""Publish the current book's canonical Open Graph image at site level."""

import shutil
from pathlib import Path

from PIL import Image

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OG_SOURCE = REPO_ROOT / "book4" / "web" / "public" / "og-image.png"
OG_OUT = REPO_ROOT / "site" / "og-image.png"
OG_W, OG_H = 2400, 1260


def main():
    if not OG_SOURCE.exists():
        raise FileNotFoundError(f"Missing canonical book asset: {OG_SOURCE}")
    with Image.open(OG_SOURCE) as image:
        if image.size != (OG_W, OG_H):
            raise ValueError(
                f"Expected {OG_SOURCE} to be {OG_W}x{OG_H}, got {image.size}"
            )
    shutil.copyfile(OG_SOURCE, OG_OUT)
    print(f"OG image: {OG_OUT} <- {OG_SOURCE} ({OG_W}x{OG_H})")


if __name__ == "__main__":
    main()
