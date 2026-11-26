#!/usr/bin/env python3
"""
Backtest nach BOT-PLAN Teil B 10 (Methode aus Video 1). Laeuft auf GitHub (braucht die Alpaca-Schluessel).
Die Regeln stehen vorher fest (config.json). Danach wird NICHT am Ergebnis gedreht.

  python3 backtest.py          -> Daten holen, alle Strategien testen, BACKTEST.md + daten/backtest_ergebnis.json

Methode:
  - 70 % der Zeit zum Ueben, die letzten 30 % versteckt. Bewertet wird nur der versteckte Teil.
  - Krypto ab 2021 (mit Crash-Jahr 2022), Aktien/ETFs ab 2016. Gebuehren: Krypto 0,25 %/Seite, Aktien 0,05 % Schlupf.
  - Einstieg zur Eroeffnung der Kerze NACH dem Signal, Stop zuerst wenn Stop und Ziel in derselben Kerze.
  - Markt-Filter wie im Bot (BTC bzw. SPY ueber 200-Tage-Schnitt).
  - Pruefungen: genug Trades, besser als Halten (Ertrag/Absturz), besser als 10 Zufalls-Zwillinge,
    max. 50 % Absturz, versteckt mind. halb so gut wie beim Ueben, Nachbar-Einstellungen gehen auch.
"""
import bisect
import json
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import strategien as st

HIER = Path(__file__).resolve().parent
ERGEBNIS = HIER / "daten" / "backtest_ergebnis.json"
BERICHT = HIER / "BACKTEST.md"
RISIKO = 0.01
GEBUEHR = {"krypto": 0.0025, "aktien": 0.0005}
NACHBARN = {  # je 2 Einstellungen nach oben/unten verschieben
    "breakout_tag": [("lookback", -10), ("lookback", 10), ("stop_atr", -0.25), ("stop_atr", 0.25)],
    "breakout_4h": [("min_stimmen", -0.2), ("min_stimmen", 0.2), ("stop_atr", -0.25), ("stop_atr", 0.25)],
    "breakout_1h": [("min_stimmen", -0.25), ("min_stimmen", 0.25), ("stop_atr", -0.25), ("stop_atr", 0.25)],
    "ruecksetzer_tag": [("rsi_max", -5), ("rsi_max", 5), ("stop_atr", -0.2), ("stop_atr", 0.2)],
    "ruecksetzer_4h": [("rsi_max", -5), ("rsi_max", 5), ("stop_atr", -0.2), ("stop_atr", 0.2)],
    "umkehr_tag": [("rsi_max", -5), ("rsi_max", 5), ("stop_atr", -0.2), ("stop_atr", 0.2)],
    "umkehr_4h": [("rsi_max", -5), ("rsi_max", 5), ("stop_atr", -0.2), ("stop_atr", 0.2)],
}


# ---------------- Daten ----------------
def lade_daten(cfg):
    import bot  # nur hier: braucht Internet + Schluessel
    now = datetime.now(timezone.utc)
    ende = now - timedelta(days=1)
    k_start, a_start = datetime(2021, 1, 1, tzinfo=timezone.utc), datetime(2016, 1, 1, tzinfo=timezone.utc)
    krypto = cfg["krypto"]
    aktien = cfg["aktien"] + cfg["neutral"] + cfg["invers_aktien"] + cfg["invers_krypto"]
    d = {"krypto": {}, "aktien": {}}
    for art, tf in (("tag", "1Day"), ("4h", "4Hour"), ("1h", "1Hour")):
        d["krypto"][art] = bot.krypto_kerzen(krypto, tf, k_start, ende)
        print(f"Krypto {art}: " + ", ".join(f"{s} {len(v)}" for s, v in d["krypto"][art].items()), flush=True)
    d["aktien"]["tag"] = bot.aktien_kerzen(aktien, a_start, ende)
    print("Aktien: " + ", ".join(f"{s} {len(v)}" for s, v in d["aktien"]["tag"].items()), flush=True)
    return d


# ---------------- Kennzahlen ----------------
def kennzahlen(trades, risiko=RISIKO):
    if not trades:
        return {"n": 0, "treffer": 0, "schnitt_r": 0, "summe_r": 0, "pf": 0, "ertrag": 0, "absturz": 0}
    rr = [t["r"] for t in sorted(trades, key=lambda t: t["aus_t"])]
    eq = hoch = 1.0
    dd = 0.0
    for r in rr:
        eq *= 1 + risiko * r
        hoch = max(hoch, eq)
        dd = max(dd, 1 - eq / hoch)
    g = sum(r for r in rr if r > 0)
    v = -sum(r for r in rr if r <= 0)
    return {"n": len(rr), "treffer": round(sum(r > 0 for r in rr) / len(rr), 3),
            "schnitt_r": round(sum(rr) / len(rr), 3), "summe_r": round(sum(rr), 1),
            "pf": round(g / v, 2) if v else 99.0, "ertrag": round(eq - 1, 4), "absturz": round(dd, 4)}


def halten(serien, ab):
    """Gleich verteilt kaufen und halten ab Zeitpunkt ab. Rueckgabe (Ertrag, groesster Absturz)."""
    normiert = []
    for k in serien.values():
        k = [x for x in k if x["t"] >= ab]
        if len(k) > 20:
            normiert.append({x["t"].date(): x["c"] / k[0]["c"] for x in k})
    if not normiert:
        return 0.0, 0.0
    tage = sorted(set().union(*[set(n) for n in normiert]))
    letzte = [1.0] * len(normiert)
    hoch, dd, wert = 1.0, 0.0, 1.0
    for t in tage:
        for j, n in enumerate(normiert):
            letzte[j] = n.get(t, letzte[j])
        wert = sum(letzte) / len(letzte)
        hoch = max(hoch, wert)
        dd = max(dd, 1 - wert / hoch)
    return round(wert - 1, 4), round(dd, 4)


def mar(ertrag, absturz):
    return ertrag / max(absturz, 0.02)


# ---------------- Markt-Filter ----------------
def filter_reihe(tageskerzen):
    """Liste (Schlusszeit, ueber SMA200?) fuer schnelle Abfrage."""
    if not tageskerzen:
        return [], []
    ind = st.vorberechnen(tageskerzen, lookbacks=())
    zeiten, werte = [], []
    for i, t in enumerate(ind["t"]):
        s = ind["sma200"][i]
        zeiten.append(t + timedelta(days=1))
        werte.append(None if s is None else ind["c"][i] > s)
    return zeiten, werte


def filter_zu(reihe, zeitpunkt):
    zeiten, werte = reihe
    i = bisect.bisect_right(zeiten, zeitpunkt) - 1
    return werte[i] if i >= 0 else None


def erlaubt_fn(sym, cfg, f_btc, f_spy, stunden):
    def ok(t):
        jetzt = t + timedelta(hours=stunden)  # Signal am Schluss der Kerze
        if sym in cfg["krypto"]:
            return filter_zu(f_btc, jetzt) is True
        if sym in cfg["neutral"]:
            return True
        if sym in cfg["invers_aktien"]:
            return filter_zu(f_spy, jetzt) is False
        if sym in cfg["invers_krypto"]:
            return filter_zu(f_btc, jetzt) is False
        return filter_zu(f_spy, jetzt) is True
    return ok


# ---------------- Test einer Strategie ----------------
def teste(name, s, serien, inds, cfg, f_btc, f_spy, gruppe):
    art = st.ART[name]
    alle = []
    for sym, k in serien.items():
        if sym not in inds or len(k) < 260:
            continue
        tr = st.simuliere(k, inds[sym], name, s, erlaubt=erlaubt_fn(sym, cfg, f_btc, f_spy, st.STUNDEN[art]),
                          gebuehr=GEBUEHR[gruppe])
        for t in tr:
            t["symbol"] = sym
        alle += tr
    return alle


def zwillinge(trades, serien, gruppe, anzahl=10, seed=42):
    """Gleich viele Trades, gleiche Haltedauer, zufaellige Zeitpunkte und Werte. Rueckgabe: Summen in %."""
    if not trades:
        return []
    syms = [s for s, k in serien.items() if len(k) > 300]
    t_min = min(t["ein_t"] for t in trades)
    starts = {s: bisect.bisect_left([x["t"] for x in serien[s]], t_min) for s in syms}
    sums = []
    for z in range(anzahl):
        rnd = random.Random(seed + z)
        summe = 0.0
        for t in trades:
            sym = rnd.choice(syms)
            k, start = serien[sym], starts[sym]
            if len(k) - t["kerzen"] - 1 <= start:
                continue
            i = rnd.randrange(start, len(k) - t["kerzen"] - 1)
            e, a = k[i]["o"], k[i + t["kerzen"]]["c"]
            summe += (a - e) / e - GEBUEHR[gruppe] * 2
        sums.append(summe)
    return sums


def prozent_summe(trades, gruppe):
    return sum((t["aus"] - t["ein"]) / t["ein"] - GEBUEHR[gruppe] * 2 for t in trades)


def auswerten(daten, cfg):
    f_btc = filter_reihe(daten["krypto"].get("tag", {}).get("BTC/USD"))
    f_spy = filter_reihe(daten["aktien"].get("tag", {}).get("SPY"))
    ergebnis = {}
    for name, s in cfg["strategien"].items():
        art = st.ART[name]
        gruppe = st.GRUPPE[art]
        serien = {sym: sorted(k, key=lambda x: x["t"]) for sym, k in daten[gruppe].get(art, {}).items() if k}
        if not serien:
            ergebnis[name] = {"bestanden": False, "grund": "keine Daten"}
            continue
        inds = {sym: st.vorberechnen(k) for sym, k in serien.items()}
        t0 = min(k[0]["t"] for k in serien.values())
        t1 = max(k[-1]["t"] for k in serien.values())
        schnitt = t0 + (t1 - t0) * 0.7
        alle = teste(name, s, serien, inds, cfg, f_btc, f_spy, gruppe)
        ueben = [t for t in alle if t["ein_t"] < schnitt]
        test = [t for t in alle if t["ein_t"] >= schnitt]
        ku, kt = kennzahlen(ueben), kennzahlen(test)
        # Halten im versteckten Teil (nur normale Werte, ohne inverse ETFs)
        hold_serien = {x: k for x, k in (daten[gruppe].get("tag") or {}).items()
                       if x in (cfg["krypto"] if gruppe == "krypto" else cfg["aktien"])}
        h_ertrag, h_absturz = halten(hold_serien, schnitt)
        # Zufalls-Zwillinge im versteckten Teil
        echt = prozent_summe(test, gruppe)
        zw = zwillinge(test, serien, gruppe)
        geschlagen = sum(echt > x for x in zw)
        # Nachbar-Einstellungen
        nachbarn = []
        for key, delta in NACHBARN.get(name, []):
            s2 = dict(s)
            s2[key] = round(float(s2[key]) + delta, 3)
            if key == "min_stimmen":
                s2[key] = min(1.0, max(0.2, s2[key]))
            tn = [t for t in teste(name, s2, serien, inds, cfg, f_btc, f_spy, gruppe) if t["ein_t"] >= schnitt]
            nachbarn.append({"aenderung": f"{key} {delta:+g}", **kennzahlen(tn)})
        nb_ok = sum(1 for n in nachbarn if n["n"] > 0 and n["schnitt_r"] > 0)
        jahre = {}
        for t in alle:
            jahre.setdefault(t["ein_t"].year, []).append(t)
        krit = {
            "mind. 20 Trades (versteckt)": kt["n"] >= 20,
            "Gewinn nach Gebühren (versteckt)": kt["schnitt_r"] > 0,
            "versteckt mind. halb so gut wie Üben": ku["schnitt_r"] > 0 and kt["schnitt_r"] >= 0.5 * ku["schnitt_r"],
            "besser als Halten (Ertrag/Absturz)": mar(kt["ertrag"], kt["absturz"]) > mar(h_ertrag, h_absturz),
            "besser als Zufall (≥ 8 von 10 Zwillingen)": geschlagen >= 8,
            "max. 50 % Absturz": kt["absturz"] <= 0.5 and ku["absturz"] <= 0.5,
            "Nachbar-Einstellungen gehen auch (≥ 3 von 4)": nb_ok >= 3,
        }
        ergebnis[name] = {
            "bestanden": all(krit.values()), "kriterien": krit, "gruppe": gruppe,
            "zeitraum": f"{t0:%Y-%m-%d} bis {t1:%Y-%m-%d}, versteckt ab {schnitt:%Y-%m-%d}",
            "ueben": ku, "versteckt": kt, "halten_versteckt": {"ertrag": h_ertrag, "absturz": h_absturz},
            "zwillinge": {"echt_prozent": round(echt, 3), "zufall_prozent": [round(x, 3) for x in zw],
                          "geschlagen": geschlagen},
            "nachbarn": nachbarn, "jahre": {str(j): kennzahlen(v) for j, v in sorted(jahre.items())},
            "ausstiege": {g: sum(1 for t in alle if t["grund"] == g) for g in ("Ziel", "Stop", "Zeit")},
        }
        print(f"{name}: bestanden={ergebnis[name]['bestanden']} | versteckt {kt} | Zwillinge {geschlagen}/10 | "
              f"Nachbarn {nb_ok}/4", flush=True)
    return ergebnis


def bericht(ergebnis, cfg):
    now = datetime.now(timezone.utc)
    zeilen = ["# Backtest v3 (Methode aus Video 1)", "",
              f"Erstellt: {now:%d.%m.%Y %H:%M} UTC · Regeln aus `config.json` (vorher festgeschrieben) · "
              f"1 % Risiko pro Trade · Gebühren eingerechnet", "",
              "| Strategie | Bestanden | Versteckt: Trades · Schnitt · PF · Ertrag · Absturz | Üben: Schnitt | "
              "Halten (versteckt) | Zufall geschlagen | Nachbarn ok |",
              "|---|---|---|---|---|---|---|"]
    for name, e in ergebnis.items():
        if "versteckt" not in e:
            zeilen.append(f"| {name} | ❌ | {e.get('grund', '')} | | | | |")
            continue
        v, u, h = e["versteckt"], e["ueben"], e["halten_versteckt"]
        nb = sum(1 for n in e["nachbarn"] if n["n"] > 0 and n["schnitt_r"] > 0)
        zeilen.append(f"| {name} | {'✅' if e['bestanden'] else '❌'} | {v['n']} · {v['schnitt_r']:+.2f}R · "
                      f"{v['pf']} · {v['ertrag']:+.1%} · {v['absturz']:.1%} | {u['schnitt_r']:+.2f}R ({u['n']}) | "
                      f"{h['ertrag']:+.1%} / −{h['absturz']:.0%} | {e['zwillinge']['geschlagen']}/10 | {nb}/4 |")
    gut = [n for n, e in ergebnis.items() if e.get("bestanden")]
    zeilen += ["", "## Ehrlich in 3 Zeilen", ""]
    if gut:
        zeilen.append(f"- Den Zufall (und alle anderen Prüfungen) schlagen: **{', '.join(gut)}**. Nur die handeln normal.")
    else:
        zeilen.append("- **Keine** Strategie besteht alle Prüfungen. Der Bot macht deshalb nur Lern-Trades (halbes Risiko).")
    schlecht = [n for n in ergebnis if n not in gut]
    zeilen.append(f"- Nicht bestanden (nur als Lern-Trades erlaubt): {', '.join(schlecht) or '–'}.")
    zeilen.append("- Vergangenheit ≠ Zukunft. Bestanden heißt nur: wahrscheinlich kein reines Glück.")
    zeilen += ["", "## Details pro Strategie", ""]
    for name, e in ergebnis.items():
        if "kriterien" not in e:
            continue
        zeilen += [f"### {name} ({e['zeitraum']})", ""]
        zeilen += [f"- {'✅' if ok else '❌'} {k}" for k, ok in e["kriterien"].items()]
        zeilen.append(f"- Jahre: " + " · ".join(f"{j}: {k['n']} Tr. {k['summe_r']:+.1f}R" for j, k in e["jahre"].items()))
        zeilen.append(f"- Nachbarn: " + " · ".join(f"{n['aenderung']}: {n['schnitt_r']:+.2f}R ({n['n']})"
                                                     for n in e["nachbarn"]))
        zeilen.append(f"- Ausstiege: {e['ausstiege']} · Zwillinge (Summe %): echt {e['zwillinge']['echt_prozent']:+.2f} "
                      f"vs Zufall {e['zwillinge']['zufall_prozent']}")
        zeilen.append("")
    zeilen += ["## Vereinfachungen", "",
               "- Jede Strategie einzeln, Trades verschiedener Werte gleichzeitig werden nacheinander verrechnet.",
               "- Aktien-Daten mit Split-Anpassung, ohne Dividenden. Inverse ETFs (SH, PSQ, BITI) nur mit eigenen Kursen.",
               "- Die KI-Ampel kann man nicht rückwirkend testen.", ""]
    BERICHT.write_text("\n".join(zeilen), encoding="utf-8")


def main():
    cfg = json.loads((HIER / "config.json").read_text(encoding="utf-8"))
    daten = lade_daten(cfg)
    ergebnis = auswerten(daten, cfg)
    ERGEBNIS.parent.mkdir(exist_ok=True)
    ERGEBNIS.write_text(json.dumps({"erstellt": datetime.now(timezone.utc).isoformat(), "version": cfg.get("version"),
                                    "strategien": ergebnis}, indent=1, ensure_ascii=False, default=str) + "\n",
                        encoding="utf-8")
    bericht(ergebnis, cfg)
    print("Fertig:", {n: e.get("bestanden") for n, e in ergebnis.items()})


if __name__ == "__main__":
    sys.exit(main())
