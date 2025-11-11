#!/usr/bin/env python3
import json, os

IN  = "badges/health.json"
OUT = "badges/health.svg"

palette = {
  "OK":       ("#2e7d32", "#e8f5e9"),
  "HEALING":  ("#f9a825", "#fff8e1"),
  "DEGRADED": ("#c62828", "#ffebee"),
}
label = "health"

def svg(label, status, fg, bg):
    font_w = 7.0
    pad = 10
    l_w = int(len(label)  * font_w + 2*pad)
    s_w = int(len(status) * font_w + 2*pad)
    w = l_w + s_w
    h = 20
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" role="img" aria-label="{label}: {status}">
  <linearGradient id="g" x2="0" y2="100%"><stop offset="0%" stop-color="#fff" stop-opacity=".7"/><stop offset="100%" stop-opacity=".7"/></linearGradient>
  <mask id="r"><rect width="{w}" height="{h}" rx="3" fill="#fff"/></mask>
  <g mask="url(#r)">
    <rect width="{l_w}" height="{h}" fill="#555"/>
    <rect x="{l_w}" width="{s_w}" height="{h}" fill="{fg}"/>
    <rect width="{w}" height="{h}" fill="url(#g)"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11">
    <text x="{l_w/2}" y="14">{label}</text>
  </g>
  <g fill="#000" opacity="0.85" text-anchor="middle" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11">
    <text x="{l_w + s_w/2}" y="14">{status}</text>
  </g>
</svg>'''

def main():
    try:
        data = json.load(open(IN, "r", encoding="utf-8"))
        status = str(data.get("status", "DEGRADED")).upper()
    except Exception:
        status = "DEGRADED"
    fg, bg = palette.get(status, palette["DEGRADED"])
    os.makedirs("badges", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(svg(label, status, fg, bg))

if __name__ == "__main__":
    main()
