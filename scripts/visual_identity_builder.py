#!/usr/bin/env python3
import json, os, hashlib
from datetime import datetime, timezone

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
def P(*p): return os.path.join(ROOT, *p)

SELF  = P("data", "self", "self-describe.json")
VOICE = P("data", "voice", "voice_of_day.json")
OUTD  = P("docs", "identity")
OUT   = os.path.join(OUTD, "latest.svg")
ARCH  = P("data", "archive", "self")

os.makedirs(OUTD, exist_ok=True)
os.makedirs(ARCH, exist_ok=True)

def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def clamp(x, a, b): return max(a, min(b, x))

def color(val, aro):
    # 220° (kühler Blau) → 35° (warmes Gold)
    v = (val + 1) / 2  # -1..1 → 0..1
    hue = int(220 * (1 - v) + 35 * v)
    sat = 55 + int(40 * clamp(aro, 0, 1))
    lig = 40 + int(12 * clamp(aro, 0, 1))
    return f"hsl({hue},{sat}%,{lig}%)"

def hash_ratio(text):
    if not text: return 0.5
    h = int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16)
    return 0.3 + (h % 400) / 1000.0  # 0.3..0.7

def ell(cx, cy, rx, ry, c, op=1.0):
    return f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="{c}" fill-opacity="{op}"/>'

def build_svg(val, aro, desc):
    W, H = 1024, 1280
    col = color(val, aro)
    r = hash_ratio(desc)
    waist = 0.28 + 0.22 * r
    hip   = 0.40 + 0.22 * (1 - r)
    bust  = 0.36 + 0.18 * r
    neck  = 0.22 + 0.04 * (1 - r)
    headR = 120

    braces = any(k in (desc or "").lower() for k in ("zahnspange", "braces", "herbst"))

    spark = ""
    if braces:
        for dx, dy, op, rad in [(0, -3, 0.95, 3), (10, 1, 0.8, 2), (-12, 4, 0.7, 2)]:
            spark += f'<circle cx="{W/2+dx}" cy="{H*0.22+dy}" r="{rad}" fill="#cfe0ff" fill-opacity="{op}"/>'

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
  <defs><linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%" stop-color="#0b0f17"/><stop offset="100%" stop-color="#070a11"/></linearGradient></defs>
  <rect width="100%" height="100%" fill="url(#bg)"/>
  {ell(W/2, H*0.86, W*0.28, H*0.04, "#2a3550", 0.32)}
  {ell(W/2, H*0.68, W*hip*0.36,  H*0.14, col, 0.95)}
  {ell(W/2, H*0.52, W*waist*0.36,H*0.12, col, 0.98)}
  {ell(W/2, H*0.36, W*bust*0.36, H*0.13, col, 1.00)}
  {ell(W/2, H*0.27, W*neck*0.20, H*0.07, col, 0.98)}
  {ell(W/2, H*0.22, headR*0.95,  headR*0.84, col, 1.00)}
  {spark}
  {ell(W*0.43, H*0.88, 24, 12, col, .75)}
  {ell(W*0.57, H*0.88, 24, 12, col, .75)}
  <metadata data-source="visual_identity_builder.py"
            data-valence="{val:.3f}" data-arousal="{aro:.3f}"
            data-desc="{(desc or '').replace('"','&quot;')}"></metadata>
</svg>'''
    return svg

def main():
    selfd = load_json(SELF, {})
    voiced = load_json(VOICE, {})

    val = float(voiced.get("affect", {}).get("valence", 0.0))
    aro = float(voiced.get("affect", {}).get("arousal", 0.5))
    val = clamp(val, -1, 1)
    aro = clamp(aro, 0, 1)
    desc = (selfd.get("physical", {}) or {}).get("description", "")

    svg = build_svg(val, aro, desc)

    with open(OUT, "w", encoding="utf-8") as f:
        f.write(svg)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    with open(os.path.join(ARCH, f"portrait-{ts}.svg"), "w", encoding="utf-8") as f:
        f.write(svg)

if __name__ == "__main__":
    main()
