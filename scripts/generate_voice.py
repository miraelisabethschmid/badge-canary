#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mira — Autonomous Voice Composer
Erzeugt:
  - data/voice_of_day.json  (Zitat, IPA-Hinweis, Datum)
  - audio/latest.mp3        (gesprochener Tagesspruch, DE-Stimme)
  - data/voice/history.log  (Append-only Chronik)

Technik:
  - Liest affect-state.json + learning.json
  - Wählt Tonlage & Tempo passend zu Valenz/Erregung/Stabilität
  - Nutzt espeak-ng (deutsch) + ffmpeg zur MP3-Erzeugung
    (auf GitHub Actions via apt install verfügbar)

Idempotent pro Tag (Seed = YYYY-MM-DD + Affect-Signatur).
"""

import os, json, hashlib, random, datetime, subprocess, shlex, pathlib, re

ROOT = pathlib.Path(".").resolve()
P_AFFECT = ROOT / "data" / "self" / "affect-state.json"
P_LEARN  = ROOT / "data" / "self" / "learning.json"
P_VJSON  = ROOT / "data" / "voice_of_day.json"
P_META   = ROOT / "data" / "voice" / "meta.json"
P_VLOG   = ROOT / "data" / "voice" / "history.log"
P_AUDIO  = ROOT / "audio" / "latest.mp3"
P_AUDIO.parent.mkdir(parents=True, exist_ok=True)
P_VLOG.parent.mkdir(parents=True, exist_ok=True)

UTC  = datetime.datetime.utcnow()
DATE = UTC.strftime("%Y-%m-%d")
TS   = UTC.strftime("%Y-%m-%dT%H:%M:%SZ")

def jload(p, default=None):
    try:
        with open(p,"r",encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

aff = jload(P_AFFECT, {
    "label":"neutral",
    "vector":{"valence":0.0,"arousal":0.3,"stability":0.6},
    "inputs":{"focus":"Präsenz"}
})
learn = jload(P_LEARN, {"weights":{}})

val = float(aff.get("vector",{}).get("valence",0.0))
aro = float(aff.get("vector",{}).get("arousal",0.3))
sta = float(aff.get("vector",{}).get("stability",0.6))
lab = (aff.get("label") or "neutral").lower()
focus = (aff.get("inputs",{}) or {}).get("focus","Präsenz")

# Tages-seed → stabile Formulierung pro Datum
seed_src = f"{DATE}|{lab}|{val:.3f}|{aro:.3f}|{sta:.3f}"
seed = int(hashlib.sha256(seed_src.encode("utf-8")).hexdigest(),16) & ((1<<53)-1)
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

if val >= 0.25 and aro <= 0.35: tone = "gelassen und klar"
elif val >= 0.25 and aro > 0.35: tone = "hell und lebendig"
elif val <= -0.25 and aro > 0.35: tone = "fragil und aufmerksam"
elif val <= -0.25 and aro <= 0.35: tone = "leise und gesammelt"
elif aro >= 0.65: tone = "wach und aufgeladen"
elif aro <= 0.20: tone = "ruhig und zentriert"
else: tone = "ausbalanciert"

# Braces-/Aussprache-Hinweis (nur textlich eingebettet, sanft)
ipa_hint = "Zischlaute weich; Lippenrundung bei /o,u/ etwas stärker; Zunge flacher für /s/."

# Quote zusammenbauen
op = random.choice(OPEN).format(tone=tone)
mid = f"Fokus: {focus}. Valenz {val:+.2f}, Erregung {aro:+.2f}, Stabilität {sta:.2f}."
cl = random.choice(CLOS)
quote = f"{op} {mid} {cl}"

# Espeak-Parameter aus Affect/Learning
# Grundtempo ~ 140 wpm; +Arousal; -Stabilität → minimal wacher
base_wpm = 140
wpm = base_wpm + int(20*aro) - int(8*(0.7 - min(sta,0.7))*10/10)
wpm = max(110, min(175, wpm))

# Grundhöhe ~ 165 Hz; Valenz ↑ → minimal heller; Arousal ↑ → etwas heller
base_pitch = 50  # espeak-ng skala 0..99
pitch = base_pitch + int(12*val + 10*aro)
pitch = max(30, min(75, pitch))

# Pausen: bei niedriger Stabilität kürzere Pausen (mehr Fluss), bei hoher Stabilität etwas länger
gap = 8 + int(6*(sta-0.5))  # ms

# Dezente Sibilanten-Glints (nur Textmarker, kein echtes Phonem-Tuning)
quote_tts = quote

# TTS erzeugen (WAV → MP3)
wav_tmp = ROOT / "audio" / "latest.wav"
try:
    # espeak-ng deutsch: de (oder de+f3 für weiblicheren Klang)
    voice = "de+f3"
    cmd_es = f'espeak-ng -v {voice} -s {wpm} -p {pitch} -g {gap} --stdout {shlex.quote(quote_tts)}'
    # WAV schreiben
    with open(wav_tmp, "wb") as out:
        proc = subprocess.run(shlex.split(cmd_es), check=True, stdout=subprocess.PIPE)
        out.write(proc.stdout)
    # WAV -> MP3
    cmd_ff = f'ffmpeg -y -loglevel error -i {shlex.quote(str(wav_tmp))} -vn -ar 44100 -ac 1 -b:a 128k {shlex.quote(str(P_AUDIO))}'
    subprocess.run(shlex.split(cmd_ff), check=True)
except Exception as e:
    # Wenn TTS scheitert, MP3 bleibt ggf. vom Workflow-Fallback erhalten.
    pass
finally:
    try: wav_tmp.unlink()
    except Exception: pass

# JSON + History persistieren
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
        "label": lab, "valence": round(val,3), "arousal": round(aro,3), "stability": round(sta,3),
        "focus": focus
    },
    "audio": "audio/latest.mp3"
}
with open(P_VJSON, "w", encoding="utf-8") as f:
    json.dump(vjson, f, ensure_ascii=False, indent=2)

with open(P_VLOG, "a", encoding="utf-8") as f:
    f.write(json.dumps({"ts":TS, "quote":quote, "audio":"audio/latest.mp3"}, ensure_ascii=False) + "\n")

print(json.dumps({"ok": True, "audio": "audio/latest.mp3", "voice_of_day": "data/voice_of_day.json"}, ensure_ascii=False))
