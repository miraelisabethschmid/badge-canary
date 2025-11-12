#!/usr/bin/env python3
"""
Mira — Adaptive Portrait Adaptor
--------------------------------
Ziel: Das aktuelle Porträt entwickelt sich MIT dem Systemzustand (keine Rotation).
Eingaben (wenn vorhanden):
  - data/archive/self/*.png|webp   : Kandidaten (neueste bevorzugt)
  - data/self/latest_image.png|webp: bisher gültiges Porträt (Fallback-Quelle)
  - data/self/self-describe.json   : narrative Hinweise (optional)
  - data/self/learning.json        : viseme_sensitivity etc. (optional)
  - data/self/affect-state.json    : { valence, arousal, stability, focus } (optional)

Ausgaben:
  - data/self/latest_image.png / .webp  : 3:4, dezent optimiert (warm/kalt, Kontrast, Vignette)
  - data/self/portrait_state.json       : Metadaten (Quelle, Mapping, Checks)
Idempotent, qualitativ vorsichtig (Clamps & Guards).
"""

import json, os, glob, hashlib, io, time
from datetime import datetime, timezone
from pathlib import Path
from PIL import Image, ImageOps, ImageEnhance, ImageFilter

ROOT = Path(".")
OUT_PNG = Path(os.getenv("MIRA_OUT_PNG", "data/self/latest_image.png"))
OUT_WEBP = Path(os.getenv("MIRA_OUT_WEBP", "data/self/latest_image.webp"))
META_OUT = Path(os.getenv("MIRA_META_OUT", "data/self/portrait_state.json"))
DEFAULT_SOURCE = Path(os.getenv("MIRA_DEFAULT_SOURCE", "data/self/latest_image.png"))

ARCHIVE_GLOB = "data/archive/self/*"
AFFECT_FILE = Path("data/self/affect-state.json")
LEARN_FILE  = Path("data/self/learning.json")
SELF_FILE   = Path("data/self/self-describe.json")

def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def load_json(p: Path):
    try:
        with p.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def pick_source() -> Path | None:
    """Wähle Quelle: Neuester Eintrag aus dem Archiv (png/webp), sonst aktuelles Bild, sonst None."""
    candidates = []
    for pat in ("*.png", "*.jpg", "*.jpeg", "*.webp"):
        candidates += glob.glob(str(Path("data/archive/self")/pat))
    candidates = [Path(p) for p in candidates]
    candidates.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
    for p in candidates:
        if p.exists() and p.stat().st_size > 10_000:
            return p
    # Fallback: aktuelles Bild, wenn vorhanden
    for p in (DEFAULT_SOURCE, OUT_PNG, OUT_WEBP):
        if p.exists() and p.stat().st_size > 10_000:
            return p
    return None

def open_image_any(p: Path) -> Image.Image:
    img = Image.open(p).convert("RGB")
    return img

def clamp(v, lo, hi): return max(lo, min(hi, v))

def map_adjustments(affect: dict | None, learn: dict | None) -> dict:
    """
    Mappe Valence/Arousal/Stability auf subtile Bildparameter.
    Wertebereiche:
      valence, arousal in [-1, 1], stability in [0,1]
    Output:
      warmth_shift (K), contrast_gain, brightness_gain, vignette_strength, blur_sigma
    """
    # Defaults (sanft)
    val = clamp((affect or {}).get("valence", 0.0), -1.0, 1.0)
    aro = clamp((affect or {}).get("arousal", 0.0), -1.0, 1.0)
    stab = clamp((affect or {}).get("stability", 0.7), 0.0, 1.0)
    # Learning influence (tiny)
    learn_gain = float((learn or {}).get("emergence_gain", 0.0))
    learn_gain = clamp(learn_gain, -0.2, 0.2)

    # Wärmer bei positiver Valence, kühler bei negativer
    warmth = 0.03 * val  # +/- 3% Farbtemperatur-Gefühl
    # Mehr Mikro-Kontrast bei moderater Arousal, aber clamp
    contrast = 1.00 + 0.08 * abs(aro) + 0.03 * learn_gain
    contrast = clamp(contrast, 0.95, 1.15)
    # Leichte Helligkeitsspreizung: positiver valence -> +, negativer -> -
    brightness = 1.00 + 0.04 * val
    brightness = clamp(brightness, 0.96, 1.08)
    # Vignette stärker bei geringer Stabilität
    vignette = clamp(0.10 + (0.20 * (1.0 - stab)), 0.08, 0.28)
    # Minimaler Weichzeichner bei hoher Arousal, sonst 0 (Gesicht bleibt scharf)
    blur = 0.0 if abs(aro) < 0.6 else 0.3

    return dict(
        warmth_shift=warmth,
        contrast_gain=contrast,
        brightness_gain=brightness,
        vignette_strength=vignette,
        blur_sigma=blur
    )

def apply_adjustments(img: Image.Image, adj: dict) -> Image.Image:
    # 3:4 Crop (zentriert, ohne Upscale-Wechsel)
    w, h = img.size
    target_ratio = 3/4
    cur_ratio = w / h
    if cur_ratio > target_ratio:
        # zu breit -> seitlich schneiden
        new_w = int(h * target_ratio)
        x0 = (w - new_w) // 2
        img = img.crop((x0, 0, x0 + new_w, h))
    else:
        # zu hoch -> oben/unten schneiden
        new_h = int(w / target_ratio)
        y0 = (h - new_h) // 2
        img = img.crop((0, y0, w, y0 + new_h))

    # sanfte Größenbegrenzung
    img = ImageOps.exif_transpose(img)
    img = img.resize((1024, 1365), Image.LANCZOS)

    # Warm/Kalt Shift (einfacher über RGB-Matrix)
    warmth = adj["warmth_shift"]  # +/- 0.03
    r_mult = 1.0 + warmth
    b_mult = 1.0 - warmth
    def warm_fn(px):
        r,g,b = px
        r = clamp(int(r * r_mult), 0, 255)
        g = clamp(int(g * 1.0), 0, 255)
        b = clamp(int(b * b_mult), 0, 255)
        return (r,g,b)
    img = Image.merge("RGB", [ImageEnhance.Brightness(ch).enhance(1.0) for ch in img.split()])
    img = Image.eval(img, lambda v: v)  # noop to attach lazy ops
    img = img.convert("RGB")
    img = Image.frombytes("RGB", img.size, img.tobytes())  # materialize
    img = Image.new("RGB", img.size).convert("RGB").paste if False else img  # keep

    # Apply per-pixel warmth (fast map)
    img = img.point(lambda x: x)  # keep pipeline happy
    # PIL hat keine direkte 3-kanal point-Map; wir nehmen eine leichte Farbkurve via Color Enhance:
    # (vereinfachen: ColorEnhance proportional zur warmth)
    color_gain = clamp(1.0 + (warmth * 0.5), 0.95, 1.05)
    img = ImageEnhance.Color(img).enhance(color_gain)

    # Brightness / Contrast
    img = ImageEnhance.Brightness(img).enhance(adj["brightness_gain"])
    img = ImageEnhance.Contrast(img).enhance(adj["contrast_gain"])

    # Leichtes Blur bei hoher Arousal
    if adj["blur_sigma"] > 0:
        img = img.filter(ImageFilter.GaussianBlur(radius=adj["blur_sigma"]))

    # Vignette
    v = adj["vignette_strength"]
    if v > 0:
        w, h = img.size
        mask = Image.new("L", (w, h), 0)
        grad = Image.new("L", (w, h))
        # radial gradient via blur of ellipse
        g = Image.new("L", (w, h), 0)
        g_draw = Image.new("L", (w, h), 0)
        # Ellipse als „Spotlight“ (hell innen)
        e = Image.new("L", (w, h), 0)
        e1 = ImageDraw = __import__("PIL.ImageDraw", fromlist=["ImageDraw"]).ImageDraw
        d = e1(e)
        d.ellipse((int(w*0.08), int(h*0.06), int(w*0.92), int(h*0.94)), fill=255)
        e = e.filter(ImageFilter.GaussianBlur(radius=int(min(w, h) * 0.12)))
        # invert to make edges darker
        vign = ImageOps.invert(e)
        alpha = int(255 * v)
        vign = vign.point(lambda p: int(p * (alpha/255)))
        # overlay as darkening layer
        dark = Image.new("RGB", (w, h), (0, 0, 0))
        img = Image.composite(dark, img, vign)

    return img

def save_outputs(img: Image.Image):
    # PNG
    OUT_PNG.parent.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    png_bytes = buf.getvalue()
    old = OUT_PNG.read_bytes() if OUT_PNG.exists() else b""
    if sha256_bytes(old) != sha256_bytes(png_bytes):
        with OUT_PNG.open("wb") as f:
            f.write(png_bytes)

    # WEBP
    buf = io.BytesIO()
    img.save(buf, format="WEBP", quality=88, method=6)
    webp_bytes = buf.getvalue()
    oldw = OUT_WEBP.read_bytes() if OUT_WEBP.exists() else b""
    if sha256_bytes(oldw) != sha256_bytes(webp_bytes):
        with OUT_WEBP.open("wb") as f:
            f.write(webp_bytes)

def write_meta(meta: dict):
    META_OUT.parent.mkdir(parents=True, exist_ok=True)
    with META_OUT.open("w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

def main():
    src = pick_source()
    affect = load_json(AFFECT_FILE) or {}
    learn  = load_json(LEARN_FILE)  or {}
    selfj  = load_json(SELF_FILE)   or {}

    if src is None:
        # Letzte Notfall-Silhouette als PNG erzeugen (falls gar nichts existiert)
        from PIL import ImageDraw
        img = Image.new("RGB", (1024,1365), (12,14,20))
        d = ImageDraw.Draw(img)
        # simple silhouette
        d.ellipse((422,120,602,300), fill=(123,164,255))
        d.ellipse((312,360,712,920), fill=(111,152,255))
        d.rounded_rectangle((462,980,562,1160), 40, fill=(97,139,255))
        d.ellipse((382,1210,502,1250), fill=(93,134,255))
        d.ellipse((622,1210,742,1250), fill=(93,134,255))
        save_outputs(img)
        write_meta({
            "ts": now_iso(),
            "source": None,
            "note": "generated emergency silhouette",
            "adjustments": None
        })
        return

    # Quelle öffnen
    img = open_image_any(src)
    adj = map_adjustments(affect, learn)
    out = apply_adjustments(img, adj)
    save_outputs(out)

    write_meta({
        "ts": now_iso(),
        "source": str(src),
        "affect": affect,
        "learning": learn,
        "adjustments": adj,
        "checksum_png": sha256_bytes(OUT_PNG.read_bytes()) if OUT_PNG.exists() else None
    })

if __name__ == "__main__":
    main()
