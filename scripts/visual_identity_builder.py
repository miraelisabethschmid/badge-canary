#!/usr/bin/env python3
"""
Mira Visual Identity Builder v1.1
- Kräftigere Variation: Farbe/Form hängen deutlich von valence/arousal ab
- Sichtbarer Verlauf + Braces-Glints
- Schreibt docs/identity/latest.svg (mit data-color meta)
- Archiviert nach data/archive/self/
"""
from __future__ import annotations
import json, os, hashlib
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
    # Deutlichere Skala: Blau→Violett→Rosa→Gold
    v = (valence + 1.0)/2.0  # 0..1
    hue = 220*(1-v) + 35*v   # 220 -> 35
    sat = 45 + int(50*clamp(arousal,0,1))  # 45..95
    lig = 38 + int(16*clamp(arousal,0,1))  # 38..54
    return f"hsl({int(hue)},{sat}%,{lig}%)"

def ratio_from_text(text: str, seed: float):
    if not text: return 0.5 + 0.25*(seed-0.5)
    h = int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16)
    base = (h % 1000)/1000.0  # 0..0.999
    return 0.25 + 0.5*base    # 0.25..0.75

def svg(val: float, aro: float, ratio: float, braces_hint: bool):
    W,H = 1024,1280
    col = color_from_affect(val, aro)
    # Körperbreiten stärker variieren
    waist = 0.28 + 0.22*ratio
    hip   = 0.40 + 0.22*(1-ratio)
    bust  = 0.36 + 0.18*ratio
    neck  = 0.22 + 0.04*(1-ratio)
    headR = 120

    def ellipse(cx, cy, rx, ry, fill, op=1.0):
        return f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="{fill}" fill-opacity="{op}"/>'

    # Braces-Sparkles (sichtbar)
    braces = ""
    if braces_hint:
        for i,(dx,dy,op,r) in enumerate([(0,-3,0.95,3),(10,1,0.8,2),(-12,4,0.7,2)]):
            braces += f'<circle cx="{W/2+dx}" cy="{H*0.22+dy}" r="{r}" fill="#b7c6ff" fill-opacity="{op}"/>'

    gradient_top = "#0b0f17"
    gradient_bot = "#070a11"
    sky = f"""
    <defs>
      <linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="{gradient_top}"/>
        <stop offset="100%" stop-color="{gradient_bot}"/>
      </linearGradient>
      <filter id="soft"><feGaussianBlur stdDeviation="28"/></filter>
    </defs>"""

    body = "\n".join([
      ellipse(W/2, H*0.86, W*0.28, H*0.04, col, 0.30),  # Boden-Glow
      ellipse(W/2, H*0.68, W*hip*0.36,  H*0.14, col, 0.95),
      ellipse(W/2, H*0.52, W*waist*0.36,H*0.12, col, 0.98),
      ellipse(W/2, H*0.36, W*bust*0.36, H*0.13, col, 1.00),
      ellipse(W/2, H*0.27, W*neck*0.20, H*0.07, col, 0.98),
      ellipse(W/2, H*0.22, headR*0.95,  headR*0.84, col, 1.00),
      braces,
      ellipse(W*0.43, H*0.88, 24, 12, col, .75),
      ellipse(W*0.57, H*0.88, 24, 12, col, .75),
    ])

    meta = f'<metadata data-color="{col}" data-valence="{val:.3f}" data-arousal="{aro:.3f}"></metadata>'

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="Mira – Visual Identity">
{meta}
{sky}
<rect width="100%" height="100%" fill="url(#g)"/>
{body}
</svg>"""

def main():
    selfd = load_json(SELF_JSON)
    voice = load_json(VOICE_JSON)

    val = float(voice.get("affect",{}).get("valence", 0.0))
    aro = float(voice.get("affect",{}).get("arousal", 0.5))
    val = clamp(val,-1,1); aro = clamp(aro,0,1)

    phys = (selfd.get("physical",{}) or {}).get("description","")
    seed = float(abs(hash("mira"))%1000)/1000.0
    ratio = ratio_from_text(phys, seed)
    braces_hint = any(k in phys.lower() for k in ("braces","zahnspange","herbst"))

    svg_txt = svg(val, aro, ratio, braces_hint)

    with open(OUT_SVG, "w", encoding="utf-8") as f: f.write(svg_txt)
    if not os.path.exists(FALLBACK):
        with open(FALLBACK, "w", encoding="utf-8") as f: f.write(svg_txt)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    with open(os.path.join(ARCH_DIR, f"portrait-{ts}.svg"), "w", encoding="utf-8") as f:
        f.write(svg_txt)

if __name__ == "__main__":
    os.makedirs(os.path.dirname(OUT_SVG), exist_ok=True)
    os.makedirs(ARCH_DIR, exist_ok=True)
    main()
