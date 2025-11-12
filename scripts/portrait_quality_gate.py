#!/usr/bin/env python3
"""
Mira — Portrait Quality Gate (non-fatal)
---------------------------------------
Bewertet das aktuelle Porträt anhand einfacher, robuster Kennzahlen:

- min_resolution_ok:     Auflösung >= 768×1024
- brightness_ok:         mittlere Helligkeit in [0.18, 0.82]
- contrast_ok:           Std-Abweichung (Luma) in [0.06, 0.32]
- sharpness_ok:          Kanten-Energie (Sobel-ähnlich) >= Schwelle
- aspect_ok:             3:4 (± 2 % Toleranz)

Ergebnis wird nach data/self/quality.json geschrieben:
{
  "ts": "...Z",
  "image": "data/self/latest_image.(png|webp|...)" | null,
  "metrics": { ... },
  "ok": true|false,
  "notes": ["...","..."]
}

Exit-Code ist immer 0 (non-fatal), damit Autopoiesis nicht stoppt.
"""

from __future__ import annotations
import json, os, sys, io, math, glob, hashlib
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional
from PIL import Image, ImageOps, ImageFilter, ImageStat

ROOT = Path(".")
OUT_JSON = Path("data/self/quality.json")

def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def pick_current_image() -> Optional[Path]:
    # bevorzugt WEBP/PNG im aktuellen Self
    for cand in ("data/self/latest_image.webp", "data/self/latest_image.png",
                 "data/self/latest_image.jpg", "data/self/latest_image.jpeg"):
        p = Path(cand)
        if p.exists() and p.stat().st_size > 10_000:
            return p
    # sonst jüngster Archiv-Eintrag
    candidates = []
    for ext in ("*.webp","*.png","*.jpg","*.jpeg"):
        candidates += glob.glob(str(Path("data/archive/self")/ext))
    candidates = [Path(p) for p in candidates]
    candidates.sort(key=lambda x: x.stat().st_mtime if x.exists() else 0, reverse=True)
    for p in candidates:
        if p.exists() and p.stat().st_size > 10_000:
            return p
    return None

def luma_image(img: Image.Image) -> Image.Image:
    # sRGB-Annäherung an Luma
    return img.convert("L")

def estimate_sharpness(luma: Image.Image) -> float:
    # Kantenenergie-Proxy: Laplace-Varianz (vereinfachte Schärfeschätzung)
    # PIL hat keinen direkten Laplace → Highpass via EDGE_ENHANCE -> differenz
    # Wir nehmen Varianz nach einem EDGE_ENHANCE_MORE Verlauf als Proxy.
    hp = luma.filter(ImageFilter.FIND_EDGES)  # robust, schnell
    stat = ImageStat.Stat(hp)
    # mittlere absolute Abweichung ~ "Kanten-Energie"
    mean = stat.mean[0] / 255.0
    std  = stat.stddev[0] / 255.0
    # Kombinierter Proxy
    return float(0.6*std + 0.4*mean)

def contrast_spread(luma: Image.Image) -> float:
    stat = ImageStat.Stat(luma)
    # Std-Abweichung normalisieren auf [0,1]
    return float((stat.stddev[0] or 0.0) / 255.0)

def mean_brightness(luma: Image.Image) -> float:
    stat = ImageStat.Stat(luma)
    return float((stat.mean[0] or 0.0) / 255.0)

def aspect_ok(w: int, h: int, target=3/4, tol=0.02) -> bool:
    r = w / h
    return abs(r - target) <= target * tol

def main():
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)

    img_path = pick_current_image()
    if not img_path:
        data = {
            "ts": now_iso(),
            "image": None,
            "metrics": {},
            "ok": False,
            "notes": ["no_image_found"]
        }
        OUT_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print("no image found; wrote quality.json with ok=false")
        return 0

    try:
        img = Image.open(img_path)
        img = ImageOps.exif_transpose(img).convert("RGB")
    except Exception as e:
        data = {
            "ts": now_iso(),
            "image": str(img_path),
            "metrics": {},
            "ok": False,
            "notes": [f"open_error:{type(e).__name__}"]
        }
        OUT_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print("failed to open image; wrote quality.json with ok=false")
        return 0

    w, h = img.size
    lum = luma_image(img)

    # Kennzahlen
    m_brightness = mean_brightness(lum)         # [0..1], gut: ~0.18..0.82
    c_spread     = contrast_spread(lum)         # [0..1], gut: ~0.06..0.32
    sharp        = estimate_sharpness(lum)      # heuristisch, typ. 0.03..0.25+
    res_ok       = (w >= 768 and h >= 1024)
    asp_ok       = aspect_ok(w, h, 3/4, tol=0.02)

    # Schwellen
    bright_ok = (0.18 <= m_brightness <= 0.82)
    contrast_ok = (0.06 <= c_spread <= 0.32)
    sharp_ok = (sharp >= 0.06)   # sehr weiche Bilder < 0.06

    ok = bool(res_ok and asp_ok and bright_ok and contrast_ok and sharp_ok)

    notes = []
    if not res_ok:     notes.append("low_resolution")
    if not asp_ok:     notes.append("aspect_off")
    if not bright_ok:  notes.append("brightness_out_of_range")
    if not contrast_ok:notes.append("contrast_out_of_range")
    if not sharp_ok:   notes.append("low_sharpness")

    out = {
        "ts": now_iso(),
        "image": str(img_path),
        "metrics": {
            "width": w, "height": h,
            "mean_brightness": round(m_brightness, 4),
            "contrast_spread": round(c_spread, 4),
            "sharpness": round(sharp, 4)
        },
        "thresholds": {
            "min_resolution": [768, 1024],
            "brightness_range": [0.18, 0.82],
            "contrast_range": [0.06, 0.32],
            "sharpness_min": 0.06,
            "aspect": "3:4 ±2%"
        },
        "ok": ok,
        "notes": notes
    }

    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"quality ok={ok}; wrote data/self/quality.json")
    return 0

if __name__ == "__main__":
    sys.exit(main())
