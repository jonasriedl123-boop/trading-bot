#!/usr/bin/env python3
"""
Rueckblick-Test (Backtest): laesst die Bot-Regeln ueber die letzten Jahre Bitcoin laufen.
Nur Regeln (die KI-Ampel kann man nicht rueckwirkend testen). Schreibt BACKTEST.md.

  python3 backtest.py            -> ab 2023-01-01
  python3 backtest.py 2021-01-01 -> ab Datum

Vereinfachungen (steht auch im Bericht):
  - Einstieg zum Schluss der Signal-Kerze, Ausstieg an Stop/Ziel/Zeitstop (4h-Kerzen).
    Beruehrt eine Kerze Stop UND Ziel, zaehlt der Stop (vorsichtig).
  - S1 (BITI) wird als Wette auf fallendes BTC gerechnet, ohne BITI-Kosten. Einstieg nur zu US-Boersenzeiten
    (wartet wie im Bot bis 20 Std.). US-Feiertage werden ignoriert.
  - Gebuehr Bitcoin 0,25 % pro Seite, Lueckten unter den Stop werden zum Eroeffnungskurs gefuellt.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import bot
import rechner
from rechner import zeit

try:
    from zoneinfo import ZoneInfo
    NY = ZoneInfo("America/New_York")
except Exception:
    NY = timezone(timedelta(hours=-5))

HIER = Path(__file__).resolve().parent
START_KAPITAL = 500.0


def boerse_offen(t):
    n = t.astimezone(NY)
    m = n.hour * 60 + n.minute
    return n.weekday() < 5 and 9 * 60 + 30 <= m <= 15 * 60 + 45


def simuliere(tage, h4, p, start):
    tage = sorted(tage, key=lambda k: k["t"])
    h4 = sorted(h4, key=lambda k: k["t"])
    equity, hoch, max_dd = START_KAPITAL, START_KAPITAL, 0.0
    trades, pos, wartet = [], None, None
    abkuehlen = pause = datetime.min.replace(tzinfo=timezone.utc)
    serie, einstiege = 0, {}
    di = 0
    for i in range(80, len(h4)):
        bar = h4[i]
        zu = bar["t"] + timedelta(hours=4)  # Schluss dieser Kerze = "jetzt"
        if zu < start:
            continue
        # --- offene Position mit dieser Kerze pruefen ---
        if pos and bar["t"] >= pos["ab"]:
            pos["n"] += 1
            e, s, z = pos["e"], pos["s"], pos["z"]
            ende = None
            if pos["kurz"]:
                if bar["h"] >= s:
                    ende = (max(s, bar["o"]), "Stop")
                elif bar["l"] <= z:
                    ende = (z, "Ziel")
            else:
                if bar["l"] <= s:
                    ende = (min(s, bar["o"]), "Stop")
                elif bar["h"] >= z:
                    ende = (z, "Ziel")
            if not ende and pos["n"] >= int(p["zeitstop_kerzen"]):
                ende = (bar["c"], "Zeitstop")
            if ende:
                x, grund = ende
                risiko = abs(e - s)
                gebuehr = 0.0 if pos["kurz"] else p["gebuehr_pro_seite"]
                r = ((e - x) if pos["kurz"] else (x - e)) / risiko - 2 * gebuehr * e / risiko
                equity += r * pos["risiko_usd"]
                hoch = max(hoch, equity)
                max_dd = max(max_dd, 1 - equity / hoch)
                trades.append({"setup": pos["setup"], "zeit": pos["zeit"], "ende": zu, "r": r, "grund": grund,
                               "regime": pos["regime"]})
                pos = None
                if r <= 0:
                    serie += 1
                    abkuehlen = zu + timedelta(hours=float(p.get("nach_verlust_pause_std", 12)))
                    if serie >= rechner.HART["verlustserie_pause"]:
                        pause, serie = zu + timedelta(hours=24), 0
                else:
                    serie = 0
        if pos:
            continue
        # --- Signale ---
        while di < len(tage) and tage[di]["t"] + timedelta(days=1) <= zu:
            di += 1
        a = rechner.analyse(tage[max(0, di - 70):di], h4[i - 79:i + 1], zu, p, equity, equity, bar["c"])
        preis, atr = bar["c"], a.get("atr") or 0
        kandidat = None
        if wartet:
            if zu > wartet["bis"]:
                wartet = None
            elif boerse_offen(zu):
                dist = wartet["stop"] - preis
                ok, _ = rechner.stop_ok(dist, preis, atr, p)
                if ok and preis <= wartet["preis"] + 0.25 * atr:
                    kandidat = {"setup": "S1", "stop": wartet["stop"], "kurz": True, "risiko": wartet["risiko"]}
                wartet = None
        if a["aktion"] == "KAUFEN":
            s1 = a["setup"] == "S1"
            risiko = a.get("risiko_anteil") if s1 else p[f"{a['setup']}_risiko"]
            if s1 and not boerse_offen(zu):
                wartet = {"stop": a["stop"], "preis": preis, "risiko": risiko, "bis": zu + timedelta(hours=20)}
                kandidat = None
            else:
                kandidat, wartet = {"setup": a["setup"], "stop": a["stop"], "kurz": s1, "risiko": risiko}, None
        if not kandidat:
            continue
        tag = zu.date()
        if zu < abkuehlen or zu < pause or einstiege.get(tag, 0) >= rechner.HART["max_einstiege_tag"]:
            continue
        dist = abs(preis - kandidat["stop"])
        risiko_usd = min(equity * kandidat["risiko"], equity * p["max_cash_anteil"] * dist / preis)
        z = preis - p["ziel_r"] * dist if kandidat["kurz"] else preis + p["ziel_r"] * dist
        pos = {"setup": kandidat["setup"], "e": preis, "s": kandidat["stop"], "z": z, "kurz": kandidat["kurz"],
               "ab": zu, "n": 0, "risiko_usd": risiko_usd, "zeit": zu, "regime": a.get("regime", "?")}
        einstiege[tag] = einstiege.get(tag, 0) + 1
    return trades, equity, max_dd


def kennzahlen(rr):
    if not rr:
        return "0 Trades"
    g = [x for x in rr if x > 0]
    v = abs(sum(x for x in rr if x <= 0))
    pf = sum(g) / v if v else 99.0
    return (f"{len(rr)} Trades · Treffer {len(g) / len(rr):.0%} · Schnitt {sum(rr) / len(rr):+.2f}R · "
            f"Summe {sum(rr):+.1f}R · PF {pf:.2f}")


def main():
    start = zeit(sys.argv[1] + "T00:00:00+00:00") if len(sys.argv) > 1 else zeit("2023-01-01T00:00:00+00:00")
    now = datetime.now(timezone.utc)
    tage_zurueck = (now - start).days + 80
    print(f"Lade Kerzen ab {(now - timedelta(days=tage_zurueck)).date()} ...")
    tage = bot.kerzen("1Day", tage_zurueck, now)
    h4 = bot.kerzen("4Hour", tage_zurueck, now)
    print(f"{len(tage)} Tageskerzen, {len(h4)} 4h-Kerzen")
    basis = rechner.lade_parameter()

    zeilen = ["# Rückblick-Test (Backtest)", "",
              f"Zeitraum: **{start:%d.%m.%Y} – {now:%d.%m.%Y}** · Start {START_KAPITAL:.0f} $ · nur Regeln (ohne KI-Ampel) · "
              f"erstellt {now.astimezone(rechner.WIEN):%d.%m.%Y %H:%M}", ""]
    btc_start = next(k["c"] for k in sorted(h4, key=lambda k: k["t"]) if k["t"] >= start)
    btc_ende = sorted(h4, key=lambda k: k["t"])[-1]["c"]
    zeilen += [f"Zum Vergleich **Bitcoin halten**: {btc_start:,.0f} → {btc_ende:,.0f} $ = "
               f"**{btc_ende / btc_start - 1:+.0%}** ({START_KAPITAL:.0f} → {START_KAPITAL * btc_ende / btc_start:,.0f} $)", ""]

    varianten = [("Bot wie jetzt (Ziel 2R)", {}), ("Ziel 1,5R", {"ziel_r": 1.5}), ("Ziel 3R", {"ziel_r": 3.0}),
                 ("ohne S1 (nur Bitcoin kaufen)", {"S1_aktiv": False}),
                 ("ohne Abkühlzeit nach Verlust", {"nach_verlust_pause_std": 0})]
    zeilen += ["## Ergebnis", "| Variante | Ergebnis | Endkapital | Größter Rückgang | Trades/Monat |", "|---|---|---|---|---|"]
    monate = max((now - start).days / 30.4, 1)
    basis_trades = None
    for name, aend in varianten:
        p = dict(basis, **aend)
        trades, eq, dd = simuliere(tage, h4, p, start)
        if basis_trades is None:
            basis_trades = trades
        zeilen.append(f"| {name} | {kennzahlen([t['r'] for t in trades])} | **{eq:,.0f} $** ({eq / START_KAPITAL - 1:+.0%}) "
                      f"| {dd:.0%} | {len(trades) / monate:.1f} |")
        print(name, eq, dd, len(trades))

    zeilen += ["", "## Bot wie jetzt – nach Setup, Trend und Jahr", "```"]
    for s in sorted({t["setup"] for t in basis_trades}):
        zeilen.append(f"{s:6} {kennzahlen([t['r'] for t in basis_trades if t['setup'] == s])}")
    for reg in sorted({t["regime"] for t in basis_trades}):
        zeilen.append(f"Trend {reg:10} {kennzahlen([t['r'] for t in basis_trades if t['regime'] == reg])}")
    for j in sorted({t["zeit"].year for t in basis_trades}):
        zeilen.append(f"{j}   {kennzahlen([t['r'] for t in basis_trades if t['zeit'].year == j])}")
    zeilen.append(f"Ausstiege: " + ", ".join(f"{g} {sum(1 for t in basis_trades if t['grund'] == g)}x"
                                            for g in ("Ziel", "Stop", "Zeitstop")))
    zeilen += ["```", "",
               "## Wichtig",
               "- Vergangenheit ≠ Zukunft. Ein guter Rückblick heißt nur: die Idee ist nicht schlecht.",
               "- **Nicht** die beste Variante blind übernehmen: das ist oft nur Zufall (Überanpassung). "
               "Ändern nur, wenn eine Variante in **jedem Jahr** besser ist.",
               "- Vereinfacht: Einstieg zum Kerzenschluss, S1 ohne BITI-Kosten, keine US-Feiertage, KI-Ampel nicht dabei.",
               ""]
    (HIER / "BACKTEST.md").write_text("\n".join(zeilen), encoding="utf-8")
    print("\n".join(zeilen))


if __name__ == "__main__":
    main()
