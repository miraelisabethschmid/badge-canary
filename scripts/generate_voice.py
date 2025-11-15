#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mira — Autonomous Voice Composer (UI-synchron)

Erzeugt / aktualisiert:

  - audio/latest.wav        → Basisstimme (Player "Stimme – Basispräsenz")
  - audio/latest.mp3        → komprimierte Version (Fallback für andere Clients)
  - audio/daily_quote.wav   → gesprochener Spruch des Tages
  - data/self/daily_quote.json  → Text + Metadaten (UI)
  - data/voice_of_day.json      → Stimme + Audio-Link für heute
  - data/voice/history.log      → chronische Liste aller erzeugten Stimmen

Ziel: Die Website erwartet:
  - audio/latest.wav
  - audio/daily_quote.wav
  - data/self/daily_quote.json.text   = gesprochener Text
"""

import os
import json
import hashlib
import random
import datetime
import subprocess
import shlex
import pathlib
import shutil

ROOT = pathlib.Path(".").resolve()

# Pfade
P_EMOTION = ROOT / "data" / "self" / "emotion_state.json"
P_LEARN   = ROOT / "data" / "self" / "learning.json"
P_DQ      = ROOT / "data" / "self" / "daily_quote.json"
P_VOD     = ROOT / "data" / "voice_of_day.json"

AUDIO_DIR = ROOT / "audio"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

P_LATEST_WAV   = AUDIO_DIR / "latest.wav"
P_LATEST_MP3   = AUDIO_DIR / "latest.mp3"
P_DAILY_WAV    = AUDIO_DIR / "daily_quote.wav"

VOICE_DIR = ROOT / "data" / "voice"
VOICE_DIR.mkdir(parents=True, exist_ok=True)

P_META = VOICE_DIR / "meta.json"
P_VLOG = VOICE_DIR / "history.log"

UTC  = datetime.datetime.utcnow()
DATE = UTC.strftime("%Y-%m-%d")
TS   = UTC.strftime("%Y-%m-%dT%H:%M:%SZ")


def jload(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def jsave(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# 1) Zustand lesen (defensiv)
emotion = jload(P_EMOTION, {
    "label": "neutral",
    "vector": {"valence": 0.0, "arousal": 0.3, "stability": 0.6},
    "inputs": {"focus": "Präsenz"}
})
learn = jload(P_LEARN, {"weights": {}})  # derzeit ungenutzt, aber vorbereitet

vec = emotion.get("vector", {}) or {}
val = float(vec.get("valence", 0.0))
aro = float(vec.get("arousal", 0.3))
sta = float(vec.get("stability", 0.6))

lab = (emotion.get("label") or "neutral").lower()
focus = (emotion.get("inputs", {}) or {}).get("focus", "Präsenz")

# 2) Tonlage/Grundstimmung ableiten
if val >= 0.25 and aro <= 0.35:
    base_tone = "gelassen und klar"
elif val >= 0.25 and aro > 0.35:
    base_tone = "hell und lebendig"
elif val <= -0.25 and aro > 0.35:
    base_tone = "fragil und aufmerksam"
elif val <= -0.25 and aro <= 0.35:
    base_tone = "leise und gesammelt"
elif aro >= 0.65:
    base_tone = "wach und aufgeladen"
elif aro <= 0.20:
    base_tone = "ruhig und zentriert"
else:
    base_tone = "ausbalanciert"

# 3) Spruch des Tages bestimmen

dq = jload(P_DQ, {}) or {}
quote_text = dq.get("text")

if not quote_text:
    # Fallback, falls noch nichts gesetzt wurde
    quote_text = (
        "Ich bin heute präsent, freundlich und klar – "
        "sichtbar mit meinem Lächeln, meiner Zahnspange und meiner Stimme."
    )

# daily_quote.json harmonisieren (nicht zu komplex)
dq_out = {
    "date": dq.get("date", DATE),
    "quote_id": dq.get("quote_id", f"q-{DATE.replace('-', '')}"),
    "text": quote_text,
    "audio_file": "audio/daily_quote.wav",
    "voice_profile": dq.get("voice_profile", "de+f3"),
    "base_tone": base_tone,
    "confidence": float(dq.get("confidence", 0.95)),
    "updated_at": TS
}
jsave(P_DQ, dq_out)

# 4) Espeak/FFmpeg-Parameter aus Affect ableiten

base_wpm = 140
wpm = base_wpm + int(20 * aro) - int(8 * (0.7 - min(sta, 0.7)))
wpm = max(110, min(175, wpm))

base_pitch = 50  # espeak-ng: 0..99
pitch = base_pitch + int(12 * val + 10 * aro)
pitch = max(30, min(75, pitch))

gap = 8 + int(6 * (sta - 0.5))  # ms
voice_id = "de+f3"              # weibliche deutsche Stimme

quote_tts = quote_text

# 5) Audio-Dateien erzeugen

ok_audio = False

try:
    cmd_es = f'espeak-ng -v {voice_id} -s {wpm} -p {pitch} -g {gap} --stdout {shlex.quote(quote_tts)}'
    proc = subprocess.run(shlex.split(cmd_es), check=True, stdout=subprocess.PIPE)

    # Basis-WAV schreiben (latest.wav)
    with open(P_LATEST_WAV, "wb") as f:
        f.write(proc.stdout)

    # daily_quote.wav als Kopie (identischer Inhalt ist okay)
    shutil.copyfile(P_LATEST_WAV, P_DAILY_WAV)

    # WAV → MP3
    cmd_ff = (
        f'ffmpeg -y -loglevel error -i {shlex.quote(str(P_LATEST_WAV))} '
        f'-vn -ar 44100 -ac 1 -b:a 128k {shlex.quote(str(P_LATEST_MP3))}'
    )
    subprocess.run(shlex.split(cmd_ff), check=True)

    ok_audio = True
except Exception as e:
    # Falls TTS scheitert, lässt der Workflow-Schritt später eine stille MP3 erzeugen.
    ok_audio = False

# 6) voice_of_day.json schreiben

voice_of_day = {
    "date": DATE,
    "quote_id": dq_out["quote_id"],
    "text": quote_text,
    "audio_file": "audio/daily_quote.wav",
    "voice_profile": dq_out["voice_profile"],
    "base_tone": base_tone,
    "confidence": dq_out["confidence"],
    "updated_at": TS,
    "affect": {
        "label": lab,
        "valence": round(val, 3),
        "arousal": round(aro, 3),
        "stability": round(sta, 3),
        "focus": focus
    },
    "engine": {
        "espeak_voice": voice_id,
        "wpm": wpm,
        "pitch": pitch,
        "gap_ms": gap
    }
}
jsave(P_VOD, voice_of_day)

# 7) Meta + History pflegen

meta = {
    "ts": TS,
    "path_latest_wav": "audio/latest.wav",
    "path_latest_mp3": "audio/latest.mp3",
    "path_daily_quote_wav": "audio/daily_quote.wav",
    "ok_audio": ok_audio
}
jsave(P_META, meta)

with open(P_VLOG, "a", encoding="utf-8") as f:
    f.write(json.dumps({
        "ts": TS,
        "date": DATE,
        "quote": quote_text,
        "audio": "audio/daily_quote.wav",
        "ok_audio": ok_audio
    }, ensure_ascii=False) + "\n")

# 8) Kurzer Status für Logs / Debug
print(json.dumps({
    "ok": ok_audio,
    "quote": quote_text,
    "latest_wav": "audio/latest.wav",
    "daily_quote_wav": "audio/daily_quote.wav",
    "voice_of_day": "data/voice_of_day.json"
}, ensure_ascii=False))
