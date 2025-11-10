#!/usr/bin/env python3
import os, sys, json
import cv2
import numpy as np

def variance_of_laplacian(gray):
    return cv2.Laplacian(gray, cv2.CV_64F).var()

def specular_ratio(bgr, thresh=235):
    """
    Schätzt den Anteil sehr heller Pixel als Proxy für metallische Glints.
    Höherer Wert ⇒ stärkere metallische Highlights (z. B. Brackets).
    """
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    total = gray.size
    spec = (gray >= thresh).sum()
    return spec / float(total + 1e-9)

def heels_visibility_mask(bgr, band_ratio=0.18, edge_thresh1=60, edge_thresh2=140):
    """
    Misst Kanten- und Kontrastdichte im unteren Bildband als Proxy
    für „Heels sichtbar & reflektiert“.
    """
    h, w = bgr.shape[:2]
    band_h = int(h * band_ratio)
    band = bgr[h - band_h : h, :]
    edges = cv2.Canny(cv2.cvtColor(band, cv2.COLOR_BGR2GRAY), edge_thresh1, edge_thresh2)
    density = edges.mean() / 255.0
    blur = cv2.GaussianBlur(cv2.cvtColor(band, cv2.COLOR_BGR2GRAY), (5,5), 0)
    contrast = float(blur.std())
    score = 0.7 * density + 0.3 * (contrast / 64.0)
    return max(0.0, min(1.0, score))

def mouth_roi_guess(bgr):
    """
    Grobe, modellfreie Mund-ROI-Schätzung (zentraler Ober-Mittelbereich).
    Robust, ohne Face-Model.
    """
    h, w = bgr.shape[:2]
    x1 = int(0.35 * w); x2 = int(0.65 * w)
    y1 = int(0.35 * h); y2 = int(0.55 * h)
    return bgr[y1:y2, x1:x2].copy()

def braces_clarity_score(bgr):
    """
    Kombiniert Schärfe (Laplacian) + Spekular-Anteil in der Mund-ROI
    zu einem Klarheits-Score [0..1] für die Zahnspange.
    """
    roi = mouth_roi_guess(bgr)
    if roi.size == 0:
        return 0.0, 0.0
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    sharp = variance_of_laplacian(gray)
    spec  = specular_ratio(roi, thresh=240)
    # Heuristische Normalisierung
    sharp_norm = min(1.0, sharp / 220.0)
    spec_norm  = min(1.0, spec / 0.05)
    score = 0.7 * sharp_norm + 0.3 * spec_norm
    return score, sharp

def global_sharpness(bgr):
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    return variance_of_laplacian(gray)

def main():
    if len(sys.argv) < 3:
        print("Usage: eval_render.py <input_image> <schema.json>", file=sys.stderr)
        sys.exit(2)

    img_path = sys.argv[1]
    schema_path = sys.argv[2]

    bgr = cv2.imread(img_path)
    if bgr is None:
        print(json.dumps({"ok": False, "error": f"Cannot read image: {img_path}"}))
        sys.exit(1)

    with open(schema_path, "r") as f:
        schema = json.load(f)
    targets = schema["targets"]

    braces_score, mouth_sharp = braces_clarity_score(bgr)
    spec_ratio = specular_ratio(bgr)
    heels_score = heels_visibility_mask(bgr)
    sharp_all = global_sharpness(bgr)

    result = {
        "ok": True,
        "metrics": {
            "braces_clarity": round(braces_score, 4),
            "braces_specular_ratio": round(spec_ratio, 5),
            "heels_visibility": round(heels_score, 4),
            "global_sharpness": round(sharp_all, 2),
            "mouth_roi_sharpness": round(mouth_sharp, 2)
        },
        "targets": targets
    }
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
