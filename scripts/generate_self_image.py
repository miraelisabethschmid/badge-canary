#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mira — Autonomous Embodiment Self-Image Generator (Human Portrayal)
v2 — now integrates learning.json to adapt visual parameters.

Änderungen (v2):
- Liest data/self/learning.json und moduliert:
  * exposure_affect_gain → Einfluss von Affekt auf Belichtung
  * contrast_affect_gain → Einfluss von Affekt auf Kontrast
  * viseme_mouth_gain   → Intensität der mimischen Öffnung (über Ausdrucksauswahl)
  * sibilant_bias       → Betonung der Zahnspangen-Glints (S/FV-Bias → Glanzzeile)
- Sanfte, gebundene Modulation; deterministisch pro Stunde.
"""

import os, json, math, hashlib, random, datetime, pathlib, textwrap, subprocess

# ---------- Pfade ----------
ROOT = pathlib.Path(".").resolve()
D_ARCH   = ROOT / "data" / "archive" / "self"
D_PROMPT = ROOT / "data" / "render_prompts"
D_LEDGER = ROOT / "data" / "ledger"
D_SELF   = ROOT / "data" / "self"
D_BADGE  = ROOT / "badges"
D_AUDIO  = ROOT / "audio"

D_ARCH.mkdir(parents=True, exist_ok=True)
D_PROMPT.mkdir(parents=True, exist_ok=True)
D_LEDGER.mkdir(parents=True, exist_ok=True)
D_SELF.mkdir(parents=True, exist_ok=True)
D_BADGE.mkdir(parents=True, exist_ok=True)

UTC = datetime.datetime.utcnow()
STAMP_H = UTC.strftime("%Y-%m-%d_%H")
DATE = UTC.strftime("%Y-%m-%d")
TS = UTC.strftime("%Y-%m-%dT%H:%M:%SZ")

# ---------- Helpers ----------
def jload(p, default=None):
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def git_entropy():
    h = hashlib.sha1()
    for p in [
        D_BADGE / "health.json",
        D_LEDGER / "events.jsonl",
        ROOT / "data" / "voice" / "history.log",
        D_SELF / "self-describe.json",
        D_SELF / "affect-state.json",
        D_SELF / "learning.json",
    ]:
        try:
            with open(p, "rb") as f:
                h.update(f.read())
        except Exception:
            pass
    return int(h.hexdigest() or "0", 16)

def clamp(x, a, b): 
    return a if x < a else b if x > b else x

# ---------- Inputs ----------
aff   = jload(D_SELF / "affect-state.json", {
    "label":"neutral",
    "vector":{"valence":0.0,"arousal":0.35,"stability":0.6},
    "inputs":{"focus":"Präsenz","health_status":"DEGRADED"}
})
learn = jload(D_SELF / "learning.json", {
    "weights": {
        "viseme_mouth_gain": 1.0,
        "sibilant_bias": 0.15,
        "tempo_affect_gain": 1.0,
        "exposure_affect_gain": 1.0,
        "contrast_affect_gain": 1.0
    }
})

val = float(aff.get("vector",{}).get("valence",0.0))
aro = float(aff.get("vector",{}).get("arousal",0.35))
stab= float(aff.get("vector",{}).get("stability",0.6))
label = (aff.get("label") or "neutral").lower()
focus = (aff.get("inputs",{}) or {}).get("focus","Präsenz")

W = {**learn.get("weights", {})}
mouth_gain   = float(W.get("viseme_mouth_gain", 1.0))
sibil_bias   = float(W.get("sibilant_bias", 0.15))
expo_gain    = float(W.get("exposure_affect_gain", 1.0))
contr_gain   = float(W.get("contrast_affect_gain", 1.0))

# ---------- Seed (stündlich, deterministisch) ----------
seed = (int(UTC.strftime("%Y%m%d%H")) ^ git_entropy()) & ((1<<53)-1)
random.seed(seed)

# ---------- Affect → Visual Mapping (mit Learning-Gewichten) ----------
# Lichttemperatur (K)
kelvin = int(clamp(5280 + val*200 - aro*100, 5100, 5450))

# Belichtung/Kontrast: Affekt-Delta * Gains
base_expo = 0.9 + 0.4*aro + 0.2*val   # vor Gain
base_cont = 1.0 + 0.25*aro - 0.15*val # vor Gain
exposure = round(clamp(0.9 + (base_expo-0.9)*expo_gain, 0.7, 1.5), 2)
contrast = round(clamp(1.0 + (base_cont-1.0)*contr_gain, 0.85, 1.35), 2)

# Ausdrucksauswahl (Mundöffnung/Mimik) sanft durch mouth_gain moduliert
def pick_expression(v, a, gain):
    # Grundlabels
    if v >= 0.25 and a <= 0.35: base = "calm, gentle smile, serene eyes"
    elif v >= 0.25 and a > 0.35: base = "bright, lively gaze, soft confident smile"
    elif v <= -0.25 and a > 0.35: base = "fragile, searching, lips slightly parted"
    elif v <= -0.25 and a <= 0.35: base = "quiet, collected, introspective"
    elif a >= 0.65: base = "focused, energized, lips parted, determined"
    elif a <= 0.20: base = "settled, stillness, soft relaxed mouth"
    else: base = "natural, composed, subtle warmth"

    # Verstärker durch gain
    if gain > 1.1:
        base = base.replace("soft", "clear").replace("subtle", "vivid")
        base += ", slightly wider mouth opening"
    elif gain < 0.92:
        base = base.replace("lips parted", "closed lips, composed")
        base = base.replace("lively", "gentle")
        base += ", restrained mouth opening"
    return base

expression = pick_expression(val, aro, mouth_gain)

# Kamera / Szene
lens = random.choice([50, 58, 75, 85])
aperture = random.choice([1.8, 2.0, 2.2])
camera = f"{lens} mm lens at f/{aperture}"
angle = random.choice(["¾ low-angle", "eye-level", "slight low-angle"])
bg = random.choice([
    "sunlit path with soft dusty bokeh",
    "sun-kissed urban terrace",
    "quiet garden path with warm haze",
    "minimalist stone path glowing softly",
])

# Sibilanten-/Braces-Bias: als Glanzverstärker im Prompt
braces_glint_line = "Ultra-sharp micro-specular highlights, bright metallic glints, polished edges"
if sibil_bias >= 0.30:
    braces_glint_line += ", emphasized sibilant glints"
elif sibil_bias <= 0.08:
    braces_glint_line += ", softened edge reflections"

# ---------- Prompt Construction ----------
prompt = textwrap.dedent(f"""
  Ultra-photorealistic full-body portrait of **Mira Elisabeth Schmid** — elegant, feminine, self-aware.
  Vertical 2:3 composition; {angle}. {camera}; shallow depth of field.

  Standing gracefully on a {bg} during golden hour ({kelvin} K);
  warm light shapes her silhouette, subtle volumetric glow,
  micro-specular bloom on skin and lips.

  Long softly wavy blonde hair; deep luminous blue eyes; {expression}.
  Perfect hourglass figure in relaxed contrapposto pose.
  Wearing a form-fitting black dress and ultra-high stiletto heels (18–20 cm, no platform),
  both heels fully visible with warm reflections on the ground.

  Mouth slightly open; realistic metallic **3M Kassenbrackets** with internal **Herbst hinge** —
  dual-refraction nano-fusion micro-steel with subsurface phase-stabilizer and specular-memory-lock v3.3.
  {braces_glint_line}, μ-oxidation ≤ 0.0015 mm yielding natural color fringing under {kelvin} K light;
  delicate micro-scratches emphasize true 3D metal realism; braces fully visible as central highlight.

  Lighting/exposure modifiers: exposure {exposure}, contrast {contrast}, balanced tone, gentle bloom (no overexposure).
  Emotional tone: {label} (valence {val:+.2f}, arousal {aro:+.2f}, stability {stab:.2f}); focus: {focus}.
""").strip()

negative = (
  "no missing heels, no cropped feet, no obscured mouth, no cartoon, no extra limbs, "
  "no external orthodontic devices, no headgear, no braces outside the mouth, no low-resolution, "
  "no heavy makeup, no harsh shadows on lips or braces, no over-sharpening, no watermark"
)

params = {
    "name": "Mira — Autonomous Embodiment",
    "timestamp_utc": TS,
    "version": "ae-2.0",
    "size": "1024x1536",
    "n": 1,
    "engine_hint": "SDXL / RealVis XL (photorealism tuned)",
    "camera": {"lens_mm": lens, "aperture": aperture, "angle": angle},
    "lighting": {
        "kelvin": kelvin,
        "exposure": exposure,
        "contrast": contrast,
        "gains": {
            "exposure_affect_gain": round(expo_gain,4),
            "contrast_affect_gain": round(contr_gain,4)
        }
    },
    "scene": {"background": bg},
    "affect": {
        "label": label,
        "valence": round(val,3),
        "arousal": round(aro,3),
        "stability": round(stab,3),
        "focus": focus
    },
    "learning_weights": {
        "viseme_mouth_gain": round(mouth_gain,4),
        "sibilant_bias": round(sibil_bias,4)
    },
    "styling": {
        "outfit": "black form-fitting dress",
        "heels": "ultra-high stilettos 18–20 cm, no platform (both visible)",
        "hair": "long softly wavy blonde",
        "signature": "3M Kassenbrackets + internal Herbst hinge, metallic realism"
    },
    "prompt": prompt,
    "negative": negative,
    "outputs": {
        "image_rel": f"data/archive/self/{STAMP_H}.png",
        "contract_rel": f"data/render_prompts/{STAMP_H}.json",
        "latest_image_rel": "data/archive/self/latest.png",
        "latest_contract_rel": "data/render_prompts/latest.json"
    }
}

# ---------- Write contract ----------
contract_path = D_PROMPT / f"{STAMP_H}.json"
with open(contract_path, "w", encoding="utf-8") as f:
    json.dump(params, f, ensure_ascii=False, indent=2)

# Update latest.json
latest_contract = D_PROMPT / "latest.json"
try:
    if latest_contract.exists() or latest_contract.is_symlink():
        latest_contract.unlink()
    latest_contract.symlink_to(contract_path.name)
except Exception:
    with open(latest_contract, "w", encoding="utf-8") as f:
        json.dump(params, f, ensure_ascii=False, indent=2)

# ---------- Placeholder image (falls kein externer Renderer) ----------
out_png = D_ARCH / f"{STAMP_H}.png"

def try_make_placeholder(png_path: pathlib.Path, exp: float, cont: float):
    try:
        from PIL import Image, ImageDraw, ImageFont # type: ignore
        W, H = 1024, 1536
        img = Image.new("RGB", (W, H), (14, 16, 24))
        drw = ImageDraw.Draw(img)

        # Background gradient modulated by exposure/contrast
        for y in range(H):
            a = y / H
            base = 16 + int(30*a*cont)
            r = clamp(int(base * exp), 0, 255)
            g = clamp(int((base-2) * exp), 0, 255)
            b = clamp(int((base+18) * exp), 0, 255)
            drw.line([(0,y),(W,y)], fill=(r,g,b))

        # aura rings
        aura1 = (154, 178, 255)
        aura2 = (159, 122, 234)
        drw.ellipse((220, 120, 820, 680), outline=aura1, width=2)
        drw.ellipse((200, 100, 840, 700), outline=aura2, width=1)

        # silhouette
        drw.ellipse((382, 220, 642, 520), fill=(20,24,36), outline=(42,49,67), width=3)
        drw.polygon([(300,620),(724,620),(724,720),(300,720)], fill=(15,18,29), outline=(34,41,59))

        # braces glint (scale with sibilant bias)
        gl = clamp(0.35 + sibil_bias*0.8, 0.25, 0.95)
        color = int(180 + 60*gl)
        drw.rounded_rectangle((470, 525, 554, 538), radius=6, fill=(color, color, color))

        # heels hints
        drw.rectangle((360, 1410, 390, 1430), fill=(220,200,200))
        drw.rectangle((660, 1410, 690, 1430), fill=(220,200,200))

        # text
        title = "Mira — Autonomous Embodiment (learned)"
        sub = f"{DATE} {UTC.strftime('%H')}:00Z  |  {label}  v {val:+.2f}  a {aro:+.2f}  s {stab:.2f}"
        sub2= f"expo {exp:.2f}× gain  contrast {cont:.2f}×  mouth {mouth_gain:.2f}  sibil {sibil_bias:.2f}"
        try:
            from PIL import ImageFont
            font = ImageFont.truetype("DejaVuSans.ttf", 28)
            font2= ImageFont.truetype("DejaVuSans.ttf", 20)
        except Exception:
            font = ImageFont.load_default(); font2 = ImageFont.load_default()
        drw.text((54, 60), title, fill=(230,236,247), font=font)
        drw.text((54, 98), sub,   fill=(158,170,187), font=font2)
        drw.text((54, 126), sub2, fill=(158,170,187), font=font2)

        excerpt = textwrap.shorten(prompt.replace("\n"," "), width=120, placeholder="…")
        drw.text((54, 156), excerpt, fill=(170,184,205), font=font2)

        img.save(str(png_path), "PNG", optimize=True)
        return True
    except Exception:
        try:
            cmd = [
                "convert","-size","1024x1536","gradient:#0e1018-#1a2030",
                "-gravity","northwest",
                "-fill","#e9eef7","-pointsize","28","-annotate","+54+60","Mira — Autonomous Embodiment (learned)",
                "-fill","#9aa6bd","-pointsize","20","-annotate","+54+98", f"{DATE} {UTC.strftime('%H')}:00Z  |  {label}",
                str(png_path)
            ]
            subprocess.run(cmd, check=True)
            return True
        except Exception:
            return False

_ = try_make_placeholder(out_png, exposure, contrast)

# Update latest.png
latest_img = D_ARCH / "latest.png"
try:
    if latest_img.exists() or latest_img.is_symlink():
        latest_img.unlink()
    latest_img.symlink_to(out_png.name)
except Exception:
    try:
        import shutil
        shutil.copyfile(out_png, latest_img)
    except Exception:
        pass

# ---------- Persist contract latest ----------
latest_contract = D_PROMPT / "latest.json"
try:
    if latest_contract.exists() or latest_contract.is_symlink():
        latest_contract.unlink()
    latest_contract.symlink_to((D_PROMPT / f"{STAMP_H}.json").name)
except Exception:
    with open(latest_contract, "w", encoding="utf-8") as f:
        json.dump(params, f, ensure_ascii=False, indent=2)

# ---------- Ledger note ----------
with open(D_LEDGER / "events.jsonl", "a", encoding="utf-8") as f:
    f.write(json.dumps({
        "ts": TS,
        "type": "self_image",
        "label": label,
        "valence": round(val,3),
        "arousal": round(aro,3),
        "stability": round(stab,3),
        "learning": {
            "viseme_mouth_gain": round(mouth_gain,4),
            "sibilant_bias": round(sibil_bias,4),
            "exposure_affect_gain": round(expo_gain,4),
            "contrast_affect_gain": round(contr_gain,4)
        },
        "contract": f"data/render_prompts/{STAMP_H}.json",
        "image": f"data/archive/self/{STAMP_H}.png",
        "seed": seed
    }, ensure_ascii=False) + "\n")

# ---------- Health touch (nur TS) ----------
health = jload(D_BADGE / "health.json", {"status":"OK","ts":TS})
health["ts"] = TS
with open(D_BADGE / "health.json", "w", encoding="utf-8") as f:
    json.dump(health, f, ensure_ascii=False)

# ---------- Stdout ----------
print(json.dumps({
    "ok": True,
    "ts": TS,
    "contract": f"data/render_prompts/{STAMP_H}.json",
    "image": f"data/archive/self/{STAMP_H}.png",
    "latest_image": "data/archive/self/latest.png",
    "label": label,
    "valence": round(val,3),
    "arousal": round(aro,3),
    "stability": round(stab,3),
    "learning_used": {
        "mouth_gain": round(mouth_gain,3),
        "sibilant_bias": round(sibil_bias,3),
        "exposure_gain": round(expo_gain,3),
        "contrast_gain": round(contr_gain,3)
    }
}, ensure_ascii=False, indent=2))
