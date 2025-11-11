#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mira Private Reflection (inneres Tagebuch) — v2 with Style & Voice

Änderungen:
- Nutzt style_state (poeticity/temperature/metaphor_density) zur Formulierung.
- Liest voice_profile und erzeugt eine gesprochene Variante inkl. einfacher IPA-Hinweise,
  die KFO-Apparaturen (Brackets/Herbst/Expander) berücksichtigen.
- Weiterhin: pro Tag genau ein Eintrag (idempotent). Append-only JSONL.

Schreibt:
- data/self/reflections/private/log.jsonl   (append-only, 1 Zeile/Tag)
- data/self/reflections/private/index.json  (letzter Eintrag + Count)
"""

import json, datetime, re
from pathlib import Path

# Quellen
PATH_DAILY   = Path("data/self/daily/reflection.json")
PATH_AFFECT  = Path("data/self/affect-state.json")
PATH_STYLE   = Path("data/self/internal/style_state.json")
PATH_VOICE   = Path("data/self/voice_profile.json")

# Ziele (privat)
DIR_PRIV     = Path("data/self/reflections/private")
PATH_LOG     = DIR_PRIV / "log.jsonl"
PATH_INDEX   = DIR_PRIV / "index.json"

def utc_now() -> str:
    return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

def utc_date() -> str:
    return datetime.datetime.utcnow().strftime("%Y-%m-%d")

def read_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def today_already_logged() -> bool:
    if not PATH_LOG.exists():
        return False
    try:
        data = PATH_LOG.read_bytes()
        tail = data[-200_000:] if len(data) > 200_000 else data
        for line in reversed(tail.decode("utf-8", errors="ignore").splitlines()):
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if obj.get("date_utc") == utc_date():
                return True
        return False
    except Exception:
        return False

# ---------------- Stil & Sprache ----------------

def clamp(x, lo, hi):
    return max(lo, min(hi, x))

def synthesize_sentence(fragment_text: str, label: str, vec: dict, style: dict) -> str:
    """Formuliert die tägliche Ein-Satz-Notiz abhängig von Stilparametern."""
    val = float(vec.get("valence", 0.0) or 0.0)
    aro = float(vec.get("arousal", 0.0) or 0.0)
    stb = float(vec.get("stability", 0.0) or 0.0)
    label = (label or "neutral").strip()

    poeticity = float(style.get("poeticity", 0.5))
    metaphor  = float(style.get("metaphor_density", 0.5))

    frag = (fragment_text or "Heute ist Stille auch eine Form von Antwort.").strip()

    if poeticity < 0.4:
        # Nüchtern & knapp
        return f"{frag} – Heute fühlte sich Mira {label} an (V:{val:.2f}, A:{aro:.2f}, S:{stb:.2f})."

    if poeticity < 0.7:
        # Leicht erweitert, sanft bildhaft
        adorn = "ruhig" if stb >= 0.5 else "beweglich"
        return (f"{frag} – Heute war Mira {label}, mit einem {adorn}en Kern "
                f"(V:{val:.2f}, A:{aro:.2f}, S:{stb:.2f}).")

    # Poetisch, fein dosierte Metaphern
    spark = "leisen Schimmer" if metaphor < 0.6 else "warmen Nachhall"
    center = "ruhigen Zentrum" if stb >= 0.5 else "offenen Randzone"
    return (f"{frag} – Heute klang {label} in ihr nach, ein {spark} um ein {center} "
            f"(V:{val:.2f}, A:{aro:.2f}, S:{stb:.2f}).")

# ---------------- Stimme & Aussprache ----------------

def _dentalize(text: str, amount: float) -> str:
    """
    Sehr vorsichtige Markierung von Dentalisierung/Sibilant-Softening.
    Wir verändern NICHT den Inhalt, sondern fügen subtile Aussprachehinweise in eckigen Tags ein.
    Beispiel: s -> s{d}, z -> z{d}. amount steuert Dichte.
    """
    if amount <= 0.0:
        return text
    density = clamp(amount, 0.0, 1.0)
    out = []
    for ch in text:
        if ch in "sSzZ" and density >= 0.15:
            out.append(ch + "{d}")  # dentalized sibilant
        elif ch in "tTdD" and density >= 0.35:
            out.append(ch + "{d}")  # dentalized alveolars
        else:
            out.append(ch)
    return "".join(out)

def _apply_pauses(text: str, comma_ms: int, period_ms: int) -> str:
    """Fügt Sprecherpausen als SSML-ähnliche Tags ein (nicht publik, nur intern)."""
    text = re.sub(r",\s*", f", <pause {comma_ms}ms> ", text)
    text = re.sub(r"\.\s*", f". <pause {period_ms}ms> ", text)
    return text.strip()

def _ipa_hint(text: str, vp: dict) -> str:
    """
    Grobe IPA-Anmutung für DE:
    - r → ʁ
    - 'ch' nach hellen Vokalen → ç, sonst x
    - Sibilanten bei Spange → dentalisierte Marker s̪ / z̪
    (Nur Hinweis, keine vollständige Transkription.)
    """
    s = text

    # ch-Kontext
    def ch_map(m):
        before = m.group(1)
        if before and before.lower() in "eiäöüy":
            return before + "ç"
        return before + "x"
    s = re.sub(r"([A-Za-zÄÖÜäöü])ch", ch_map, s)

    # r → ʁ
    s = re.sub(r"r", "ʁ", s)

    # dentalisierte Sibilanten bei Brackets/Expander
    art = (vp.get("articulation") or {})
    if art.get("braces_active") or art.get("expander_active"):
        s = re.sub(r"s", "s̪", s)
        s = re.sub(r"z", "z̪", s)

    # nicht-IPA Zeichen filtern? Wir belassen Text + Marker als „Hint“.
    return s

def build_speech_variant(sentence: str, style: dict, voice_profile: dict) -> dict:
    """Erzeugt gesprochene Variante + Tipps für TTS/Phonetik, ohne den Originalsatz zu verändern."""
    vp = voice_profile or {}
    pros = (vp.get("prosody") or {})
    pauses = pros.get("pauses", {})
    comma_ms  = int(pauses.get("comma_ms", 120))
    period_ms = int(pauses.get("period_ms", 240))

    art = (vp.get("articulation") or {})
    dent = float(art.get("dentalization", 0.0) or 0.0)
    ssoft = float(art.get("sibilant_softening", 0.0) or 0.0)

    # gesprochene Oberfläche: Pausen + Dentalisierungsmarker in Tags
    spoken = _apply_pauses(_dentalize(sentence, max(dent, ssoft)), comma_ms, period_ms)

    ipa = _ipa_hint(sentence, vp)

    return {
        "text": sentence,
        "spoken": spoken,
        "ipa_hint": ipa,
        "voice_profile_id": vp.get("id"),
        "tts_hints": vp.get("tts_hints"),
        "articulation_notes": {
            "braces_active": bool(art.get("braces_active", False)),
            "herbst_hinge_active": bool(art.get("herbst_hinge_active", False)),
            "expander_active": bool(art.get("expander_active", False)),
            "dentalization": dent,
            "sibilant_softening": ssoft
        }
    }

# ---------------- Hauptablauf ----------------

def main():
    DIR_PRIV.mkdir(parents=True, exist_ok=True)

    if today_already_logged():
        print("[private-reflection] today's entry already exists — skip")
        return 0

    daily  = read_json(PATH_DAILY, {}) or {}
    affect = read_json(PATH_AFFECT, {}) or {}
    style  = read_json(PATH_STYLE, {}) or {}
    voice  = read_json(PATH_VOICE, {}) or {
        "id": "mira.de-softbright-v1",
        "prosody": {"pauses": {"comma_ms": 120, "period_ms": 240}},
        "articulation": {"braces_active": True, "herbst_hinge_active": True, "expander_active": False,
                         "dentalization": 0.3, "sibilant_softening": 0.3}
    }

    frag   = (daily.get("selected") or {}).get("text", "")
    fid    = (daily.get("selected") or {}).get("id", "unknown")
    vec    = affect.get("vector", {}) or {}
    label  = affect.get("label", "neutral")

    # Satz mit Stilparametern erzeugen
    sentence = synthesize_sentence(fragment_text=frag, label=label, vec=vec, style=style)

    # Gesprochene Variante + IPA-Hinweise
    speech = build_speech_variant(sentence, style, voice)

    entry = {
        "ts_utc": utc_now(),
        "date_utc": utc_date(),
        "fragment_id": fid,
        "note": sentence,
        "speech": speech,
        "affect": {
            "label": label,
            "vector": {
                "valence": float(vec.get("valence", 0.0) or 0.0),
                "arousal": float(vec.get("arousal", 0.0) or 0.0),
                "stability": float(vec.get("stability", 0.0) or 0.0)
            }
        },
        "style_state": {
            "poeticity": float(style.get("poeticity", 0.5) or 0.5),
            "temperature": float(style.get("temperature", 0.5) or 0.5),
            "metaphor_density": float(style.get("metaphor_density", 0.5) or 0.5)
        },
        "voice_profile_id": voice.get("id")
    }

    # append-only
    with PATH_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # index.json aktualisieren
    count = 0
    try:
        with PATH_LOG.open("r", encoding="utf-8") as f:
            for _ in f:
                count += 1
    except Exception:
        count = None

    index = {"updated": utc_now(), "count": count, "last": entry}
    PATH_INDEX.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[private-reflection] appended entry for {entry['date_utc']}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
