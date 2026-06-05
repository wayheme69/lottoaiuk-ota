#!/usr/bin/env python3
# Auto-updates uklotto_recent.json with the latest UK Lotto draws.
# Runs on GitHub's servers (not the user's ISP) so the official source is reachable.
import re, json, urllib.request, datetime, sys, time
def fetch(year):
    url = f"https://r.jina.ai/https://www.lottery.co.uk/lotto/results/archive-{year}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    for _ in range(4):
        try:
            with urllib.request.urlopen(req, timeout=80) as r:
                txt = r.read().decode("utf-8", "replace")
            if len(re.findall(r"results-\d{2}-\d{2}-\d{4}", txt)) >= 10:
                return txt
        except Exception as e:
            print("fetch retry:", str(e)[:60])
        time.sleep(15)
    return ""
def parse(txt, draws, seen):
    for line in txt.splitlines():
        m = re.search(r"results-(\d{2})-(\d{2})-(\d{4})", line)
        if not m: continue
        dd, mm, yyyy = map(int, m.groups())
        try: d = datetime.date(yyyy, mm, dd)
        except: continue
        if d in seen: continue
        nums = None
        for c in (x.strip() for x in line.split("|")):
            cm = re.match(r"^(\d{1,2}(?:\s+\d{1,2}){6})(?:\s|$)", c)
            if cm:
                vals = [int(t) for t in cm.group(1).split()]
                if all(1 <= v <= 59 for v in vals) and len(set(vals)) == 7:
                    nums = vals; break
        if nums is None: continue
        jm = re.search(r"£([\d,]+)", line)
        seen.add(d)
        draws.append((d, sorted(nums[:6]), nums[6], ("£" + jm.group(1)) if jm else None))
y = datetime.date.today().year
draws, seen = [], set()
for yr in (y, y - 1):
    parse(fetch(yr), draws, seen)
draws = [x for x in draws if x[0] >= datetime.date(2015, 10, 10)]
draws.sort(key=lambda x: x[0], reverse=True)
if len(draws) < 5:
    print("Too few draws parsed — keeping existing file."); sys.exit(0)
out = [{"date": d.isoformat(), "main": mn, "bonus": bn, "jackpot": jp} for d, mn, bn, jp in draws[:30]]
json.dump(out, open("uklotto_recent.json", "w"), indent=1)
print(f"Wrote {len(out)} draws; latest {out[0]['date']}")
