#!/usr/bin/env python3
"""
Mira — Affect-Coupled Portrait State
------------------------------------
Sanfte, zustandsgeführte Weiterentwicklung des aktuellen Porträts.
- bevorzugt neueste Quelle aus data/archive/self/*
- sonst bestehendes data/self/latest_image.(png|jpg|jpeg|webp)
- sonst Notfall-Silhouette
Affect-Mapping:
  valence  [-1..1]  -> Wärme/Kühle (+/-)
  arousal  [-1..1]  -> Mikrokontrast/leichter Blur
  stability [0..1]  -> Vignette-Rahmung (unsteter -> stärker)
Idempotent: schreibt nur, wenn sich Ausgabebytes ändern.
"""

from __future__ import annotations
import io, os, glob, json, hashlib
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional
from PIL import Image, ImageOps, ImageEnhance, ImageFilter, ImageDraw

ROOT = Path(".")
OUT_PNG  = Path(os.getenv("OUT_PNG",  "data/self/latest_image.png"))
OUT_WEBP = Path(os.getenv("OUT_WEBP", "data/self/latest_image.webp"))
META_OUT = Path(os.getenv("META_OUT", "data/self/portrait_state.json"))

AFFECT_FILE = Path("data/self/affect-state.json")
SELF_FILE   = Path("data/self/self-describe.json")

def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def sha256_bytes(b: bytes) -> str:
    h = hashlib.sha256(); h.update(b); return h.hexdigest()

def clamp(x, lo, hi): 
    return max(lo, min(hi, x))

def load_json(p: Path) -> Optional[dict]:
    try:
        with p.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def pick_source() -> Optional[Path]:
    # Neuester Kandidat im Archiv
    candidates = []
    for ext in ("*.png", "*.jpg", "*.jpeg", "*.webp"):
        candidates += glob.glob(str(Path("data/archive/self")/ext))
    candidates = [Path(p) for p in candidates]
    candidates.sort(key=lambda x: x.stat().st_mtime if x.exists() else 0, reverse=True)
    for p in candidates:
        if p.exists() and p.stat().st_size > 10_000:
            return p
    # Fallback: bestehendes aktuelles Porträt
    for p in (OUT_WEBP, OUT_PNG):
        if p.exists() and p.stat().st_size > 10_000:
            return p
    return None

def map_adjustments(affect: dict | None) -> dict:
    a = affect or {}
    val = clamp(float(a.get("valence", 0.0)), -1.0, 1.0)
    aro = clamp(float(a.get("arousal", 0.0)), -1.0, 1.0)
    stab= clamp(float(a.get("stability", 0.75)), 0.0, 1.0)

    warmth = 0.03 * val                    # +/- 3% Farbtemperaturgefühl
    contrast = clamp(1.00 + 0.10*abs(aro), 0.95, 1.18)
    brightness= clamp(1.00 + 0.04*val,     0.96, 1.08)
    blur = 0.0 if abs(aro) < 0.65 else 0.35
    vign = clamp(0.10 + 0.20*(1.0-stab),   0.08, 0.28)

    return dict(
        warmth_shift=warmth,
        contrast_gain=contrast,
        brightness_gain=brightness,
        blur_sigma=blur,
        vignette_strength=vign
    )

def crop_to_3x4(img: Image.Image) -> Image.Image:
    w, h = img.size
    target = 3/4
    cur = w / h
    if cur > target:
        new_w = int(h * target)
        x0 = (w - new_w)//2
        img = img.crop((x0, 0, x0+new_w, h))
    elif cur < target:
        new_h = int(w / target)
        y0 = (h - new_h)//2
        img = img.crop((0, y0, w, y0+new_h))
    return img

def apply_adjustments(img: Image.Image, adj: dict) -> Image.Image:
    img = ImageOps.exif_transpose(img).convert("RGB")
    img = crop_to_3x4(img)
    img = img.resize((1024, 1365), Image.LANCZOS)

    # sanfter Warm/Kalt-Eindruck über Color-Saturation + kleine Kanalverschiebung
    warmth = adj["warmth_shift"]  # [-0.03..0.03]
    color_gain = clamp(1.0 + warmth*0.5, 0.95, 1.05)
    img = ImageEnhance.Color(img).enhance(color_gain)

    # Brightness & Contrast
    img = ImageEnhance.Brightness(img).enhance(adj["brightness_gain"])
    img = ImageEnhance.Contrast(img).enhance(adj["contrast_gain"])

    # Minimaler Blur bei hoher Arousal
    if adj["blur_sigma"] > 0:
        img = img.filter(ImageFilter.GaussianBlur(radius=adj["blur_sigma"]))

    # Vignette (dunkler Rand → Fokus)
    v = adj["vignette_strength"]
    if v > 0:
        w, h = img.size
        mask = Image.new("L", (w, h), 0)
        e = Image.new("L", (w, h), 0)
        d = ImageDraw.Draw(e)
        d.ellipse((int(w*0.08), int(h*0.06), int(w*0.92), int(h*0.94)), fill=255)
        e = e.filter(ImageFilter.GaussianBlur(radius=int(min(w, h)*0.12)))
        vign = ImageOps.invert(e)
        alpha = int(255 * v)
        vign = vign.point(lambda p: int(p * (alpha/255)))
        dark = Image.new("RGB", (w, h), (0, 0, 0))
        img = Image.composite(dark, img, vign)
    return img

def save_if_changed(img: Image.Image):
    # PNG
    OUT_PNG.parent.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO(); img.save(buf, format="PNG", optimize=True)
    new_png = buf.getvalue()
    old_png = OUT_PNG.read_bytes() if OUT_PNG.exists() else b""
    if sha256_bytes(new_png) != sha256_bytes(old_png):
        with OUT_PNG.open("wb") as f: f.write(new_png)

    # WEBP
    buf = io.BytesIO(); img.save(buf, format="WEBP", quality=88, method=6)
    new_webp = buf.getvalue()
    old_webp = OUT_WEBP.read_bytes() if OUT_WEBP.exists() else b""
    if sha256_bytes(new_webp) != sha256_bytes(old_webp):
        with OUT_WEBP.open("wb") as f: f.write(new_webp)

def write_meta(meta: dict):
    META_OUT.parent.mkdir(parents=True, exist_ok=True)
    with META_OUT.open("w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

def emergency_silhouette() -> Image.Image:
    img = Image.new("RGB", (1024, 1365), (11,14,20))
    d = ImageDraw.Draw(img)
    d.ellipse((422,140,602,320), fill=(123,164,255))
    d.ellipse((312,380,712,940),  fill=(111,152,255))
    d.rounded_rectangle((462,990,562,1160), 40, fill=(97,139,255))
    d.ellipse((382,1210,502,1250), fill=(93,134,255))
    d.ellipse((622,1210,742,1250), fill=(93,134,255))
    return img

def main():
    src = pick_source()
    affect = load_json(AFFECT_FILE) or {}
    selfj  = load_json(SELF_FILE)   or {}

    if src is None:
        img = emergency_silhouette()
        save_if_changed(img)
        write_meta({
            "ts": now_iso(),
            "source": None,
            "note": "emergency silhouette",
            "affect": affect
        })
        return

    base = Image.open(src).convert("RGB")
    adj  = map_adjustments(affect)
    out  = apply_adjustments(base, adj)
    save_if_changed(out)

    meta = {
        "ts": now_iso(),
        "source": str(src),
        "affect": affect,
        "adjustments": adj,
        "self_hint": {
            "has_description": bool(selfj)
        }
    }
    write_meta(meta)

if __name__ == "__main__":
    main()
