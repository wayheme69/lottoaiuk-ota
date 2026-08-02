#!/usr/bin/env python3
"""Sonde temporaire : teste depuis le runner GitHub quelles sources UK Lotto
repondent et contiennent des tirages exploitables. A supprimer apres usage."""
import urllib.request, re, datetime, sys

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
      "(KHTML, like Gecko) Version/17.4 Safari/605.1.15")
YEAR = datetime.date.today().year
LC = f"https://www.lottery.co.uk/lotto/results/archive-{YEAR}"

CANDIDATES = [
    ("lottery.co.uk direct",        LC, {"User-Agent": UA}),
    ("lottery.co.uk via jina",      f"https://r.jina.ai/{LC}", {"User-Agent": UA, "X-Return-Format": "html"}),
    ("lottery.co.uk via allorigins", f"https://api.allorigins.win/raw?url={LC}", {"User-Agent": UA}),
    ("lottery.co.uk via codetabs",  f"https://api.codetabs.com/v1/proxy?quest={LC}", {"User-Agent": UA}),
    ("national-lottery CSV direct", "https://www.national-lottery.co.uk/results/lotto/draw-history/csv", {"User-Agent": UA}),
    ("national-lottery CSV jina",   "https://r.jina.ai/https://www.national-lottery.co.uk/results/lotto/draw-history/csv", {"User-Agent": UA, "X-Return-Format": "text"}),
    ("lottery.net",                 "https://www.lottery.net/uk/lotto/numbers", {"User-Agent": UA}),
    ("lottonumbers.com",            f"https://www.lottonumbers.com/uk-lotto/archive-{YEAR}", {"User-Agent": UA}),
    ("lotteryextreme.com",          "https://www.lotteryextreme.com/uk/lotto-results", {"User-Agent": UA}),
    ("beatlottery.co.uk",           "https://www.beatlottery.co.uk/lotto/draw-history", {"User-Agent": UA}),
]

def probe(name, url, headers):
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=45) as r:
            body = r.read().decode("utf-8", "replace")
            code = r.status
    except Exception as e:
        print(f"  {name:<32} ECHEC  {str(e)[:60]}")
        return
    # indices d'exploitabilite
    dates_iso  = len(re.findall(r"\d{4}-\d{2}-\d{2}", body))
    dates_slash= len(re.findall(r"\d{2}[-/]\d{2}[-/]\d{4}", body))
    balls_lc   = body.count("lotto-ball")
    rounds_lc  = body.count("lotto-ball-round-")
    # une date recente est-elle presente ?
    recent = []
    for d in (datetime.date.today() - datetime.timedelta(days=k) for k in range(0, 10)):
        for pat in (d.isoformat(), d.strftime("%d-%m-%Y"), d.strftime("%d/%m/%Y"),
                    d.strftime("%d %b %Y"), d.strftime("%-d %B %Y")):
            if pat in body:
                recent.append(pat); break
    print(f"  {name:<32} HTTP {code}  {len(body):>8} o  "
          f"dates={dates_iso}/{dates_slash}  balls={balls_lc} rounds={rounds_lc}  "
          f"recent={recent[:2] if recent else 'AUCUNE'}")

print(f"=== SONDE SOURCES UK LOTTO — {datetime.datetime.utcnow().isoformat()}Z ===")
print(f"    annee cible {YEAR}\n")
for c in CANDIDATES:
    probe(*c)
print("\n=== FIN SONDE ===")
