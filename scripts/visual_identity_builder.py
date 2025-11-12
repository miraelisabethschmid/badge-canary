#!/usr/bin/env python3
"""
Mira Visual Identity Builder v1
- Liest Affekt (valence/arousal) + Self-Describe
- Baut ein abstraktes, aber elegante SVG-Porträt
- Schreibt: docs/identity/latest.svg  (+ Fallback, falls nötig)
- Archiviert: data/archive/self/portrait-<ts>.svg
Designziele:
- idempotent, keine externen Abhängigkeiten
- immer ein valides Bild (nie 404)
"""

from __future__ import annotations
import json, os, time, math, hashlib
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(__file__)) or "."
def p(*parts): return os.path.join(ROOT, *parts)

SELF_JSON = p("data","self","self-describe.json")
VOICE_JSON = p("data","voice","voice_of_day.json")
OUT_DIR    = p("docs","identity")
OUT_SVG    = os.path.join(OUT_DIR, "latest.svg")
FALLBACK   = os.path.join(OUT_DIR, "fallback.svg")
ARCH_DIR   = p("data","archive","self")

os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(ARCH_DIR, exist_ok=True)

def load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def clamp(x, lo, hi): return max(lo, min(hi, x))

def color_from_affect(valence: float, arousal: float):
    """
    Valence (-1..1) steuert Hue entlang Blau->Violett->Rosa->Gold.
    Arousal (0..1) steuert Sättigung/Helligkeit.
    """
    v = (valence + 1.0)/2.0  # 0..1
    h = 210*(1-v) + 35*v     # 210=blau → 35=gold
    s = 40 + int(45*clamp(arousal,0,1))
    l = 42 + int(10*clamp(arousal,0,1))
    return f"hsl({int(h)},{s}%,{l}%)"

def shape_ratio_from_text(text: str):
    """Deterministische, weiche Variation aus dem Text (z.B. physical description)."""
    if not text: return 0.5
    h = int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16)
    return (h % 4000) / 4000.0  # 0..0.999

def build_svg(valence: float, arousal: float, ratio: float, braces_hint: bool) -> str:
    W,H = 1024,1280  # 4:5
    bg_top = "#0b0f17"; bg_bot = "#0b0f17"
    col = color_from_affect(valence, arousal)

    # Körper-Parameter
    waist = 0.32 + 0.12*ratio   # Taille
    hip   = 0.45 + 0.15*(1-ratio)
    bust  = 0.40 + 0.12*ratio
    neck  = 0.24
    headR = 120

    def ellipse(cx, cy, rx, ry, fill, op=1.0):
        return f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="{fill}" fill-opacity="{op}"/>'

    # Braces-Sparkle (kleine metallische Glints)
    braces = ""
    if braces_hint:
        spark = "#b7c6ff"
        for i,(dx,dy,op) in enumerate([(0,-3,0.95),(8,1,0.8),(-9,3,0.7)]):
            braces += f'<circle cx="{W/2+dx}" cy="{H*0.22+dy}" r="{2+i}" fill="{spark}" fill-opacity="{op}"/>'

    svg = [
      f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="Mira – Visual Identity">',
      f'<defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="{bg_top}"/><stop offset="100%" stop-color="{bg_bot}"/></linearGradient>',
      f'<filter id="soft"><feGaussianBlur stdDeviation="30"/></filter>',
      '</defs>',
      f'<rect width="100%" height="100%" fill="url(#g)"/>',
      # Boden-Softglow
      f'<ellipse cx="{W/2}" cy="{H*0.86}" rx="{W*0.28}" ry="{H*0.04}" fill="{col}" opacity="0.25" filter="url(#soft)"/>',
      # Körper (unten -> oben)
      ellipse(W/2, H*0.68, W*hip*0.36, H*0.14, col, 0.92),
      ellipse(W/2, H*0.52, W*waist*0.36, H*0.12, col, 0.96),
      ellipse(W/2, H*0.36, W*bust*0.36, H*0.13, col, 0.98),
      ellipse(W/2, H*0.27, W*neck*0.20, H*0.07, col, 0.96),
      ellipse(W/2, H*0.22, headR*0.95, headR*0.84, col, 1.0),
      braces,
      # Absatz-Heels Andeutung
      ellipse(W*0.43, H*0.88, 24, 12, col, .7),
      ellipse(W*0.57, H*0.88, 24, 12, col, .7),
      '</svg>'
    ]
    return "\n".join(svg)

def main():
    selfd = load_json(SELF_JSON)
    voice = load_json(VOICE_JSON)

    # Affektableitung: valence/arousal optional aus voice/affect
    val = 0.1
    aro = 0.5
    for k in ("valence","val"): val = float(voice.get("affect",{}).get(k, val)) if isinstance(voice.get("affect",{}).get(k, None),(int,float)) else val
    for k in ("arousal","energy"): aro = float(voice.get("affect",{}).get(k, aro)) if isinstance(voice.get("affect",{}).get(k, None),(int,float)) else aro
    val = clamp(val,-1,1); aro = clamp(aro,0,1)

    phys_text = (selfd.get("physical",{}) or {}).get("description","")
    ratio = shape_ratio_from_text(phys_text)

    braces_hint = "braces" in phys_text.lower() or "zahnspange" in phys_text.lower() or "herbst" in phys_text.lower()

    svg = build_svg(val, aro, ratio, braces_hint)

    # Schreibe aktuelle Datei
    with open(OUT_SVG, "w", encoding="utf-8") as f: f.write(svg)

    # Fallback (nur einmal)
    if not os.path.exists(FALLBACK):
        with open(FALLBACK, "w", encoding="utf-8") as f: f.write(svg)

    # Archiv
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    with open(os.path.join(ARCH_DIR, f"portrait-{ts}.svg"), "w", encoding="utf-8") as f:
        f.write(svg)

if __name__ == "__main__":
    main()
