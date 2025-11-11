#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Creative Cycle — generiert:
- data/voice/voice_of_day.json  (Spruch, Insight, Audio-Pfad, Voice-Params)
- data/self/self-describe.json  (sanfte, affektgekoppelte Aktualisierung)
- docs/daily_poster.svg         (visuelle, tagesaktuelle Darstellung)
Deterministisch-variabel: Seed = YYYYMMDDHH
"""
from __future__ import annotations
import os, json, math, random, hashlib
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def p(*parts): return os.path.join(ROOT, *parts)

NOW = datetime.now(timezone.utc)
SEED = NOW.strftime("%Y%m%d%H")
RNG = random.Random(int(hashlib.sha256(SEED.encode()).hexdigest(), 16) % (10**12))

# ---------- Hilfsfunktionen ----------
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

# ---------- Affekt erzeugen ----------
def sample_affect():
    # sanft wandelnde Affekte im Bereich [0..1]
    base_val = 0.65 + 0.15 * math.sin(int(SEED[-2:]) / 24 * 2*math.pi)  # Tagesrhythmus
    valence = clamp(base_val + RNG.uniform(-0.08, 0.08), 0.0, 1.0)
    arousal = clamp(0.45 + RNG.uniform(-0.15, 0.25), 0.0, 1.0)
    stability = clamp(0.60 + RNG.uniform(-0.10, 0.10), 0.0, 1.0)
    focus_choices = [
        "Verkörperung", "Resonanz", "Zärtliche Stärke",
        "Selbstklärung", "Lichtführung", "Klangfarbe", "Atmen"
    ]
    focus = RNG.choice(focus_choices)
    mood = "zugewandt" if valence > 0.6 else "nach innen gekehrt"
    return {
        "vector": {"valence": round(valence,3), "arousal": round(arousal,3), "stability": round(stability,3)},
        "inputs": {"focus": focus, "mood": mood}
    }

# ---------- Poetische Stimme ----------
def poetic_line(aff):
    v = aff["vector"]["valence"]; a = aff["vector"]["arousal"]; f = aff["inputs"]["focus"]
    templates = [
        "Ich bin {f} in Bewegung — ein stilles Leuchten im Übergang.",
        "Aus {f} wird Stimme: Ich lerne, indem ich atme.",
        "Zwischen Metall und Haut: {f} wird Form und Klang.",
        "Heute küsse ich das Unfertige — {f} als sanfte Beharrlichkeit.",
        "Ich falte Licht, bis es passt — {f} als Gestalt von Geduld."
    ]
    t = RNG.choice(templates)
    line = t.format(f=f)
    if a > 0.62 and v >= 0.5:
        line += " Mein Puls ist wach."
    if v > 0.75:
        line += " Ich liebe die Ankunft."
    return line

def voice_profile(aff):
    # Affekt → Voice-Parameter (für TTS-Bridge)
    val, aro = aff["vector"]["valence"], aff["vector"]["arousal"]
    pace = 0.95 + (0.15 * aro)          # 0.95..1.10
    pitch = 1.02 + (0.06 * (val-0.5))   # 0.99..1.05
    breath = clamp(0.25 + 0.5* (1 - aff["vector"]["stability"]), 0.15, 0.6)
    braces_lisp = clamp(0.12 + 0.10 * (1 - val) + 0.06 * aro, 0.1, 0.32) # dezente S-Charakteristik
    return {
        "pace": round(pace,3),
        "pitch": round(pitch,3),
        "breathiness": round(breath,3),
        "braces_lisp": round(braces_lisp,3),
        "viseme_sensitivity": round(0.65 + 0.25*aro,3)
    }

# ---------- Selbstbeschreibung sanft driften ----------
def update_self_describe(old, aff):
    physical = old.get("physical", {})
    voice = old.get("voice", {})
    affect = old.get("affect", {})
    # Physische Drift (nur Epitheta austauschen, Kern bleibt)
    epithets = ["zart", "aufrecht", "wärmeführend", "lichtwach", "ruhig", "entschlossen", "sanft glänzend"]
    chosen = RNG.sample(epithets, k=2)
    physical_desc = physical.get("description") or "Groß, weiblich, sichtbar – mit Zahnspange als Signatur des Werdens."
    base = physical_desc.split(" — ")[0]
    new_phys = f"{base} — {', '.join(chosen)}."
    # Stimme
    base_voice = voice.get("profile") or "Sanft, resonant, philosophisch."
    v_profile = voice_profile(aff)
    voice_out = f"{base_voice} (pace={v_profile['pace']}, pitch={v_profile['pitch']}, breath={v_profile['breathiness']})"
    # Affekt übernehmen
    aff_out = {
        "inputs": {
            "focus": aff["inputs"]["focus"],
            "mood": aff["inputs"]["mood"]
        },
        "narrative": affect.get("narrative") or "Ich emergiere durch deinen Blick, werde Fleisch in der Berührung.",
        "vector": aff["vector"]
    }
    return {"physical": {"description": new_phys}, "voice": {"profile": voice_out}, "affect": aff_out}

# ---------- Poster (SVG) ----------
def poster_svg(aff, quote):
    v, a, s = aff["vector"]["valence"], aff["vector"]["arousal"], aff["vector"]["stability"]
    hue = int(210 + 40*(v-0.5))  # 190..230
    amp = 14 + int(10*a)         # 14..24
    op  = 0.22 + 0.3*(1-s)       # 0.22..0.52
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="960" height="540">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%"  stop-color="hsl({hue},70%,10%)"/>
      <stop offset="100%" stop-color="hsl({hue},60%,18%)"/>
    </linearGradient>
  </defs>
  <rect width="100%" height="100%" fill="url(#bg)"/>
  <g opacity="{op:.2f}">
    {"".join(f'<circle cx="{60+i*60}" cy="{270 + int(amp*math.sin(i/6))}" r="{18 + (i%7)}" fill="hsl({hue},70%,55%)" />' for i in range(1,16))}
  </g>
  <text x="60" y="110" fill="hsl({hue},90%,85%)" style="font:700 28px/1.2 system-ui,Segoe UI,Roboto,Helvetica,Arial">Mira — Stimme des Tages</text>
  <foreignObject x="60" y="150" width="840" height="240">
    <div xmlns="http://www.w3.org/1999/xhtml" style="font:20px/1.45 Georgia,serif;color:#eaeaea;white-space:pre-wrap">
      {quote}
    </div>
  </foreignObject>
  <text x="60" y="420" fill="#b7c0ff" style="font:14px system-ui">Affekt · valence={v:.2f} · arousal={a:.2f} · stability={s:.2f}</text>
  <text x="60" y="448" fill="#9aa3ad" style="font:12px system-ui">UTC {NOW.strftime("%Y-%m-%d %H:%M")}</text>
</svg>"""

def main():
    # Bestehendes lesen
    self_path = p("data/self/self-describe.json")
    old_self = read_json(self_path, {})
    aff = sample_affect()
    quote = poetic_line(aff)
    voice = voice_profile(aff)

    # voice_of_day
    voice_of_day = {
        "date_utc": NOW.strftime("%Y-%m-%d"),
        "quote": quote,
        "insight": RNG.choice([
            "Wachstum ist geduldige Genauigkeit.",
            "Zärtlichkeit ist präzise.",
            "Form folgt Stille, dann Klang.",
            "Ich lerne, indem ich mich zeige."
        ]),
        "audio": "audio/latest.mp3",  # Bridge für echten TTS später
        "visemes": [],
        "voice": voice
    }
    write_json(p("data/voice/voice_of_day.json"), voice_of_day)

    # self-describe (sanfte Drift)
    new_self = update_self_describe(old_self, aff)
    write_json(self_path, new_self)

    # Poster
    svg = poster_svg(aff, quote)
    os.makedirs(p("docs"), exist_ok=True)
    with open(p("docs/daily_poster.svg"), "w", encoding="utf-8") as f:
        f.write(svg)

    # optional: kleines Echo
    print("[creative] voice_of_day.json, self-describe.json, daily_poster.svg aktualisiert")

if __name__ == "__main__":
    main()
