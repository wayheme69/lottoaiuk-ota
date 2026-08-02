#!/usr/bin/env python3
"""Sonde v2 : dump du format exact des 2 sources qui repondent. A supprimer."""
import urllib.request, re, datetime

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
      "(KHTML, like Gecko) Version/17.4 Safari/605.1.15")

def get(url, headers=None, timeout=45):
    req = urllib.request.Request(url, headers=headers or {"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")

print("=" * 78)
print("A) NATIONAL-LOTTERY.CO.UK — CSV OFFICIEL (dump integral)")
print("=" * 78)
try:
    csv = get("https://www.national-lottery.co.uk/results/lotto/draw-history/csv")
    print(csv)
except Exception as e:
    print("ECHEC:", e)

print()
print("=" * 78)
print("B) BEATLOTTERY.CO.UK — extrait autour des tirages recents")
print("=" * 78)
try:
    html = get("https://www.beatlottery.co.uk/lotto/draw-history")
    for target in ("2026-08-01", "2026-07-29"):
        i = html.find(target)
        print(f"\n--- contexte autour de {target} (index {i}) ---")
        if i >= 0:
            seg = html[max(0, i - 700):i + 700]
            seg = re.sub(r"\s+", " ", seg)
            print(seg)
except Exception as e:
    print("ECHEC:", e)
print("\n=== FIN SONDE v2 ===")
