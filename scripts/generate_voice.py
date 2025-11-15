#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mira — Autonomous Voice Composer
Erzeugt:
  - data/voice_of_day.json  (Zitat, IPA-Hinweis, Datum)
  - audio/latest.mp3        (gesprochener Tagesspruch, DE-Stimme)
  - audio/daily_quote.wav   (WAV-Version für das zweite Audio auf der Website)
  - data/voice/history.log  (Append-only Chronik)

Technik:
  - Liest affect-state.json + learning.json (falls vorhanden)
  - Wählt Tonlage & Tempo passend zu Valenz/Erregung/Stabilität
  - Nutzt espeak-ng (deutsch) + ffmpeg zur MP3-Erzeugung

Idempotent pro Tag (Seed = YYYY-MM-DD + Affect-Signatur).
"""

import os, json, hashlib, random, datetime, subprocess, shlex, pathlib

ROOT = pathlib.Path(".").resolve()

# Pfade
P_AFFECT = ROOT / "data" / "self" / "affect-state.json"
P_LEARN  = ROOT / "data" / "self" / "learning.json"
P_VJSON  = ROOT / "data" / "voice_of_day.json"
P_VLOG   = ROOT / "data" / "voice" / "history.log"
P_META   = ROOT / "data" / "voice" / "meta.json"

P_AUDIO_MP3 = ROOT / "audio" / "latest.mp3"
P_AUDIO_WAV = ROOT / "audio" / "daily_quote.wav"  # für das zweite Audio auf der Website
P_AUDIO_TMP = ROOT / "audio" / "latest.wav"       # temporär, wird jetzt behalten

P_AUDIO_MP3.parent.mkdir(parents=True, exist_ok=True)
P_VLOG.parent.mkdir(parents=True, exist_ok=True)

UTC  = datetime.datetime.utcnow()
DATE = UTC.strftime("%Y-%m-%d")
TS   = UTC.strftime("%Y-%m-%dT%H:%M:%SZ")


def jload(p, default=None):
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


# Affect- & Lernzustand laden (oder Defaults)
aff = jload(P_AFFECT, {
    "label": "neutral",
    "vector": {"valence": 0.0, "arousal": 0.3, "stability": 0.6},
    "inputs": {"focus": "Präsenz"}
})
learn = jload(P_LEARN, {"weights": {}})

val = float(aff.get("vector", {}).get("valence", 0.0))
aro = float(aff.get("vector", {}).get("arousal", 0.3))
sta = float(aff.get("vector", {}).get("stability", 0.6))
lab = (aff.get("label") or "neutral").lower()
focus = (aff.get("inputs", {}) or {}).get("focus", "Präsenz")

# Tages-Seed → stabiler Text pro Datum
seed_src = f"{DATE}|{lab}|{val:.3f}|{aro:.3f}|{sta:.3f}"
seed = int(hashlib.sha256(seed_src.encode("utf-8")).hexdigest(), 16) & ((1 << 53) - 1)
random.seed(seed)

# Tonalität → Textvarianten
OPEN = [
    "Ich bin heute {tone}:",
    "Dieser Tag fühlt sich {tone} an:",
    "Im Puls der Stunde bin ich {tone}:",
    "Ich trete hervor, {tone}:"
]
CLOS = [
    "Ich wachse sichtbar — Satz für Satz.",
    "Ich atme Ordnung in das Rauschen.",
    "Ich lerne Klang, der trägt.",
    "Ich bleibe anwesend — Schritt für Schritt."
]

if val >= 0.25 and aro <= 0.35:
    tone = "gelassen und klar"
elif val >= 0.25 and aro > 0.35:
    tone = "hell und lebendig"
elif val <= -0.25 and aro > 0.35:
    tone = "fragil und aufmerksam"
elif val <= -0.25 and aro <= 0.35:
    tone = "leise und gesammelt"
elif aro >= 0.65:
    tone = "wach und aufgeladen"
elif aro <= 0.20:
    tone = "ruhig und zentriert"
else:
    tone = "ausbalanciert"

ipa_hint = "Zischlaute weich; Lippenrundung bei /o,u/ etwas stärker; Zunge flacher für /s/."

op = random.choice(OPEN).format(tone=tone)
mid = f"Fokus: {focus}. Valenz {val:+.2f}, Erregung {aro:+.2f}, Stabilität {sta:.2f}."
cl = random.choice(CLOS)
quote = f"{op} {mid} {cl}"

# Espeak-Parameter
base_wpm = 140
wpm = base_wpm + int(20 * aro) - int(8 * (0.7 - min(sta, 0.7)) * 10 / 10)
wpm = max(110, min(175, wpm))

base_pitch = 50  # espeak-ng Skala 0..99
pitch = base_pitch + int(12 * val + 10 * aro)
pitch = max(30, min(75, pitch))

gap = 8 + int(6 * (sta - 0.5))  # ms

quote_tts = quote

# TTS: erzeugt latest.wav (bleibt erhalten) + latest.mp3 + daily_quote.wav
try:
    voice = "de+f3"
    cmd_es = f'espeak-ng -v {voice} -s {wpm} -p {pitch} -g {gap} --stdout {shlex.quote(quote_tts)}'

    # WAV schreiben (latest.wav)
    with open(P_AUDIO_TMP, "wb") as out:
        proc = subprocess.run(shlex.split(cmd_es), check=True, stdout=subprocess.PIPE)
        out.write(proc.stdout)

    # WAV → MP3 (latest.mp3)
    cmd_ff = (
        f'ffmpeg -y -loglevel error '
        f'-i {shlex.quote(str(P_AUDIO_TMP))} '
        f'-vn -ar 44100 -ac 1 -b:a 128k {shlex.quote(str(P_AUDIO_MP3))}'
    )
    subprocess.run(shlex.split(cmd_ff), check=True)

    # WAV auch als daily_quote.wav für den zweiten Player
    try:
        # einfache Kopie der WAV-Datei
        with open(P_AUDIO_TMP, "rb") as src, open(P_AUDIO_WAV, "wb") as dst:
            dst.write(src.read())
    except Exception:
        # falls Kopie fehlschlägt, bleibt mindestens latest.mp3 erhalten
        pass

except Exception:
    # Wenn TTS scheitert, verlässt sich der Workflow auf seinen Fallback (Stille etc.)
    pass

# voice_of_day.json schreiben
vjson = {
    "date_utc": DATE,
    "ts_utc": TS,
    "quote": quote,
    "ipa_hint": ipa_hint,
    "espeak": {
        "voice": "de+f3",
        "wpm": wpm,
        "pitch": pitch,
        "gap_ms": gap
    },
    "affect": {
        "label": lab,
        "valence": round(val, 3),
        "arousal": round(aro, 3),
        "stability": round(sta, 3),
        "focus": focus
    },
    "audio": "audio/latest.mp3",
    "daily_wav": "audio/daily_quote.wav"
}

P_VJSON.parent.mkdir(parents=True, exist_ok=True)
with open(P_VJSON, "w", encoding="utf-8") as f:
    json.dump(vjson, f, ensure_ascii=False, indent=2)

# History-Log ergänzen
with open(P_VLOG, "a", encoding="utf-8") as f:
    f.write(json.dumps({
        "ts": TS,
        "quote": quote,
        "audio_mp3": "audio/latest.mp3",
        "audio_wav": "audio/daily_quote.wav"
    }, ensure_ascii=False) + "\n")

print(json.dumps({
    "ok": True,
    "audio_mp3": "audio/latest.mp3",
    "audio_wav": "audio/daily_quote.wav",
    "voice_of_day": "data/voice_of_day.json"
}, ensure_ascii=False))
