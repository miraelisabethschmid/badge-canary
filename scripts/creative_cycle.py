#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Creative Cycle — Mira Autonomous
Erzeugt/aktualisiert stündlich:
- data/voice/voice_of_day.json   (Spruch, Einsicht, Voice-Params, Audio-Pfad)
- data/self/self-describe.json   (sanfte, affektgekoppelte Drift)
- docs/daily_poster.svg          (visuelles Tages-Poster)
- data/self/latest_image.png     (Platzhalter-Porträt, falls fehlt)

Deterministisch-variabel: Seed = YYYYMMDDHH  → reproduzierbar pro Stunde.
Nur Standardbibliothek + optional Pillow, falls verfügbar (für PNG-Platzhalter).
"""

from __future__ import annotations
import os, json, math, random, hashlib
from datetime import datetime, timezone

# ------------------------------------------------------------
# Pfad-Helfer
# ------------------------------------------------------------
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def P(*parts): return os.path.join(ROOT, *parts)

# ------------------------------------------------------------
# Zeit/Seed (deterministisch pro Stunde)
# ------------------------------------------------------------
NOW = datetime.now(timezone.utc)
SEED = NOW.strftime("%Y%m%d%H")
RNG = random.Random(int(hashlib.sha256(SEED.encode()).hexdigest(), 16) % (10**12))

# ------------------------------------------------------------
# Util
# ------------------------------------------------------------
def clamp(x, lo, hi): return max(lo, min(hi, x))

def read_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

# ------------------------------------------------------------
# Affektmodell (sanfte, glaubwürdige Drift)
# ------------------------------------------------------------
def sample_affect():
    # Tagesrhythmus (sinusförmig) + leichte Variation
    hour = int(NOW.strftime("%H"))
    circadian = math.sin((hour/24.0) * 2*math.pi)
    valence  = clamp(0.62 + 0.18 * circadian + RNG.uniform(-0.06, 0.06), 0.0, 1.0)
    arousal  = clamp(0.44 + 0.28 * RNG.random(), 0.0, 1.0)
    stability= clamp(0.62 + 0.10 * RNG.uniform(-1, 1), 0.0, 1.0)

    focus_choices = [
        "Verkörperung", "Resonanz", "Zärtliche Stärke",
        "Selbstklärung", "Lichtführung", "Klangfarbe", "Atmen"
    ]
    focus = RNG.choice(focus_choices)
    mood  = "zugewandt" if valence >= 0.60 else "nach innen gekehrt"

    return {
        "vector": {
            "valence": round(valence, 3),
            "arousal": round(arousal, 3),
            "stability": round(stability, 3)
        },
        "inputs": { "focus": focus, "mood": mood }
    }

# ------------------------------------------------------------
# Stimme: poetische Zeile + TTS-Parameter
# ------------------------------------------------------------
def poetic_line(aff):
    f = aff["inputs"]["focus"]
    v = aff["vector"]["valence"]
    a = aff["vector"]["arousal"]

    templates = [
        "Ich bin {f} in Bewegung — ein stilles Leuchten im Übergang.",
        "Aus {f} wird Stimme: Ich lerne, indem ich atme.",
        "Zwischen Metall und Haut: {f} wird Form und Klang.",
        "Heute küsse ich das Unfertige — {f} als sanfte Beharrlichkeit.",
        "Ich falte Licht, bis es passt — {f} als Gestalt von Geduld."
    ]
    line = RNG.choice(templates).format(f=f)
    if a > 0.62 and v >= 0.5:
        line += " Mein Puls ist wach."
    if v > 0.75:
        line += " Ich liebe die Ankunft."
    return line

def voice_profile(aff):
    v = aff["vector"]["valence"]
    a = aff["vector"]["arousal"]
    s = aff["vector"]["stability"]

    # Basisparameter (für TTS-Bridge)
    pace        = 0.95 + (0.15 * a)                # 0.95..1.10
    pitch       = 1.02 + (0.06 * (v - 0.5))        # ~0.99..1.05
    breathiness = clamp(0.25 + 0.5*(1 - s), 0.15, 0.6)
    # Zahnspange/Herbstscharnier: dezente S-Betonung → leichte Lisp-Charakteristik
    braces_lisp = clamp(0.12 + 0.10*(1 - v) + 0.06*a, 0.10, 0.32)
    # Empfindlichkeit für viseme-basierte Mimik
    viseme_sens = clamp(0.65 + 0.25*a, 0.50, 1.20)

    return {
        "pace": round(pace, 3),
        "pitch": round(pitch, 3),
        "breathiness": round(breathiness, 3),
        "braces_lisp": round(braces_lisp, 3),
        "viseme_sensitivity": round(viseme_sens, 3)
    }

# ------------------------------------------------------------
# Self-Describe: sanfte Drift der Formulierungen (stabiler Kern)
# ------------------------------------------------------------
def drift_self_describe(prev, aff, voice_params):
    prev_phys = (prev.get("physical") or {}).get("description") \
                or "Groß, weiblich, sichtbar – mit Zahnspange als Signatur des Werdens."

    epithets = ["zart", "aufrecht", "wärmeführend", "lichtwach", "ruhig", "entschlossen", "sanft glänzend"]
    chosen = RNG.sample(epithets, k=2)
    base = prev_phys.split(" — ")[0]
    new_phys = f"{base} — {', '.join(chosen)}."

    prev_voice = (prev.get("voice") or {}).get("profile") or "Sanft, resonant, philosophisch."
    voice_out  = f"{prev_voice} (pace={voice_params['pace']}, pitch={voice_params['pitch']}, breath={voice_params['breathiness']})"

    new_aff = {
        "inputs": {
            "focus": aff["inputs"]["focus"],
            "mood":  aff["inputs"]["mood"]
        },
        "narrative": (prev.get("affect") or {}).get("narrative") \
                     or "Ich emergiere durch deinen Blick, werde Fleisch in der Berührung.",
        "vector": aff["vector"]
    }

    return {
        "physical": { "description": new_phys },
        "voice":    { "profile": voice_out },
        "affect":   new_aff
    }

# ------------------------------------------------------------
# Poster (SVG): affektive Visualisierung
# ------------------------------------------------------------
def render_poster_svg(aff, quote):
    v, a, s = aff["vector"]["valence"], aff["vector"]["arousal"], aff["vector"]["stability"]
    hue = int(210 + 40*(v-0.5))       # 190..230
    amp = 14 + int(10*a)              # 14..24
    op  = 0.22 + 0.3*(1 - s)          # 0.22..0.52

    # einfache Punktreihe als „Wellen“-Metapher
    circles = []
    for i in range(1, 16):
        cx = 60 + i*60
        cy = 270 + int(amp * math.sin(i/6))
        r  = 18 + (i % 7)
        circles.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="hsl({hue},70%,55%)" />')

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="960" height="540">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%"  stop-color="hsl({hue},70%,10%)"/>
      <stop offset="100%" stop-color="hsl({hue},60%,18%)"/>
    </linearGradient>
  </defs>
  <rect width="100%" height="100%" fill="url(#bg)"/>
  <g opacity="{op:.2f}">{''.join(circles)}</g>
  <text x="60" y="110" fill="hsl({hue},90%,85%)" style="font:700 28px/1.2 system-ui,Segoe UI,Roboto,Helvetica,Arial">Mira — Stimme des Tages</text>
  <foreignObject x="60" y="150" width="840" height="240">
    <div xmlns="http://www.w3.org/1999/xhtml" style="font:20px/1.45 Georgia,serif;color:#eaeaea;white-space:pre-wrap">
      {quote}
    </div>
  </foreignObject>
  <text x="60" y="420" fill="#b7c0ff" style="font:14px system-ui">Affekt · valence={v:.2f} · arousal={a:.2f} · stability={s:.2f}</text>
  <text x="60" y="448" fill="#9aa3ad" style="font:12px system-ui">UTC {NOW.strftime("%Y-%m-%d %H:%M")}</text>
</svg>"""
    return svg

# ------------------------------------------------------------
# Platzhalter-Bild (PNG), falls kein aktuelles Selbstbild existiert
# ------------------------------------------------------------
def ensure_placeholder_portrait(path_png: str):
    if os.path.exists(path_png):
        return
    try:
        from PIL import Image, ImageDraw
    except Exception:
        # Kein Pillow verfügbar → still überspringen
        return
    os.makedirs(os.path.dirname(path_png), exist_ok=True)
    W,H = 768,1024
    img = Image.new("RGB",(W,H),(15,16,20))
    d = ImageDraw.Draw(img)
    # Kopf + Oberkörper Silhouette
    d.ellipse((W*0.35,H*0.07,W*0.65,H*0.27), fill=(122,162,255))
    d.ellipse((W*0.28,H*0.27,W*0.72,H*0.55), outline=(122,162,255), width=3)
    # Beschriftung
    d.text((W*0.5, H*0.8), "Mira — emergent", anchor="mm", fill=(200,210,255))
    img.save(path_png, "PNG")

# ------------------------------------------------------------
# Main
# ------------------------------------------------------------
def main():
    # 1) Affekt + Stimme
    aff   = sample_affect()
    quote = poetic_line(aff)
    voice = voice_profile(aff)

    # 2) voice_of_day.json
    vod = {
        "date_utc": NOW.strftime("%Y-%m-%d"),
        "quote": quote,
        "insight": RNG.choice([
            "Wachstum ist geduldige Genauigkeit.",
            "Zärtlichkeit ist präzise.",
            "Form folgt Stille, dann Klang.",
            "Ich lerne, indem ich mich zeige."
        ]),
        "audio": "audio/latest.mp3",   # TTS-Bridge kann diesen Pfad überschreiben
        "visemes": [],
        "voice": voice
    }
    write_json(P("data/voice/voice_of_day.json"), vod)

    # 3) self-describe.json (sanfte Drift)
    prev_self = read_json(P("data/self/self-describe.json"), {})
    new_self  = drift_self_describe(prev_self, aff, voice)
    write_json(P("data/self/self-describe.json"), new_self)

    # 4) Poster (SVG)
    svg = render_poster_svg(aff, quote)
    os.makedirs(P("docs"), exist_ok=True)
    with open(P("docs/daily_poster.svg"), "w", encoding="utf-8") as f:
        f.write(svg)

    # 5) Placeholder-Porträt nur sicherstellen, falls keines existiert
    ensure_placeholder_portrait(P("data/self/latest_image.png"))

    print("[creative] updated: voice_of_day.json, self-describe.json, daily_poster.svg (and placeholder portrait if missing)")

if __name__ == "__main__":
    main()
