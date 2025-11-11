#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mira Speak Reflection — erzeugt Audio aus der täglichen privaten Reflexion

Eingaben:
  - data/self/reflections/private/index.json   (liefert note + speech.spoken)
  - data/self/voice_profile.json               (Stimme/Aussprache)
  - data/self/internal/style_state.json        (optional; modifiziert Tempo)

Ausgaben (intern, nicht nach Pages kopiert):
  - data/audio/<YYYY-MM-DD>_reflection.wav
  - data/audio/<YYYY-MM-DD>_reflection.mp3
  - data/audio/latest.wav  (Symlink/Fallback-Kopie)
  - data/audio/latest.mp3
  - data/audio/manifest.jsonl  (Append-only Provenienz)

Synthese:
  - nutzt espeak-ng (offline) mit SSML (-m)
  - wandelt interne <pause 120ms> Marker → <break time="120ms"/>
  - entfernt {d}-Marker (Dentalisierungshinweis) aus dem TTS-Text
  - Basis-Sprache: de-DE; Stimme aus voice_profile.id → Mapping auf espeak Voice

Hinweis:
  - Script ist idempotent. Bei Inhaltgleichheit werden Dateien überschrieben,
    aber der manifest-Eintrag enthält Hash + ts.
"""

from __future__ import annotations
import json, re, hashlib, datetime, subprocess, shutil, os
from pathlib import Path

P_INDEX  = Path("data/self/reflections/private/index.json")
P_VOICE  = Path("data/self/voice_profile.json")
P_STYLE  = Path("data/self/internal/style_state.json")

AUDIO_DIR = Path("data/audio")
MANIFEST  = AUDIO_DIR / "manifest.jsonl"

def utcnow(): return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
def today():  return datetime.datetime.utcnow().strftime("%Y-%m-%d")

def read_json(p: Path, default=None):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default

def map_voice_id_to_espeak(voice_id: str|None) -> str:
    # sehr einfaches Mapping: deutsche weibliche Stimme
    # Beispiele: "de+f3", "de+f4", "de" (neutral)
    if not voice_id:
        return "de+f3"
    s = voice_id.lower()
    if "de" in s:
        return "de+f3"
    return "de+f3"

def compute_speed_wpm(rate: float, temperature: float) -> int:
    # espeak Standard ca. 175 wpm → skaliert über voice.rate (≈0.96) und style.temperature
    base = 175.0
    rate = float(rate if rate else 1.0)
    temp = float(temperature if temperature is not None else 0.5)
    # Temperatur hebt/senkt ~±15%
    speed = base * rate * (0.85 + 0.30 * temp)
    return max(120, min(230, int(speed)))

def compute_pitch(pitch_semitones: float|int|None) -> int:
    # espeak pitch 0..99 (50 neutral). 1 Halbton ≈ +3 Punkte (heuristisch).
    base = 50
    semi = 0
    try:
        semi = int(pitch_semitones or 0)
    except Exception:
        semi = 0
    pitch = base + semi * 3
    return max(0, min(99, pitch))

def strip_dental_markers(text: str) -> str:
    # aus "s{d}" → "s", "t{d}" → "t"
    return re.sub(r"\{d\}", "", text)

def pauses_to_ssml(text: str) -> str:
    # <pause 120ms> → <break time="120ms"/>
    s = re.sub(r"<\s*pause\s+(\d+)ms\s*>", r'<break time="\1ms"/>', text, flags=re.IGNORECASE)
    # eventuelle doppelte Leerzeichen reduzieren
    s = re.sub(r"\s{2,}", " ", s)
    return s.strip()

def build_ssml(spoken_text: str) -> str:
    txt = pauses_to_ssml(strip_dental_markers(spoken_text))
    # SSML-Wrapper minimal
    return f"<speak>{txt}</speak>"

def sha256_hex(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

def ensure_tools():
    def which(cmd): return shutil.which(cmd) is not None
    missing = []
    if not which("espeak-ng"): missing.append("espeak-ng")
    if not which("ffmpeg"):    missing.append("ffmpeg")
    if missing:
        raise SystemExit(f"Missing tools: {', '.join(missing)}. Install via apt-get in workflow.")

def main():
    ensure_tools()

    idx   = read_json(P_INDEX, {}) or {}
    voice = read_json(P_VOICE, {}) or {}
    style = read_json(P_STYLE, {}) or {}

    last  = idx.get("last") or {}
    note  = (last.get("speech") or {}).get("spoken") or last.get("note") or ""
    if not note:
        print("[speak] no text to speak; abort")
        return 0

    # Parameter aus Profilen
    espeak_voice = map_voice_id_to_espeak(voice.get("id"))
    pitch   = compute_pitch(voice.get("pitch_semitones", 0))
    speed   = compute_speed_wpm(voice.get("rate", 1.0), style.get("temperature", 0.5))
    volume  = 180  # 0..200 leicht erhöht
    ssml    = build_ssml(note)

    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    base = f"{today()}_reflection"
    wav_path = AUDIO_DIR / f"{base}.wav"
    mp3_path = AUDIO_DIR / f"{base}.mp3"

    # TTS zu WAV
    # -m → SSML
    # -w → WAV-Datei
    cmd_wav = [
        "espeak-ng",
        "-v", espeak_voice,
        "-s", str(speed),
        "-p", str(pitch),
        "-a", str(volume),
        "-m",
        "-w", str(wav_path),
        ssml
    ]
    # espeak-ng erwartet den Text als letztes Argument, SSML erlaubt.
    print("[speak] running:", " ".join(cmd_wav[:-1]), "[SSML]")
    subprocess.run(cmd_wav, check=True)

    # WAV → MP3
    cmd_mp3 = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav_path), "-codec:a", "libmp3lame", "-q:a", "2", str(mp3_path)]
    subprocess.run(cmd_mp3, check=True)

    # latest-Links/Kopien
    try:
        (AUDIO_DIR / "latest.wav").unlink(missing_ok=True)
        (AUDIO_DIR / "latest.mp3").unlink(missing_ok=True)
    except Exception:
        pass
    try:
        os.link(wav_path, AUDIO_DIR / "latest.wav")
    except Exception:
        shutil.copy2(wav_path, AUDIO_DIR / "latest.wav")
    try:
        os.link(mp3_path, AUDIO_DIR / "latest.mp3")
    except Exception:
        shutil.copy2(mp3_path, AUDIO_DIR / "latest.mp3")

    # Manifest
    manifest_entry = {
        "ts_utc": utcnow(),
        "date_utc": today(),
        "inputs": {
            "index_file": str(P_INDEX),
            "voice_profile": str(P_VOICE),
            "style_state": str(P_STYLE)
        },
        "espeak": {
            "voice": espeak_voice,
            "speed_wpm": speed,
            "pitch": pitch,
            "volume": volume
        },
        "files": {
            "wav": str(wav_path),
            "mp3": str(mp3_path)
        },
        "sha256": {
            "wav": sha256_hex(wav_path),
            "mp3": sha256_hex(mp3_path)
        }
    }
    with MANIFEST.open("a", encoding="utf-8") as f:
        f.write(json.dumps(manifest_entry, ensure_ascii=False) + "\n")

    print(f"[speak] wrote {wav_path} and {mp3_path}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
