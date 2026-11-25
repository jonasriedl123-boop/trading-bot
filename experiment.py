"""
Experiment: Lohnt sich Traden mit KI?

Vergleicht 4 Varianten (Regeln dafuer stehen in EXPERIMENT.md):
  Bot (Regeln + KI)  = die echten Paper-Trades. Die KI-Ampel von Claude darf Signale sperren oder halbieren.
  Nur Regeln         = echte Trades (immer volles Risiko) + Signale, die die KI gesperrt hat.
                       Die gesperrten Signale werden als "Schatten-Trades" nur ausgerechnet, nicht gehandelt.
  Bitcoin halten     = Startgeld am ersten Tag komplett in Bitcoin
  Nichts tun         = Startgeld bleibt liegen

Dateien: daten/experiment.json, daten/verlauf.csv, daten/schatten.csv, BERICHT.md
"""
import csv
import json
from datetime import timedelta
from pathlib import Path

import rechner
from rechner import WIEN, zeit

HIER = Path(__file__).resolve().parent
DATEN = HIER / "daten"
EXP = DATEN / "experiment.json"
VERLAUF = DATEN / "verlauf.csv"
SCHATTEN = DATEN / "schatten.csv"
TRADES = DATEN / "trades.csv"
BERICHT = HIER / "BERICHT.md"

MIN_TRADES = 30       # vorher kein Urteil (sonst ist es Zufall)
MIN_TAGE = 56         # mind. 8 Wochen
DAUER_TAGE = 90       # Endauswertung nach ca. 3 Monaten
MAX_RUECKGANG = 0.15  # Bot darf vom Hoechststand max. 15 % verlieren
MIN_PF = 1.2          # Profit-Faktor (Gewinne / Verluste) mind. 1,2

SCH_SPALTEN = ["id", "setup", "richtung", "zeit", "kerze_ab", "einstieg", "stop", "ziel", "sperre",
               "status", "ausstieg", "ausstieg_zeit", "r"]
V_SPALTEN = ["datum", "bot", "btc_preis", "bitcoin_halten"]


def _lies(pfad):
    if not pfad.exists():
        return []
    with pfad.open(encoding="utf-8") as d:
        return list(csv.DictReader(d))


def _schreib(pfad, spalten, zeilen):
    with pfad.open("w", encoding="utf-8", newline="") as d:
        w = csv.DictWriter(d, fieldnames=spalten)
        w.writeheader()
        w.writerows(zeilen)


def start(now, equity, btc):
    """Legt beim ersten Lauf den Startpunkt fest (wird nie mehr geaendert)."""
    if EXP.exists():
        return json.loads(EXP.read_text(encoding="utf-8"))
    e = {"start": now.isoformat(), "equity": round(equity, 2), "btc": round(btc, 2),
         "ende_geplant": (now + timedelta(days=DAUER_TAGE)).astimezone(WIEN).date().isoformat()}
    EXP.write_text(json.dumps(e, indent=2) + "\n", encoding="utf-8")
    return e


def verlauf_update(now, equity, btc, exp):
    """Eine Zeile pro Tag (wird im Lauf des Tages ueberschrieben)."""
    zeilen = _lies(VERLAUF)
    heute = now.astimezone(WIEN).date().isoformat()
    neu = {"datum": heute, "bot": round(equity, 2), "btc_preis": round(btc),
           "bitcoin_halten": round(exp["equity"] * btc / exp["btc"], 2)}
    if zeilen and zeilen[-1]["datum"] == heute:
        zeilen[-1] = neu
    else:
        zeilen.append(neu)
    _schreib(VERLAUF, V_SPALTEN, zeilen)


# ---------- Schatten-Trades (von der KI gesperrte Signale) ----------
def schatten_neu(now, kerze_ab, setup, richtung, einstieg, stop, ziel, sperre):
    zeilen = _lies(SCHATTEN)
    zeilen.append({"id": len(zeilen) + 1, "setup": setup, "richtung": richtung, "zeit": now.isoformat(),
                   "kerze_ab": kerze_ab.isoformat(), "einstieg": round(einstieg, 2), "stop": round(stop, 2),
                   "ziel": round(ziel, 2), "sperre": sperre[:150], "status": "offen", "ausstieg": "",
                   "ausstieg_zeit": "", "r": ""})
    _schreib(SCHATTEN, SCH_SPALTEN, zeilen)


def _r(kurz, e, s, x, gebuehr):
    if kurz:  # Wette auf fallendes BTC ueber BITI (keine Gebuehr)
        return (e - x) / (s - e)
    return (x - e) / (e - s) - 2 * gebuehr * e / (e - s)


def schatten_update(h4, now, p):
    """Rechnet offene Schatten-Trades mit fertigen 4h-Kerzen weiter. Gleiche Regeln wie echte Trades:
    Stop, Ziel (2R), Zeitstop. Beruehrt eine Kerze Stop UND Ziel, zaehlt der Stop (vorsichtig)."""
    zeilen = _lies(SCHATTEN)
    fertig_neu = []
    for z in zeilen:
        if z["status"] != "offen":
            continue
        kurz = z["richtung"] == "short"
        e, s, zi = float(z["einstieg"]), float(z["stop"]), float(z["ziel"])
        ab = zeit(z["kerze_ab"])
        kerzen = sorted([k for k in h4 if k["t"] >= ab and k["t"] + timedelta(hours=4) <= now], key=lambda k: k["t"])
        ende = None
        for i, k in enumerate(kerzen, 1):
            if kurz:
                ende = (s, "Stop") if k["h"] >= s else (zi, "Ziel") if k["l"] <= zi else None
            else:
                ende = (s, "Stop") if k["l"] <= s else (zi, "Ziel") if k["h"] >= zi else None
            if not ende and i >= int(p["zeitstop_kerzen"]):
                ende = (k["c"], "Zeitstop")
            if ende:
                ende = ende + (k["t"] + timedelta(hours=4),)
                break
        if not ende and now - ab > timedelta(days=11):  # keine Kerzen mehr da (Bot lief lange nicht)
            ende = (e, "abgelaufen", now)
        if ende:
            x, grund, t_ende = ende
            gebuehr = 0.0 if kurz else p["gebuehr_pro_seite"]
            z.update(status=grund, ausstieg=round(x, 2), ausstieg_zeit=t_ende.isoformat(),
                     r=round(_r(kurz, e, s, x, gebuehr), 2) if grund != "abgelaufen" else 0.0)
            fertig_neu.append(dict(z))
    if fertig_neu:
        _schreib(SCHATTEN, SCH_SPALTEN, zeilen)
    return fertig_neu


# ---------- Tages-Prognose der KI (steigt / faellt / seitwaerts in 24 Std.) ----------
PROGNOSEN = DATEN / "prognosen.csv"
P_SPALTEN = ["erstellt", "start_zeit", "richtung", "start_preis", "ende_zeit", "ende_preis", "aenderung", "ergebnis"]
P_SCHWELLE = 0.01  # mehr als +1 % = steigt, weniger als -1 % = faellt, dazwischen = seitwaerts


def _richtung(x):
    x = str(x).lower().replace("ä", "ae")
    return "steigt" if x.startswith("st") else "faellt" if x.startswith("f") else "seitwaerts"


def prognose_update(now, preis, ampel_pfad):
    """Merkt sich jede neue Prognose aus der KI-Ampel und prueft sie nach 24 Std. Rueckgabe: neu geprueft (Liste)."""
    zeilen = _lies(PROGNOSEN)
    geaendert, fertig = False, []
    try:
        roh = json.loads(Path(ampel_pfad).read_text(encoding="utf-8"))
        pr, erst = roh.get("prognose_24h"), roh.get("erstellt")
        if pr and erst and not any(z["erstellt"] == erst for z in zeilen) and now - zeit(erst) < timedelta(hours=12):
            zeilen.append({"erstellt": erst, "start_zeit": now.isoformat(), "richtung": _richtung(pr),
                           "start_preis": round(preis), "ende_zeit": "", "ende_preis": "", "aenderung": "",
                           "ergebnis": "offen"})
            geaendert = True
    except Exception:
        pass
    for z in zeilen:
        if z["ergebnis"] == "offen" and now - zeit(z["start_zeit"]) >= timedelta(hours=24):
            ae = preis / float(z["start_preis"]) - 1
            echt = "steigt" if ae > P_SCHWELLE else "faellt" if ae < -P_SCHWELLE else "seitwaerts"
            z.update(ende_zeit=now.isoformat(), ende_preis=round(preis), aenderung=f"{ae:+.2%}",
                     ergebnis=("richtig" if echt == z["richtung"] else "falsch") + f" ({echt})")
            geaendert = True
            fertig.append(dict(z))
    if geaendert:
        _schreib(PROGNOSEN, P_SPALTEN, zeilen)
    return fertig


def prognose_text():
    zeilen = [z for z in _lies(PROGNOSEN) if z["ergebnis"] != "offen"]
    if not zeilen:
        return "noch keine geprüften Prognosen"
    n = len(zeilen)
    richtig = sum(1 for z in zeilen if z["ergebnis"].startswith("richtig"))
    echt = [z["ergebnis"].split("(")[-1].rstrip(")") for z in zeilen]
    haeufig = max(set(echt), key=echt.count)
    dauer = echt.count(haeufig) / n
    return (f"{richtig}/{n} richtig = **{richtig / n:.0%}** · Zufall wäre ca. 33 % · "
            f"immer „{haeufig}\" sagen hätte {dauer:.0%} gebracht")


# ---------- Bericht ----------
def max_rueckgang(werte):
    hoch, dd = None, 0.0
    for v in werte:
        hoch = v if hoch is None else max(hoch, v)
        if hoch:
            dd = max(dd, 1 - v / hoch)
    return dd


def _pf(rr):
    g = sum(x for x in rr if x > 0)
    v = abs(sum(x for x in rr if x <= 0))
    return (g / v) if v else (99.0 if g else 0.0)


def bericht(now, equity, btc, exp, z, ampel, aktiv):
    trades = [t for t in _lies(TRADES) if t.get("r_netto")]
    sch = _lies(SCHATTEN)
    verlauf = _lies(VERLAUF)
    tag = (now - zeit(exp["start"])).days + 1

    start_g = float(exp["equity"])
    bot_ret = equity / start_g - 1
    bh_wert = start_g * btc / float(exp["btc"])
    bh_ret = bh_wert / start_g - 1
    dd_bot = max_rueckgang([float(v["bot"]) for v in verlauf] + [equity])
    dd_bh = max_rueckgang([float(v["bitcoin_halten"]) for v in verlauf] + [bh_wert])

    rr = [float(t["r_netto"]) for t in trades]
    n = len(rr)
    schnitt = sum(rr) / n if n else 0.0
    pf = _pf(rr)
    treffer = sum(1 for x in rr if x > 0) / n if n else 0.0
    r_ki = sum(float(t["r_netto"]) * (0.5 if t.get("ki") == "GELB" else 1.0) for t in trades)
    ki_sch = [s for s in sch if s["sperre"].startswith("KI")]
    ki_fertig = [s for s in ki_sch if s["status"] != "offen"]
    r_sch = sum(float(s["r"] or 0) for s in ki_fertig)
    r_regeln = sum(rr) + r_sch
    gelb = sum(1 for t in trades if t.get("ki") == "GELB")

    genug = n >= MIN_TRADES and tag >= MIN_TAGE

    def mark(ok, daten=True):
        return "⏳" if not daten else ("✅" if ok else "❌")

    k = [
        ("Macht der Bot nach Gebühren Gewinn? (Schnitt > 0R und Profit-Faktor ≥ 1,2)",
         f"{schnitt:+.2f}R pro Trade, PF {pf:.2f}" if n else "noch keine Trades", schnitt > 0 and pf >= MIN_PF, n > 0),
        ("Besser als nichts tun?", f"{bot_ret:+.1%}", bot_ret > 0, True),
        ("Besser als Bitcoin halten?", f"Bot {bot_ret:+.1%} / Bitcoin {bh_ret:+.1%}", bot_ret > bh_ret, True),
        (f"Größter Rückgang unter {MAX_RUECKGANG:.0%}?", f"Bot {dd_bot:.1%} / Bitcoin {dd_bh:.1%}",
         dd_bot < MAX_RUECKGANG, True),
        ("Hilft die KI-Ampel? (KI-Bot ≥ nur Regeln)",
         f"KI {r_ki:+.2f}R / nur Regeln {r_regeln:+.2f}R ({len(ki_fertig)} gesperrte Signale fertig, {gelb}x halbes Risiko)",
         r_ki >= r_regeln, bool(ki_fertig) or gelb > 0),
    ]

    if not genug:
        urteil = (f"⏳ **Noch kein Urteil.** {n}/{MIN_TRADES} Trades, Tag {tag}/{MIN_TAGE}. "
                  f"Mit so wenig Trades kann alles noch Zufall sein.")
    elif all(ok for _, _, ok, _ in k[:4]):
        urteil = "✅ **Lohnt sich (bis jetzt).**" + (
            " Die KI-Ampel hilft dabei." if k[4][2] else " Aber die KI-Ampel bringt nichts extra – nur Regeln wäre gleich gut.")
    else:
        nein = [txt.split("?")[0] for txt, _, ok, _ in k[:4] if not ok]
        urteil = "❌ **Lohnt sich (noch) nicht.** Nicht erfüllt: " + "; ".join(nein)

    t = z.get("position")
    if t:
        pos = (f"{t.get('symbol', 'BTCUSD')} · Setup {t['setup']} · Einstieg {t['einstieg']} · Stop {t['stop']} · "
               f"Ziel {t['ziel']} · KI {t.get('ki', '?')}")
    else:
        pos = "keine" + (" (S1-Signal wartet auf US-Börse)" if z.get("s1_wartet") else "")
    if ampel:
        amp = (f"Bitcoin steigt: **{ampel.get('long_btc', '?')}** · Bitcoin fällt: **{ampel.get('fallend_biti', '?')}** "
               f"· gültig bis {zeit(ampel['gueltig_bis']).astimezone(WIEN):%d.%m. %H:%M}\n\n> {ampel.get('begruendung', '')}")
    else:
        amp = "keine gültige Ampel → Bot handelt nur nach Regeln (Claude-Lauf fehlt)"
    status = "aktiv" if aktiv else "AUS (BOT_AKTIV.txt)"
    if z.get("pause_bis") and zeit(z["pause_bis"]) > now:
        status += f", Pause bis {zeit(z['pause_bis']).astimezone(WIEN):%d.%m. %H:%M}"
    offen_sch = sum(1 for s in sch if s["status"] == "offen")

    zeilen = [
        "# Experiment: Lohnt sich Traden mit KI?",
        "",
        f"Stand: {now.astimezone(WIEN):%d.%m.%Y %H:%M} · Tag {tag} · Start {zeit(exp['start']).astimezone(WIEN):%d.%m.%Y} "
        f"· Endauswertung ca. {exp['ende_geplant']}",
        "",
        "## Urteil",
        urteil,
        "",
        "## Vergleich",
        "| | Bot (Regeln + KI) | Bitcoin halten | Nichts tun |",
        "|---|---|---|---|",
        f"| Wert | {equity:,.2f} $ | {bh_wert:,.2f} $ | {start_g:,.2f} $ |",
        f"| Ergebnis | {bot_ret:+.1%} | {bh_ret:+.1%} | ±0 % |",
        f"| Größter Rückgang | {dd_bot:.1%} | {dd_bh:.1%} | 0 % |",
        "",
        f"Trades: **{n}** · Treffer {treffer:.0%} · Summe {sum(rr):+.2f}R · Gesperrte Signale (KI): {len(ki_sch)} "
        f"({offen_sch} laufen noch)",
        "",
        "## Die 5 Fragen",
        "| Frage | Stand | |",
        "|---|---|---|",
    ]
    zeilen += [f"| {txt} | {wert} | {mark(ok, daten)} |" for txt, wert, ok, daten in k]
    zeilen += [
        "",
        f"**Bonus – kann die KI die Richtung vorhersagen? (Bitcoin in 24 Std.)** {prognose_text()}",
        "",
        "## Jetzt",
        f"- Bot: {status}",
        f"- Position: {pos}",
        f"- KI-Ampel: {amp}",
        "",
        "## Details",
        "```",
        *rechner.stats(TRADES),
        "```",
        "",
        "_R = Vielfaches vom Risiko. 1R = so viel, wie bei Stop verloren geht (ca. 2 % vom Konto). "
        "Schatten-Trades sind ungefähr gerechnet (4-Std.-Kerzen)._",
        "",
    ]
    BERICHT.write_text("\n".join(zeilen), encoding="utf-8")
