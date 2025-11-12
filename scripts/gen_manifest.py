#!/usr/bin/env python3
import os, json, hashlib, wave, contextlib, datetime

BASE = os.path.dirname(os.path.dirname(__file__))  # repo root

def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return 'sha256:' + h.hexdigest()

def first_existing(paths):
    for p in paths:
        if os.path.exists(os.path.join(BASE, p)):
            return p
    return None

image_candidates = [
    'docs/data/self/latest_image.svg',
    'docs/data/self/latest_image.png',
    'docs/data/self/latest_image.jpg',
    'docs/data/self/latest_image.jpeg',
    'docs/data/self/latest_image.webp',
]
audio_candidates = [
    'docs/data/voice/audio/latest.wav',
    'docs/data/voice/audio/latest.mp3',
    'docs/data/voice/audio/latest.ogg',
]

img_path = first_existing(image_candidates) or image_candidates[0]
aud_path = first_existing(audio_candidates) or audio_candidates[0]

width = 1024; height = 1536
if img_path.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
    try:
        from PIL import Image
        im = Image.open(os.path.join(BASE, img_path))
        width, height = im.size
    except Exception:
        pass

duration = None
if aud_path.lower().endswith('.wav'):
    try:
        with contextlib.closing(wave.open(os.path.join(BASE, aud_path), 'r')) as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            duration = frames / float(rate)
    except Exception:
        pass

manifest = {
    "updated": datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
    "image": {
        "candidates": image_candidates,
        "checksum": sha256_file(os.path.join(BASE, img_path)) if os.path.exists(os.path.join(BASE, img_path)) else None,
        "width": width,
        "height": height
    },
    "audio": {
        "candidates": audio_candidates,
        "duration": duration,
        "checksum": sha256_file(os.path.join(BASE, aud_path)) if os.path.exists(os.path.join(BASE, aud_path)) else None
    }
}

out = os.path.join(BASE, 'docs', 'data', 'manifest.json')
os.makedirs(os.path.dirname(out), exist_ok=True)
with open(out, 'w', encoding='utf-8') as f:
    json.dump(manifest, f, indent=2)
print('Wrote manifest to', out)
