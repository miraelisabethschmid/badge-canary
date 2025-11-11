#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Update Hero Image from latest archive render.

- Picks newest PNG from data/archive/
- Converts to docs/portrait/mira-hero.jpg (max 780x1080), JPEG quality 90
- Writes a small provenance note (mira-hero.txt)
- Idempotent: only updates output if pixels actually change
"""

import os, sys, hashlib, time
from pathlib import Path

try:
    from PIL import Image, ImageOps
except Exception as e:
    print("[hero] Pillow not available. Install with: pip install pillow", file=sys.stderr)
    sys.exit(1)

ARCHIVE = Path("data/archive")
OUT_DIR = Path("docs/portrait")
OUT_JPG = OUT_DIR / "mira-hero.jpg"
OUT_TXT = OUT_DIR / "mira-hero.txt"
MAX_W, MAX_H = 780, 1080

def newest_png():
    if not ARCHIVE.exists():
        return None
    cand = sorted(ARCHIVE.glob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True)
    return cand[0] if cand else None

def sha256_bytes(b: bytes) -> str:
    import hashlib
    h = hashlib.sha256()
    h.update(b)
    return h.hexdigest()

def encode_jpeg(img: Image.Image) -> bytes:
    from io import BytesIO
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=90, optimize=True, progressive=True)
    return buf.getvalue()

def prepare(img: Image.Image) -> Image.Image:
    # Convert to RGB, letterbox-fit into MAX_W x MAX_H, then center-crop if necessary
    img = img.convert("RGB")
    # First, scale so that the image fits into the bounding box while preserving aspect
    img.thumbnail((MAX_W, MAX_H), Image.LANCZOS)
    # If result is smaller on one side, place on black canvas to keep exact size
    canvas = Image.new("RGB", (MAX_W, MAX_H), (0,0,0))
    ox = (MAX_W - img.size[0]) // 2
    oy = (MAX_H - img.size[1]) // 2
    canvas.paste(img, (ox, oy))
    return canvas

def main():
    src = newest_png()
    if not src:
        print("[hero] No PNGs in data/archive — nothing to update.")
        return 0

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Load and prepare
    try:
        im = Image.open(src)
    except Exception as e:
        print(f"[hero] Failed to open {src}: {e}", file=sys.stderr)
        return 0

    out_img = prepare(im)
    new_bytes = encode_jpeg(out_img)
    new_hash = sha256_bytes(new_bytes)

    old_hash = None
    if OUT_JPG.exists():
        try:
            old_bytes = OUT_JPG.read_bytes()
            old_hash = sha256_bytes(old_bytes)
        except Exception:
            old_hash = None

    if new_hash == old_hash:
        print(f"[hero] Up-to-date (source: {src.name})")
        return 0

    # Write new hero and provenance
    OUT_JPG.write_bytes(new_bytes)
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    OUT_TXT.write_text(
        f"hero_source: {src.name}\nupdated_utc: {ts}\nsha256: {new_hash}\n",
        encoding="utf-8"
    )
    print(f"[hero] Updated hero from {src.name}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
