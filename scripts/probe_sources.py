#!/usr/bin/env python3
"""Sonde v3 : structure complete de 2 tirages beatlottery. A supprimer."""
import urllib.request, re

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
      "(KHTML, like Gecko) Version/17.4 Safari/605.1.15")
req = urllib.request.Request("https://www.beatlottery.co.uk/lotto/draw-history",
                             headers={"User-Agent": UA})
html = urllib.request.urlopen(req, timeout=45).read().decode("utf-8", "replace")

i = html.find("draw_date/2026-08-01")
start = html.rfind("<tr", 0, max(0, i - 1200))
seg = html[start:i + 2600]
seg = re.sub(r"\s+", " ", seg)
print("=== STRUCTURE BRUTE (2 tirages) ===")
print(seg)

print("\n=== TEST DE PARSING ===")
# tokens dans l'ordre d'apparition : dates, marqueurs de round, boules
toks = re.findall(
    r'draw_date/(\d{4}-\d{2}-\d{2})'
    r'|Round (\d)</div>'
    r'|results_ball_new ball-(lotto|bonus)">(\d+)<', html)
print("30 premiers tokens :")
for t in toks[:30]:
    print("   ", t)
