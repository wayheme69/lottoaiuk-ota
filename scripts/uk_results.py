#!/usr/bin/env python3
# uk_results.py — flux de la v5 de LOTTO AI UK (07/10/2026) : uk_results.json
#
#   lotto        : 30 derniers tirages « deux rounds » (depuis le 10/06/2026), les deux
#                  séries de chaque soir + les gains réels par rang.
#   euromillions : 30 derniers tirages + gains UK par gagnant (en £), rang par rang.
#
# Sources :
#   - national-lottery.co.uk (OFFICIEL, XML) : dernier tirage de chaque jeu, avec le
#     nombre de gagnants et les montants UK.
#   - beatlottery.co.uk (Lotto, historique des deux rounds)  — via update_uklotto.py
#   - euromillions.api.pedromealha.dev (EuroMillions, numéros)
#   - euro-millions.com/results/DD-MM-YYYY (EuroMillions, tableau UK « Prize Per Winner »)
#
# Rien ne peut faire échouer le run sauf un flux périmé (> 6 j) : chaque source est
# optionnelle et on fusionne avec le fichier déjà publié (les gains déjà connus restent).
# Le flux de la v4 (uklotto_recent.json, update_uklotto.py) n'est PAS touché.
import datetime, email.utils, json, os, re, sys, time, urllib.request

sys.path.insert(0, os.path.dirname(__file__))
from update_uklotto import _get, fetch_beatlottery, fetch_official as fetch_lotto_official_balls

FEED = "uk_results.json"
KEEP = 30
MAX_STALE_DAYS = 6
TWO_ROUNDS_FROM = "2026-06-10"
# Gains fixes du Lotto depuis le 10/06/2026 (par round) ; le jackpot (6) est partagé
LOTTO_FIXED = {"5+B": 1000000.0, "5": 1000.0, "4": 50.0, "3": 10.0, "2": 1.0}
LOTTO_LEVELS = ["6", "5+B", "5", "4", "3", "2"]
EM_LEVELS = ["5+2", "5+1", "5+0", "4+2", "4+1", "3+2", "4+0", "2+2", "3+1", "3+0", "1+2", "2+1", "2+0"]


def log(*a):
    print(*a, flush=True)


def attempt(label, fn, tries=2, pause=6):
    for i in range(tries):
        try:
            return fn()
        except Exception as e:
            log(f"  [KO] {label}: {str(e)[:100]} (tentative {i + 1})")
            if i < tries - 1:
                time.sleep(pause)
    return None


def tiers(xml, country=None):
    """{level: (winners, total £)} d'un bloc <prize-tiers>."""
    if country:
        m = re.search(rf'<prize-tiers country="{country}">(.*?)</prize-tiers>', xml, re.S)
    else:
        m = re.search(r"<prize-tiers>(.*?)</prize-tiers>", xml, re.S)
    if not m:
        return {}
    out = {}
    for lvl, body in re.findall(r'<prize-tier level="(\d+)">(.*?)</prize-tier>', m.group(1), re.S):
        w = re.search(r"<number-of-winners>(\d+)</number-of-winners>", body)
        v = re.search(r"<win-value>([\d.]+)</win-value>", body)
        if w:
            out[int(lvl)] = (int(w.group(1)), float(v.group(1)) if v else None)
    return out


# ------------------------------- Lotto -------------------------------
def lotto_official():
    xml = _get("https://www.national-lottery.co.uk/results/lotto/draw-history/csv")
    d = re.search(r"<draw-date>(\d{4}-\d{2}-\d{2})</draw-date>", xml).group(1)
    if "<confirmed>Y</confirmed>" not in xml:
        return d, None, None
    t = tiers(xml)
    payouts, winners = {}, {}
    for i, key in enumerate(LOTTO_LEVELS):
        a, b = t.get(i + 1), t.get(i + 7)          # round 1 = niveaux 1-6, round 2 = 7-12
        if not a or not b:
            continue
        n = a[0] + b[0]
        winners[key] = n
        if n > 0 and (a[1] or 0) + (b[1] or 0) > 0:
            payouts[key] = round(((a[1] or 0) + (b[1] or 0)) / n, 2)
    return d, payouts, winners


def build_lotto(prev):
    rounds = {}
    for r in (attempt("beatlottery", fetch_beatlottery) or []) + (attempt("lotto officiel", fetch_lotto_official_balls) or []):
        if r.get("round") in (1, 2) and r["date"] >= TWO_ROUNDS_FROM:
            rounds.setdefault(r["date"], {})[r["round"]] = {"numbers": sorted(r["main"]), "bonus": r["bonus"]}
    for p in prev:                                   # l'historique publié comble les trous
        for i, rd in enumerate(p.get("rounds", []), start=1):
            rounds.setdefault(p["date"], {}).setdefault(i, rd)
    off = attempt("lotto gains officiels", lotto_official)
    prev_by = {p["date"]: p for p in prev}
    out = []
    for d in sorted(rounds, reverse=True)[:KEEP]:
        rr = rounds[d]
        if 1 not in rr or 2 not in rr:
            continue
        pay = dict(LOTTO_FIXED)
        old = prev_by.get(d, {})
        pay.update({k: v for k, v in (old.get("payouts") or {}).items() if v is not None})
        winners = old.get("winners")
        if off and off[0] == d and off[1] is not None:
            pay.update(off[1]); winners = off[2]
        out.append({"date": d, "rounds": [rr[1], rr[2]], "payouts": pay, "winners": winners})
    return out


# ---------------------------- EuroMillions ----------------------------
def em_numbers():
    out = {}
    y = datetime.date.today().year
    for year in (y - 1, y):
        data = json.loads(_get(f"https://euromillions.api.pedromealha.dev/draws?year={year}"))
        for d in data:
            day = email.utils.parsedate_to_datetime(d["date"]).date().isoformat()   # « Fri, 02 Jan 2026 00:00:00 GMT »
            nums = sorted(int(x) for x in d["numbers"]); stars = sorted(int(x) for x in d["stars"])
            if len(set(nums)) == 5 and all(1 <= n <= 50 for n in nums) and len(set(stars)) == 2 and all(1 <= s <= 12 for s in stars):
                out[day] = {"numbers": nums, "stars": stars}
    return out


def em_history_page():
    """Secours : euro-millions.com/results-history-YYYY (numéros seulement)."""
    out = {}
    y = datetime.date.today().year
    for year in (y, y - 1):
        html = _get(f"https://www.euro-millions.com/results-history-{year}")
        for dd, body in re.findall(r'<a href="/results/(\d{2}-\d{2}-\d{4})"[^>]*>.*?</a>\s*</td>(.*?)</ul>', html, re.S):
            nums = sorted(int(x) for x in re.findall(r'resultBall ball small">(\d+)<', body))
            stars = sorted(int(x) for x in re.findall(r'resultBall lucky-star small">(\d+)<', body))
            if len(set(nums)) == 5 and all(1 <= n <= 50 for n in nums) and len(set(stars)) == 2 and all(1 <= s <= 12 for s in stars):
                day = datetime.datetime.strptime(dd, "%d-%m-%Y").date().isoformat()
                out[day] = {"numbers": nums, "stars": stars}
    return out


def em_official():
    xml = _get("https://www.national-lottery.co.uk/results/euromillions/draw-history/csv")
    d = re.search(r"<draw-date>(\d{4}-\d{2}-\d{2})</draw-date>", xml).group(1)
    blk = re.search(r"<balls>(.*?)</balls>", xml, re.S).group(1)
    nums = sorted(int(x) for x in re.findall(r'<ball number="\d+">(\d+)</ball>', blk))
    stars = sorted(int(x) for x in re.findall(r'<bonus-ball type="luckystar"[^>]*>(\d+)</bonus-ball>', blk))
    pay, win = {}, {}
    if "<confirmed>Y</confirmed>" in xml:
        for lvl, (n, total) in tiers(xml, "UK").items():
            if 1 <= lvl <= len(EM_LEVELS):
                win[EM_LEVELS[lvl - 1]] = n
                if n > 0 and total:
                    pay[EM_LEVELS[lvl - 1]] = round(total / n, 2)
    return d, {"numbers": nums, "stars": stars}, pay, win


def em_page(day):
    """Tableau UK de euro-millions.com : {rang: £ par gagnant}, {rang: gagnants UK}."""
    dd = datetime.date.fromisoformat(day)
    html = _get(f"https://www.euro-millions.com/results/{dd:%d-%m-%Y}")
    t = re.sub(r"<script.*?</script>|<style.*?</style>", "", html, flags=re.S)
    t = re.sub(r"<[^>]+>", " ", t).replace("&pound;", "£")
    t = re.sub(r"\s+", " ", t)
    i = t.find("UK Winners")
    if i < 0:
        return {}, {}
    j = t.find("Totals", i)
    seg = t[i:j]
    pay, win = {}, {}
    for a, b, prize, n in re.findall(r"(\d) (?:\+ (\d) )?£([\d,]+\.\d\d) ([\d,]+) £", seg):
        k = f"{a}+{b or 0}"
        if k in EM_LEVELS:
            win[k] = int(n.replace(",", ""))
            v = float(prize.replace(",", ""))
            # Jackpot non gagné : la page affiche le montant remis en jeu, pas un gain
            if v > 0 and not (k == "5+2" and win[k] == 0):
                pay[k] = v
    return pay, win


def build_em(prev):
    draws = attempt("pedromealha", em_numbers, tries=4, pause=20) or {}
    hist = attempt("euro-millions.com historique", em_history_page) or {}
    for d, v in hist.items():
        if d in draws and draws[d] != v:
            log(f"  [!] désaccord EuroMillions le {d} : {draws[d]} vs {v} — tirage ignoré")
            draws.pop(d)
        else:
            draws.setdefault(d, v)
    for p in prev:
        draws.setdefault(p["date"], {"numbers": p["numbers"], "stars": p["stars"]})
    off = attempt("euromillions officiel", em_official)
    if off:
        draws[off[0]] = off[1]
    prev_by = {p["date"]: p for p in prev}
    out = []
    for d in sorted(draws, reverse=True)[:KEEP]:
        old = prev_by.get(d, {})
        pay, win = dict(old.get("payouts") or {}), old.get("winners")
        if off and off[0] == d and off[2]:
            pay.update(off[2]); win = off[3]
        if len(pay) < 10:                            # gains UK manquants → page du tirage
            got = attempt(f"euro-millions.com {d}", lambda d=d: em_page(d), tries=1)
            if got and got[0]:
                for k, v in got[0].items():
                    pay.setdefault(k, v)
                win = win or got[1]
            time.sleep(1)
        out.append({"date": d, **draws[d], "payouts": pay or None, "winners": win})
    return out


def main():
    prev = {}
    if os.path.exists(FEED):
        try:
            prev = json.load(open(FEED))
        except Exception as e:
            log("flux existant illisible:", e)
    lotto = build_lotto(prev.get("lotto", []))
    em = build_em(prev.get("euromillions", []))
    if not lotto or not em:
        log("FAIL: un des deux jeux est vide"); sys.exit(1)
    for name, lst in (("lotto", lotto), ("euromillions", em)):
        age = (datetime.date.today() - datetime.date.fromisoformat(lst[0]["date"])).days
        log(f"{name}: {len(lst)} tirages, dernier {lst[0]['date']} ({age} j)")
        if age > MAX_STALE_DAYS:
            log(f"FAIL: {name} périmé"); sys.exit(1)
    new = {"lotto": lotto, "euromillions": em}
    if new == {k: prev.get(k) for k in new}:
        log("Aucune nouvelle donnée."); return
    json.dump({"updated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%MZ"), **new},
              open(FEED, "w"), indent=1)
    log("OK")


if __name__ == "__main__":
    main()
