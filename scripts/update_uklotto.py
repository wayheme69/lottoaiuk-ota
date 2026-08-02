#!/usr/bin/env python3
# Met a jour uklotto_recent.json avec les derniers tirages UK Lotto.
#
# 26/07/2026 : reecriture « Double Your Luck » (2 rounds/tirage depuis le 10/06/2026),
#              echec BRUYANT (exit 1) quand le flux est perime.
# 30/07/2026 : ajout du repli r.jina.ai (lottery.co.uk timeoutait depuis les runners).
# 02/08/2026 : lottery.co.uk est tombee POUR DE BON (521/522 Cloudflare = origine HS),
#              le tirage du 01/08 n'a jamais ete recupere. On ne depend plus d'un seul
#              site : 3 sources independantes, fusionnees avec l'historique deja publie.
#
#   1. national-lottery.co.uk  — source OFFICIELLE, XML, dernier tirage uniquement.
#   2. beatlottery.co.uk       — historique complet en HTML.
#   3. lottery.co.uk           — l'ancienne source, gardee si elle revient.
#
# Chaque source est optionnelle : on agrege tout ce qui repond, on fusionne avec le
# fichier existant, et on echoue bruyamment seulement si le resultat reste perime.
import re, json, os, sys, time, datetime, urllib.request

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
      "(KHTML, like Gecko) Version/17.4 Safari/605.1.15")
FEED = "uklotto_recent.json"
KEEP = 14
MAX_STALE_DAYS = 6

# Le jeu 6/59 actuel : garde-fou de validation.
def valid(mains, bonus):
    return (len(mains) == 6 and len(set(mains)) == 6
            and all(1 <= n <= 59 for n in mains) and 1 <= bonus <= 59)


def _get(url, headers=None, timeout=45):
    req = urllib.request.Request(url, headers=headers or {"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def _try(label, fn, attempts=2, pause=8):
    """Execute une source, ne leve jamais : renvoie [] si elle est indisponible."""
    for i in range(attempts):
        try:
            recs = fn()
            good = [r for r in recs if valid(r["main"], r["bonus"])]
            if good:
                print(f"  [OK]   {label}: {len(good)} tirage(s)")
                return good
            print(f"  [VIDE] {label}: 0 tirage exploitable (tentative {i+1})")
        except Exception as e:
            print(f"  [KO]   {label}: {str(e)[:90]} (tentative {i+1})")
        if i < attempts - 1:
            time.sleep(pause)
    return []


# --------------------------------------------------------------------------
# Source 1 — national-lottery.co.uk (OFFICIELLE). Renvoie du XML : le dernier
# tirage, avec un bloc <balls> par round.
# --------------------------------------------------------------------------
def fetch_official():
    xml = _get("https://www.national-lottery.co.uk/results/lotto/draw-history/csv")
    m = re.search(r"<draw-date>(\d{4}-\d{2}-\d{2})</draw-date>", xml)
    if not m:
        return []
    date = m.group(1)
    out = []
    for rnd, block in enumerate(re.findall(r"<balls>(.*?)</balls>", xml, re.S), start=1):
        mains = [int(x) for x in re.findall(r'<ball number="\d+">(\d+)</ball>', block)]
        bonus = re.findall(r"<bonus-ball[^>]*>(\d+)</bonus-ball>", block)
        if len(mains) == 6 and bonus:
            out.append({"date": date, "main": sorted(mains),
                        "bonus": int(bonus[0]), "jackpot": None, "round": rnd})
    # Avant « Double Your Luck » il n'y avait qu'un tirage : round 0, comme l'historique.
    if len(out) == 1:
        out[0]["round"] = 0
    return out


# --------------------------------------------------------------------------
# Source 2 — beatlottery.co.uk. Historique complet. Chaque ligne commence par une
# cellule DD/MM/YYYY en rowspan=2, puis « Round 1 » et « Round 2 ».
# --------------------------------------------------------------------------
def fetch_beatlottery():
    html = _get("https://www.beatlottery.co.uk/lotto/draw-history", timeout=60)
    out = []
    chunks = re.split(r'rowspan="2">(\d{2}/\d{2}/\d{4})</td>', html)
    for i in range(1, len(chunks) - 1, 2):
        try:
            d = datetime.datetime.strptime(chunks[i], "%d/%m/%Y").date()
        except ValueError:
            continue
        body = chunks[i + 1]
        if "Round 1</div>" in body:
            for rnd in (1, 2):
                m = re.search(rf"Round {rnd}</div>(.*?)</td>", body, re.S)
                if not m:
                    continue
                blk = m.group(1)
                mains = [int(x) for x in re.findall(r'ball-lotto">(\d+)<', blk)][:6]
                bonus = re.findall(r'ball-bonus">(\d+)<', blk)
                if len(mains) == 6 and bonus:
                    out.append({"date": d.isoformat(), "main": sorted(mains),
                                "bonus": int(bonus[0]), "jackpot": None, "round": rnd})
        else:
            mains = [int(x) for x in re.findall(r'ball-lotto">(\d+)<', body)][:6]
            bonus = re.findall(r'ball-bonus">(\d+)<', body)
            if len(mains) == 6 and bonus:
                out.append({"date": d.isoformat(), "main": sorted(mains),
                            "bonus": int(bonus[0]), "jackpot": None, "round": 0})
    return out


# --------------------------------------------------------------------------
# Source 3 — lottery.co.uk (historique). HS depuis le 01/08/2026, gardee au cas ou.
# --------------------------------------------------------------------------
def fetch_lotterycouk():
    year = datetime.date.today().year
    url = f"https://www.lottery.co.uk/lotto/results/archive-{year}"
    html = ""
    for u, h in ((url, {"User-Agent": UA}),
                 (f"https://r.jina.ai/{url}", {"User-Agent": UA, "X-Return-Format": "html"})):
        try:
            t = _get(u, h, timeout=40)
            if t.count("/lotto/results-") >= 1 and "lotto-ball" in t:
                html = t
                break
        except Exception:
            continue
    if not html:
        raise RuntimeError("injoignable (origine HS depuis le 01/08)")
    out = []
    chunks = re.split(r'href="/lotto/results-(\d{2})-(\d{2})-(\d{4})"', html)
    for i in range(1, len(chunks) - 3, 4):
        dd, mm, yyyy, body = chunks[i], chunks[i + 1], chunks[i + 2], chunks[i + 3]
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
    existing = []
    if os.path.exists(FEED):
        try:
            existing = json.load(open(FEED))
            print(f"flux existant : {len(existing)} tirage(s), "
                  f"le plus recent {existing[0]['date'] if existing else '-'}")
        except Exception as e:
            print("flux existant illisible:", e)

    print("interrogation des sources :")
    fetched = []
    fetched += _try("national-lottery.co.uk (officiel)", fetch_official)
    fetched += _try("beatlottery.co.uk", fetch_beatlottery)
    fetched += _try("lottery.co.uk", fetch_lotterycouk, attempts=1)

    if not fetched:
        print("FAIL: aucune des 3 sources n'a repondu")
        sys.exit(1)

    # Fusion : les tirages frais l'emportent, l'historique publie comble les trous.
    merged = {}
    for r in existing + fetched:
        try:
            merged[(r["date"], r["round"])] = r
        except (KeyError, TypeError):
            continue
    records = sorted(merged.values(), key=lambda r: (r["date"], r["round"]), reverse=True)[:KEEP]

    if len(records) < 4:
        print(f"FAIL: seulement {len(records)} tirage(s) apres fusion")
        sys.exit(1)

    newest = datetime.date.fromisoformat(records[0]["date"])
    age = (datetime.date.today() - newest).days
    if age > MAX_STALE_DAYS:
        print(f"FAIL: le tirage le plus recent ({newest}) date de {age} jours")
        sys.exit(1)

    json.dump(records, open(FEED, "w"), indent=1)
    print(f"OK: {len(records)} tirages, le plus recent {newest} ({age} j)")


if __name__ == "__main__":
    main()
