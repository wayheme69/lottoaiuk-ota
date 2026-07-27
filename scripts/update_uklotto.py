#!/usr/bin/env python3
# Auto-updates uklotto_recent.json with the latest UK Lotto draws.
# 26/07/2026 rewrite: « Double Your Luck » (2 rounds/draw since 10 Jun 2026),
# direct lottery.co.uk fetch (desktop UA), LOUD failure (exit 1) when stale —
# the previous version exited 0 silently and the feed froze for 7 weeks.
import re, json, urllib.request, datetime, sys, time

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15"

def fetch(year):
    url = f"https://www.lottery.co.uk/lotto/results/archive-{year}"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for i in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                txt = r.read().decode("utf-8", "replace")
            if txt.count("/lotto/results-") >= 1 and "lotto-ball" in txt:
                return txt
        except Exception as e:
            print("fetch retry:", str(e)[:80])
        if i < 3:
            time.sleep(12 * (i + 1))
    return ""

def parse(html):
    out = []
    chunks = re.split(r'href="/lotto/results-(\d{2})-(\d{2})-(\d{4})"', html)
    for i in range(1, len(chunks) - 3, 4):
        dd, mm, yyyy, body = chunks[i], chunks[i+1], chunks[i+2], chunks[i+3]
        try:
            d = datetime.date(int(yyyy), int(mm), int(dd))
        except ValueError:
            continue
        if "lotto-ball-round-1" in body:
            for rnd in (1, 2):
                mains = [int(x) for x in re.findall(rf'lotto-ball-round-{rnd}[^"]*">(\d+)<', body)][:6]
                bonus = re.findall(rf'lotto-bonus-ball-round-{rnd}[^"]*">(\d+)<', body)
                if len(mains) == 6 and bonus:
                    out.append({"date": d.isoformat(), "main": sorted(mains),
                                "bonus": int(bonus[0]), "jackpot": None, "round": rnd})
        else:
            mains = [int(x) for x in re.findall(r'"result small lotto-ball">(\d+)<', body)][:6]
            bonus = re.findall(r'"result small lotto-bonus-ball">(\d+)<', body)
            if len(mains) == 6 and bonus:
                out.append({"date": d.isoformat(), "main": sorted(mains),
                            "bonus": int(bonus[0]), "jackpot": None, "round": 0})
    return out

def main():
    year = datetime.date.today().year
    records = parse(fetch(year))
    if len(records) < 14:
        records += parse(fetch(year - 1))
    records.sort(key=lambda r: (r["date"], r["round"]), reverse=True)
    records = records[:14]
    if len(records) < 4:
        print(f"FAIL: only {len(records)} records parsed"); sys.exit(1)
    newest = datetime.date.fromisoformat(records[0]["date"])
    if (datetime.date.today() - newest).days > 6:
        print(f"FAIL: newest record {newest} is stale"); sys.exit(1)
    json.dump(records, open("uklotto_recent.json", "w"), indent=1)
    print(f"OK: {len(records)} records, newest {newest}")

if __name__ == "__main__":
    main()
