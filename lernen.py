#!/usr/bin/env python3
"""
Wochen-Analyse (BOT-PLAN Teil B 9). Laeuft sonntags auf GitHub (vor dem Claude-Lernen) und schreibt LERNEN.md.
Claude liest das am Sonntag, entscheidet max. 1 Aenderung und nutzt dafuer die Befehle unten.

  python3 lernen.py analyse                  -> LERNEN.md + daten/lernen.json (Zahlen + Zufalls-Zwillinge)
  python3 lernen.py speichern "Grund"        -> Kopie von config.json nach history/ (VOR jeder Aenderung)
  python3 lernen.py zurueck history/<datei>  -> alte Version wieder herstellen
"""
import csv
import json
import random
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HIER = Path(__file__).resolve().parent
TRADES, SCHATTEN = HIER / "daten" / "trades.csv", HIER / "daten" / "schatten.csv"
HISTORY = HIER / "history"
MIN_FEIN, MIN_AUS = 20, 15  # Trades fuer Feinjustieren / Abschalten


def lies(p):
    if not p.exists():
        return []
    with p.open(encoding="utf-8") as d:
        return list(csv.DictReader(d))


def stat(zs, key="r"):
    rr = [float(z[key]) for z in zs if z.get(key) not in (None, "")]
    if not rr:
        return {"n": 0}
    g, v = sum(x for x in rr if x > 0), -sum(x for x in rr if x <= 0)
    return {"n": len(rr), "treffer": round(sum(x > 0 for x in rr) / len(rr), 2), "schnitt_r": round(sum(rr) / len(rr), 2),
            "summe_r": round(sum(rr), 2), "pf": round(g / v, 2) if v else None,
            "usd": round(sum(float(z.get("gewinn_usd") or 0) for z in zs), 2)}


def gruppen(zs, feld):
    out = {}
    for z in zs:
        out.setdefault(z.get(feld) or "?", []).append(z)
    return {k: stat(v) for k, v in sorted(out.items())}


def urteil(z):
    """Kurz-Urteil pro Trade: Koennen / Pech / Glueck / Fehler (Vorschlag, Claude prueft am Sonntag)."""
    r, mfe = float(z["r"]), float(z.get("mfe_r") or 0)
    if r > 0 and z["grund"] == "Ziel":
        return "Können (Plan ging auf)"
    if r > 0:
        return "Glück (Gewinn ohne Ziel, z. B. Zeitstop)"
    if mfe >= 1.0:
        return "Fehler? (war schon +1R, dann verloren → Ausstieg prüfen)"
    if z["grund"].startswith("Stop") and float(z.get("mae_r") or -1) <= -1:
        return "Pech oder schlechtes Signal (sofort gegen uns)"
    return "Pech (normaler Verlust nach Regeln)"


def zwillinge(zs, n=10, seed=7):
    """Live-Version: Ergebnis der Strategie vs. zufaellig gemischte Vorzeichen (Muenzwurf-Test auf die R-Werte)."""
    rr = [float(z["r"]) for z in zs]
    if len(rr) < 5:
        return None
    echt = sum(rr)
    zuf = []
    for k in range(n):
        rnd = random.Random(seed + k)
        zuf.append(sum(abs(x) * rnd.choice((1, -1)) for x in rr))
    return {"echt": round(echt, 2), "zufall": [round(x, 2) for x in zuf], "geschlagen": sum(echt > x for x in zuf)}


def analyse():
    now = datetime.now(timezone.utc)
    alle = [z for z in lies(TRADES) if z["strategie"] != "START"]
    woche = [z for z in alle if datetime.fromisoformat(z["ausstieg_zeit"]) >= now - timedelta(days=7)]
    normal, lern = [z for z in alle if z["lern"] == "nein"], [z for z in alle if z["lern"] == "ja"]
    sch = [z for z in lies(SCHATTEN) if z["status"] != "offen"]
    vorschlaege = []
    for s, zs in sorted({x["strategie"]: [z for z in normal if z["strategie"] == x["strategie"]] for x in normal}.items()):
        st = stat(zs)
        if st["n"] >= MIN_AUS and st["schnitt_r"] < -0.3:
            vorschlaege.append(f"{s}: {st['n']} Trades, Schnitt {st['schnitt_r']}R → Abschalten prüfen")
        elif st["n"] >= MIN_FEIN and st["schnitt_r"] > 0.2:
            vorschlaege.append(f"{s}: läuft gut ({st['schnitt_r']}R) → mehr Gewicht prüfen")
    for sym, st in gruppen(alle, "symbol").items():
        if st["n"] >= 8 and st["schnitt_r"] < -0.5:
            vorschlaege.append(f"{sym}: {st['n']} Trades, {st['schnitt_r']}R → in gesperrte_werte prüfen")
    lj = {"erstellt": now.isoformat(), "gesamt": stat(alle), "woche": stat(woche), "normal": stat(normal),
          "lern": stat(lern), "schatten": stat(sch), "nach_strategie": gruppen(alle, "strategie"),
          "nach_wert": gruppen(alle, "symbol"), "nach_uhrzeit": gruppen(
              [dict(z, stunde=z["uhrzeit_wien"][:2]) for z in alle], "stunde"),
          "nach_wochentag": gruppen(alle, "wochentag"), "nach_trend": gruppen(alle, "trend"),
          "nach_ki": gruppen(alle, "ki"), "schatten_nach_grund": gruppen(
              [dict(z, g=z["warum_nicht"].split(":")[0][:40]) for z in sch], "g"),
          "zwillinge": {s: zwillinge([z for z in normal if z["strategie"] == s]) for s in {z["strategie"] for z in normal}},
          "vorschlaege": vorschlaege}
    (HIER / "daten" / "lernen.json").write_text(json.dumps(lj, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

    def tab(titel, d):
        zeilen = [f"### {titel}", "", "| | Trades | Treffer | Schnitt R | Summe R | $ |", "|---|---|---|---|---|---|"]
        for k, s in d.items():
            if s.get("n"):
                zeilen.append(f"| {k} | {s['n']} | {s['treffer']:.0%} | {s['schnitt_r']:+.2f} | {s['summe_r']:+.1f} | {s['usd']:+.2f} |")
        return zeilen + [""]

    md = [f"# Lernen – Wochen-Analyse", "", f"Erstellt {now:%d.%m.%Y %H:%M} UTC. Claude liest das am Sonntag.", "",
          "## Überblick", "", "| | Trades | Treffer | Schnitt R | Summe R | $ |", "|---|---|---|---|---|---|"]
    for k in ("woche", "gesamt", "normal", "lern", "schatten"):
        s = lj[k]
        if s.get("n"):
            md.append(f"| {k} | {s['n']} | {s['treffer']:.0%} | {s['schnitt_r']:+.2f} | {s['summe_r']:+.1f} | {s.get('usd', 0):+.2f} |")
        else:
            md.append(f"| {k} | 0 | | | | |")
    md += [""] + tab("Nach Strategie", lj["nach_strategie"]) + tab("Nach Wert", lj["nach_wert"]) \
        + tab("Nach Uhrzeit (Wien)", lj["nach_uhrzeit"]) + tab("Nach Wochentag", lj["nach_wochentag"]) \
        + tab("Nach Markt-Filter", lj["nach_trend"]) + tab("Nach KI-Ampel", lj["nach_ki"]) \
        + tab("Schatten-Trades nach Grund (was wäre gewesen?)", lj["schatten_nach_grund"])
    md += ["## Zufalls-Zwillinge (live, normale Trades)", ""]
    for s, zw in lj["zwillinge"].items():
        md.append(f"- {s}: " + (f"echt {zw['echt']:+.1f}R, schlägt {zw['geschlagen']}/10 Zufalls-Kopien"
                                if zw else "zu wenige Trades"))
    md += ["", "## Trades der Woche – Kurz-Urteil (Vorschlag)", ""]
    for z in woche:
        md.append(f"- #{z['id']} {z['symbol']} {z['strategie']}{' (Lern)' if z['lern'] == 'ja' else ''}: "
                  f"{float(z['r']):+.2f}R, {z['grund']}, MFE {z['mfe_r']} → {urteil(z)}")
    md += ["", "## Vorschläge (nur wenn genug Daten, max. 1 Änderung pro Woche)", ""]
    md += [f"- {v}" for v in vorschlaege] or ["- keine – zu wenige Daten oder nichts Auffälliges. Oft ist „nichts ändern“ richtig."]
    (HIER / "LERNEN.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


def speichern(grund):
    HISTORY.mkdir(exist_ok=True)
    ziel = HISTORY / f"config-{datetime.now(timezone.utc):%Y-%m-%d-%H%M}.json"
    shutil.copy(HIER / "config.json", ziel)
    with (HISTORY / "VERSIONEN.md").open("a", encoding="utf-8") as d:
        d.write(f"| {datetime.now(timezone.utc):%Y-%m-%d} | {ziel.name} | {grund} |\n")
    print(f"Gespeichert: {ziel}")


def zurueck(datei):
    speichern(f"vor dem Zurückdrehen auf {Path(datei).name}")
    shutil.copy(HIER / datei, HIER / "config.json")
    print(f"config.json = {datei}")


if __name__ == "__main__":
    befehl = sys.argv[1] if len(sys.argv) > 1 else "analyse"
    if befehl == "analyse":
        analyse()
    elif befehl == "speichern":
        speichern(" ".join(sys.argv[2:]) or "ohne Grund")
    elif befehl == "zurueck":
        zurueck(sys.argv[2])
    else:
        print(__doc__)
