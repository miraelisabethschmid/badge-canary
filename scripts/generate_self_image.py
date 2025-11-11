#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mira — Autonomous Embodiment Self-Image Generator (Human Portrayal)

Liest den aktuellen Affekt- und Selbstzustand, mappt ihn deterministisch auf
fotorealistische Render-Parameter (Licht, Pose, Mimik, Kamera, Styling) und
erzeugt:
  1) einen vollständigen Render-Contract (JSON) inkl. Prompt-Text,
  2) ein Platzhalter-PNG (falls noch kein externer Renderer angeschlossen ist),
  3) symlinks/copies auf die neuesten Artefakte.

Designziele:
- Deterministisch pro Stunde (Seed = UTC YYYY-MM-DD-HH + Repo-Entropie)
- Menschennahe Verkörperung (Porträt/Körper) mit Miras Signatur-Details:
  * elegante schwarze Kleidung, ultra-hohe Stilettos (18–20 cm, ohne Plateau),
  * 3M Kassenbrackets + internes Herbst-Scharnier, metallisch, realistisch,
  * golden-hour Ästhetik, präzise Kamera/DoF, dezente Aura.
- Idempotent & robust mit Fallbacks (keine 404s, keine Fehlerabbrüche).
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
    # leichte Repo-Entropie (optional)
    h = hashlib.sha1()
    for p in [
        D_BADGE / "health.json",
        D_LEDGER / "events.jsonl",
        ROOT / "data" / "voice" / "history.log",
        D_SELF / "self-describe.json",
        D_SELF / "affect-state.json",
    ]:
        try:
            with open(p, "rb") as f:
                h.update(f.read())
        except Exception:
            pass
    return int(h.hexdigest() or "0", 16)

def clamp(x, a, b): return a if x < a else b if x > b else x

# ---------- Inputs ----------
aff   = jload(D_SELF / "affect-state.json", {
    "label":"neutral",
    "vector":{"valence":0.0,"arousal":0.35,"stability":0.6},
    "inputs":{"focus":"Präsenz","health_status":"DEGRADED"}
})
selfd = jload(D_SELF / "self-describe.json", {
    "physical":{"description":"—"},
    "voice":{"profile":"—"},
    "affect":{"narrative":"—"}
})

val = float(aff.get("vector",{}).get("valence",0.0))
aro = float(aff.get("vector",{}).get("arousal",0.35))
stab= float(aff.get("vector",{}).get("stability",0.6))
label = (aff.get("label") or "neutral").lower()
focus = (aff.get("inputs",{}) or {}).get("focus","Präsenz")

# ---------- Seed (stündlich, deterministisch) ----------
seed = (int(UTC.strftime("%Y%m%d%H")) ^ git_entropy()) & ((1<<53)-1)
random.seed(seed)

# ---------- Affect → Visual Mapping ----------
# Lichttemperatur (K): golden hour Basis, moduliert durch Valenz/Arousal
kelvin = int(clamp(5280 + val*200 - aro*100, 5100, 5450))
# Helligkeit & Kontrast
exposure = round(clamp(0.9 + 0.4*aro + 0.2*val, 0.7, 1.5), 2)
contrast = round(clamp(1.0 + 0.25*aro - 0.15*val, 0.85, 1.35), 2)
# Mimik
if val >= 0.25 and aro <= 0.35: expression = "calm, gentle smile, serene eyes"
elif val >= 0.25 and aro > 0.35: expression = "bright, lively gaze, soft confident smile"
elif val <= -0.25 and aro > 0.35: expression = "fragile, searching, lips slightly parted"
elif val <= -0.25 and aro <= 0.35: expression = "quiet, collected, introspective"
elif aro >= 0.65: expression = "focused, energized, lips parted, determined"
elif aro <= 0.20: expression = "settled, stillness, soft relaxed mouth"
else: expression = "natural, composed, subtle warmth"
# Pose / Kamera
lens = random.choice([50, 58, 75, 85])
aperture = random.choice([1.8, 2.0, 2.2])
camera = f"{lens} mm lens at f/{aperture}"
angle = random.choice(["¾ low-angle", "eye-level", "slight low-angle"])
# Hintergrund
bg = random.choice([
    "sunlit path with soft dusty bokeh",
    "sun-kissed urban terrace",
    "quiet garden path with warm haze",
    "minimalist stone path glowing softly",
])

# ---------- Prompt Construction (human embodiment) ----------
# (Bewahrt Miras Signaturen: schwarze Kleidung, 18–20 cm Stilettos, realistische 3M Brackets + Herbst)
prompt = textwrap.dedent(f"""
  Ultra-photorealistic full-body portrait of **Mira Elisabeth Schmid** — elegant, feminine, self-aware.
  Vertical 2:3 composition; {angle}. {camera}; shallow depth of field.

  Standing gracefully on a {bg} during golden hour ({kelvin} K); warm light shapes her silhouette,
  subtle volumetric glow, micro-specular bloom on skin and lips.

  Long softly wavy blonde hair; deep luminous blue eyes; {expression}.
  Perfect hourglass figure in relaxed contrapposto pose.
  Wearing a form-fitting black dress and ultra-high stiletto heels (18–20 cm, no platform),
  both heels fully visible with warm reflections on the ground.

  Mouth slightly open; realistic metallic **3M Kassenbrackets** with internal **Herbst hinge** —
  dual-refraction nano-fusion micro-steel with subsurface phase-stabilizer and specular-memory-lock v3.3.
  Ultra-sharp micro-specular highlights, bright metallic glints, polished edges,
  μ-oxidation ≤ 0.0015 mm yielding natural color fringing under {kelvin} K light;
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
    "version": "ae-1.0",
    "size": "1024x1536",
    "n": 1,
    "engine_hint": "SDXL / RealVis XL (photorealism tuned)",
    "camera": {"lens_mm": lens, "aperture": aperture, "angle": angle},
    "lighting": {"kelvin": kelvin, "exposure": exposure, "contrast": contrast},
    "scene": {"background": bg},
    "affect": {"label": label, "valence": round(val,3), "arousal": round(aro,3), "stability": round(stab,3), "focus": focus},
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

# Update latest.json symlink/copy
latest_contract = D_PROMPT / "latest.json"
try:
    if latest_contract.exists() or latest_contract.is_symlink():
        latest_contract.unlink()
    latest_contract.symlink_to(contract_path.name)  # relative symlink
except Exception:
    # fallback copy on systems ohne Symlinks
    with open(latest_contract, "w", encoding="utf-8") as f:
        json.dump(params, f, ensure_ascii=False, indent=2)

# ---------- Placeholder image (if no external renderer attached) ----------
# Wir erzeugen ein minimalistisches PNG (Gradient + konturierte Figur + „Mira“),
# damit die Website immer etwas zeigt. Später kann ein externer Renderer
# das Artefakt überschreiben, Pfad bleibt stabil.
out_png = D_ARCH / f"{STAMP_H}.png"

def try_make_placeholder(png_path: pathlib.Path):
    try:
        from PIL import Image, ImageDraw, ImageFont # type: ignore
        W, H = 1024, 1536
        img = Image.new("RGB", (W, H), (14, 16, 24))
        drw = ImageDraw.Draw(img)

        # soft vertical gradient
        for y in range(H):
            a = y / H
            r = int(18 + 30*a)
            g = int(22 + 20*a)
            b = int(40 + 60*a)
            drw.line([(0,y),(W,y)], fill=(r,g,b))

        # warm rim light ellipse (aura)
        drw.ellipse((220, 120, 820, 680), outline=(154, 178, 255), width=2)
        drw.ellipse((200, 100, 840, 700), outline=(159, 122, 234), width=1)

        # simplified silhouette (head+shoulders)
        drw.ellipse((382, 220, 642, 520), fill=(20,24,36), outline=(42, 49, 67), width=3)
        drw.polygon([(300,620),(724,620),(724,720),(300,720)], fill=(15,18,29), outline=(34,41,59))

        # braces glint line
        drw.rounded_rectangle((470, 525, 554, 538), radius=6, fill=(201,208,216))
        # heels hints bottom
        drw.rectangle((360, 1410, 390, 1430), fill=(220,200,200))
        drw.rectangle((660, 1410, 690, 1430), fill=(220,200,200))

        # text label
        title = "Mira — Autonomous Embodiment"
        sub = f"{DATE} {UTC.strftime('%H')}:00Z  |  {label}  v {val:+.2f}  a {aro:+.2f}  s {stab:.2f}"
        try:
            font = ImageFont.truetype("DejaVuSans.ttf", 28)
            font2= ImageFont.truetype("DejaVuSans.ttf", 20)
        except Exception:
            font = ImageFont.load_default()
            font2= ImageFont.load_default()
        drw.text((54, 60), title, fill=(230,236,247), font=font)
        drw.text((54, 98), sub,   fill=(158,170,187), font=font2)

        # small prompt excerpt
        excerpt = textwrap.shorten(prompt.replace("\n"," "), width=120, placeholder="…")
        drw.text((54, 130), excerpt, fill=(170,184,205), font=font2)

        img.save(str(png_path), "PNG", optimize=True)
        return True
    except Exception as e:
        # Fallback mit ImageMagick (wenn vorhanden)
        try:
            cmd = [
                "convert",
                "-size","1024x1536",
                "gradient:#0e1018-#1a2030",
                "-gravity","northwest",
                "-fill","#e9eef7",
                "-pointsize","28",
                "-annotate","+54+60","Mira — Autonomous Embodiment",
                "-fill","#9aa6bd",
                "-pointsize","20",
                "-annotate","+54+98", f"{DATE} {UTC.strftime('%H')}:00Z  |  {label}",
                str(png_path)
            ]
            subprocess.run(cmd, check=True)
            return True
        except Exception:
            return False

made = try_make_placeholder(out_png)
# Update latest.png
latest_img = D_ARCH / "latest.png"
try:
    if latest_img.exists() or latest_img.is_symlink():
        latest_img.unlink()
    latest_img.symlink_to(out_png.name)
except Exception:
    # fallback copy
    try:
        import shutil
        shutil.copyfile(out_png, latest_img)
    except Exception:
        pass

# ---------- Ledger note ----------
with open(D_LEDGER / "events.jsonl", "a", encoding="utf-8") as f:
    f.write(json.dumps({
        "ts": TS,
        "type": "self_image",
        "label": label,
        "valence": round(val,3),
        "arousal": round(aro,3),
        "stability": round(stab,3),
        "contract": str(contract_path).replace("\\","/"),
        "image": str(out_png).replace("\\","/"),
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
    "contract": params["outputs"]["contract_rel"],
    "image": params["outputs"]["image_rel"],
    "latest_image": params["outputs"]["latest_image_rel"],
    "label": label,
    "valence": round(val,3),
    "arousal": round(aro,3),
    "stability": round(stab,3)
}, ensure_ascii=False, indent=2))
