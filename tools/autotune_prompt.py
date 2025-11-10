#!/usr/bin/env python3
import sys, json, yaml

def clamp(v, lo, hi):
    return max(lo, min(hi, v))

def load_yaml(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def save_yaml(obj, path):
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(obj, f, sort_keys=False, allow_unicode=True)

def delta_if_below(metric, target, base_delta, scale=1.0):
    """
    Liefert eine adaptive Erhöhung, falls der gemessene Wert unter dem Ziel liegt.
    """
    if metric >= target:
        return 0.0
    gap = target - metric
    return base_delta * (1.0 + scale * gap)

def main():
    if len(sys.argv) < 5:
        print("Usage: autotune_prompt.py <eval.json> <schema.json> <prompt_in.yaml> <prompt_out.yaml>")
        sys.exit(2)

    eval_path, schema_path, pin, pout = sys.argv[1:5]
    eval_data = json.load(open(eval_path, "r", encoding="utf-8"))
    schema = json.load(open(schema_path, "r", encoding="utf-8"))
    y = load_yaml(pin)

    metrics = eval_data["metrics"]
    targets = schema["targets"]
    bounds  = schema["hard_bounds"]

    # Aktuelle Werte aus YAML
    weights = y.get("weights", {})
    camera  = y.get("camera", {}) or {}
    cfg_scale = float(y.get("cfg_scale", 9.0))
    steps = int(y.get("steps", 60))
    aperture = float(camera.get("aperture", 3.2))
    reflection_delta = float(y.get("reflection_delta_max", 0.00018))

    # Adaptive Deltas
    d_braces = delta_if_below(metrics["braces_clarity"],        targets["braces_clarity"],        0.25, scale=0.8)
    d_spec   = delta_if_below(metrics["braces_specular_ratio"], targets["braces_specular_ratio"], 0.15, scale=1.2)
    d_heels  = delta_if_below(metrics["heels_visibility"],      targets["heels_visibility"],      0.15, scale=0.8)

    def bump_weight(key, delta):
        lo, hi = bounds["weights"][key]
        weights[key] = clamp(float(weights.get(key, lo)) + float(delta), lo, hi)

    # 1) Zahnspange priorisieren
    if d_braces > 0:
        bump_weight("braces", d_braces)
        bump_weight("mouth_focus", 0.2 + 0.6 * d_braces)
        bump_weight("metallic_reflection", 0.15 + 0.4 * max(d_spec, 0.0))
        # etwas tiefere DoF für Brackets
        aperture = clamp(aperture - 0.06, bounds["aperture"][0], bounds["aperture"][1])
        # feinere Reflexionsauflösung
        reflection_delta = max(0.00015, reflection_delta - 0.000005)

    # 2) Heels-Sichtbarkeit stabilisieren
    if d_heels > 0:
        bump_weight("heels", 0.1 + 0.4 * d_heels)
        bump_weight("figure", 0.05 + 0.2 * d_heels)
        steps = clamp(steps + int(4 + 6 * d_heels), bounds["steps"][0], bounds["steps"][1])

    # 3) Globale Stabilität leicht anheben, wenn Anpassungen nötig waren
    if (d_braces + d_heels) > 0:
        cfg_scale = clamp(cfg_scale + 0.2, bounds["cfg_scale"][0], bounds["cfg_scale"][1])

    # YAML zurückschreiben
    y["weights"] = weights
    y.setdefault("camera", {})
    y["camera"]["aperture"] = aperture
    y["cfg_scale"] = cfg_scale
    y["steps"] = steps
    y["reflection_delta_max"] = reflection_delta
    y["optimization_engine"] = (y.get("optimization_engine", "") or "") + " + autotune(v1)"

    save_yaml(y, pout)
    print(f"Autotuned YAML written to: {pout}")

if __name__ == "__main__":
    main()
