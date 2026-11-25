"""
Rechen-Teil des Bots: Indikatoren, Signale, Positionsgroesse, Trade-Verwaltung, Statistik.
Reine Funktionen ohne Internet - dadurch testbar.
"""
import csv
import json
from datetime import timedelta
from pathlib import Path

HIER = Path(__file__).resolve().parent

# Harte Grenzen: gelten immer, egal was in parameter.json steht. Nur Jonas aendert die.
HART = {
    "risiko_max": 0.02,       # max. 2 % vom Konto pro Trade
    "ziel_r_min": 1.5,
    "ziel_r_max": 3.0,
    "max_cash_anteil": 0.95,
    "min_notional": 10.0,     # Alpaca-Minimum fuer Krypto-Orders
    "notbremse_equity": 425.0,  # unter 425 $ keine neuen Trades
    "max_einstiege_tag": 2,
    "verlustserie_pause": 3,  # 3 Verluste in Folge -> 24 Std. Pause
}


def lade_parameter(pfad=None):
    p = json.loads(Path(pfad or HIER / "parameter.json").read_text(encoding="utf-8"))
    p["L1_risiko"] = min(float(p["L1_risiko"]), HART["risiko_max"])
    p["L2_risiko"] = min(float(p["L2_risiko"]), HART["risiko_max"])
    p["ziel_r"] = min(max(float(p["ziel_r"]), HART["ziel_r_min"]), HART["ziel_r_max"])
    p["max_cash_anteil"] = min(float(p.get("max_cash_anteil", 0.95)), HART["max_cash_anteil"])
    return p


# ---------- Indikatoren ----------
def sma(werte, n):
    return sum(werte[-n:]) / n if len(werte) >= n else None


def ema_reihe(werte, n):
    if len(werte) < n:
        return [None] * len(werte)
    out = [None] * (n - 1)
    e = sum(werte[:n]) / n
    out.append(e)
    a = 2 / (n + 1)
    for w in werte[n:]:
        e = a * w + (1 - a) * e
        out.append(e)
    return out


def rsi_reihe(closes, n=14):
    if len(closes) <= n:
        return [None] * len(closes)
    g, v = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i - 1]
        g.append(max(d, 0.0))
        v.append(max(-d, 0.0))
    ag, av = sum(g[:n]) / n, sum(v[:n]) / n

    def rs(ag, av):
        return 100.0 if av == 0 else 100 - 100 / (1 + ag / av)

    out = [None] * n + [rs(ag, av)]
    for i in range(n, len(g)):
        ag = (ag * (n - 1) + g[i]) / n
        av = (av * (n - 1) + v[i]) / n
        out.append(rs(ag, av))
    return out


def atr(kerzen, n=14):
    if len(kerzen) <= n:
        return None
    tr = []
    for i in range(1, len(kerzen)):
        h, l, pc = kerzen[i]["h"], kerzen[i]["l"], kerzen[i - 1]["c"]
        tr.append(max(h - l, abs(h - pc), abs(l - pc)))
    a = sum(tr[:n]) / n
    for x in tr[n:]:
        a = (a * (n - 1) + x) / n
    return a


# ---------- Analyse ----------
def analyse(tage, h4, now, p, equity, cash, preis=None, trade=None):
    """
    tage: Liste dicts {t,o,h,l,c} (Tageskerzen), h4: Liste dicts {t,o,h,l,c} (4h-Kerzen), Zeiten UTC.
    trade: dict {setup, einstieg, stop, ziel, zeit} wenn Position offen.
    Rueckgabe: dict mit 'aktion' (NICHTS / KAUFEN / HALTEN / VERKAUFEN_ZIEL / VERKAUFEN_ZEIT / PRUEFEN_STOP),
    'text' (Zeilen fuer das Protokoll) und Kennzahlen.
    """
    tage = sorted([k for k in tage if k["t"] + timedelta(days=1) <= now], key=lambda k: k["t"])
    alle4h = sorted(h4, key=lambda k: k["t"])
    k4 = [k for k in alle4h if k["t"] + timedelta(hours=4) <= now]
    r = {"aktion": "NICHTS", "text": [], "gruende": []}

    if len(tage) < 36 or len(k4) < 40:
        r["text"].append(f"FEHLER: zu wenig Daten (Tage {len(tage)}/36, 4h {len(k4)}/40)")
        r["gruende"].append("Daten unvollstaendig")
        return r

    dc = [k["c"] for k in tage]
    sma30 = sma(dc, 30)
    sma30_vor5 = sum(dc[-35:-5]) / 30
    rsi_d = rsi_reihe(dc)[-1]
    schluss_d = dc[-1]
    if schluss_d > sma30 and sma30 > sma30_vor5:
        regime = "AUF"
    elif schluss_d < sma30 and sma30 < sma30_vor5:
        regime = "AB"
    else:
        regime = "SEITWAERTS"

    c4 = [k["c"] for k in k4]
    ema20 = ema_reihe(c4, 20)
    sma40 = sma(c4, 40)
    rsi4 = rsi_reihe(c4)
    a = atr(k4)
    letzte, vor = k4[-1], k4[-2]
    preis = preis or alle4h[-1]["c"]
    gruen = letzte["c"] > letzte["o"]

    r.update(regime=regime, rsi_tag=round(rsi_d, 1), rsi_4h=round(rsi4[-1], 1), atr=a,
             atr_pct=round(a / letzte["c"] * 100, 2), preis=preis, letzte_kerze=letzte["t"],
             sma30=sma30, ema20=ema20[-1], sma40=sma40)
    r["text"].append(f"Trend {regime} | Tag: Schluss {schluss_d:,.0f}, SMA30 {sma30:,.0f} "
                     f"({schluss_d / sma30 - 1:+.1%}), RSI {rsi_d:.1f}")
    r["text"].append(f"4h ({letzte['t']:%d.%m. %H:%M} UTC): Schluss {letzte['c']:,.0f}, EMA20 {ema20[-1]:,.0f}, "
                     f"SMA40 {sma40:,.0f}, RSI {rsi4[-1]:.1f}, ATR {a:,.0f} ({a / letzte['c']:.2%}), "
                     f"{'gruen' if gruen else 'rot'} | Preis {preis:,.0f}")

    # ---- offene Position verwalten ----
    if trade:
        risiko = trade["einstieg"] - trade["stop"]
        seit = [k for k in alle4h if k["t"] + timedelta(hours=4) > trade["zeit"]]
        fertig = [k for k in seit if k["t"] + timedelta(hours=4) <= now and k["t"] >= trade["zeit"] - timedelta(hours=4)]
        hoch = max([k["h"] for k in seit] + [preis])
        tief = min([k["l"] for k in seit] + [preis])
        r["mfe_r"] = round((hoch - trade["einstieg"]) / risiko, 2)
        r["mae_r"] = round((tief - trade["einstieg"]) / risiko, 2)
        r["jetzt_r"] = round((preis - trade["einstieg"]) / risiko, 2)
        r["ziel_beruehrt"] = hoch >= trade["ziel"]
        r["text"].append(f"Position {trade['setup']}: Einstieg {trade['einstieg']:,.0f}, Stop {trade['stop']:,.0f}, "
                         f"Ziel {trade['ziel']:,.0f} | jetzt {r['jetzt_r']:+.2f}R, MFE {r['mfe_r']:+.2f}R, "
                         f"MAE {r['mae_r']:+.2f}R, Kerzen seit Einstieg {len(fertig)}")
        if preis >= trade["ziel"]:
            r["aktion"] = "VERKAUFEN_ZIEL"
        elif len(fertig) >= int(p["zeitstop_kerzen"]):
            r["aktion"] = "VERKAUFEN_ZEIT"
        elif preis <= trade["stop"]:
            r["aktion"] = "PRUEFEN_STOP"
        else:
            r["aktion"] = "HALTEN"
        return r

    # ---- neue Signale ----
    kandidat = None
    if p.get("L1_aktiv", True):
        if regime != "AUF":
            r["gruende"].append(f"L1: Trend {regime}")
        else:
            t1 = letzte["c"] > sma40 and ema20[-1] > sma40
            pull = min(k["l"] for k in k4[-3:]) <= ema20[-1] + p["L1_ema_toleranz_atr"] * a
            rsi_ok = min(x for x in rsi4[-3:] if x is not None) < p["L1_rsi_max"]
            trig = gruen and letzte["c"] > vor["h"]
            if t1 and pull and rsi_ok and trig:
                kandidat = ("L1", min(k["l"] for k in k4[-6:]) - p["stop_puffer_atr"] * a, p["L1_risiko"])
            else:
                fehlt = [n for n, ok in [("4h-Trend", t1), ("Ruecklauf EMA20", pull),
                                         (f"RSI<{p['L1_rsi_max']}", rsi_ok), ("Ausloeser", trig)] if not ok]
                r["gruende"].append("L1 fehlt: " + ", ".join(fehlt))

    if kandidat is None and p.get("L2_aktiv", True):
        gedehnt = rsi_d < p["L2_rsi_tag_max"] or schluss_d < sma30 * (1 - p["L2_abstand_sma30"])
        lb = int(p["L2_lookback"])
        ref_tief = min(k["l"] for k in k4[-(lb + 2):-2])
        sweep_tief = min(k["l"] for k in k4[-2:])
        sweep = sweep_tief < ref_tief
        zurueck = letzte["c"] > ref_tief and gruen
        r["l2_ref_tief"] = ref_tief
        if gedehnt and sweep and zurueck:
            kandidat = ("L2", sweep_tief - p["stop_puffer_atr"] * a, p["L2_risiko"])
        else:
            fehlt = [n for n, ok in [("ueberverkauft", gedehnt), (f"Sweep unter {ref_tief:,.0f}", sweep),
                                     ("gruen zurueck ueber Tief", zurueck)] if not ok]
            r["gruende"].append("L2 fehlt: " + ", ".join(fehlt))

    if kandidat is None:
        return r

    setup, stop, risiko_anteil = kandidat
    dist = preis - stop
    if dist <= 0:
        r["gruende"].append(f"{setup}: Preis schon unter Stop")
        return r
    for ok, txt in [(dist >= p["stop_min_atr"] * a, "Stop zu eng"), (dist <= p["stop_max_atr"] * a, "Stop zu weit"),
                    (dist / preis >= p["stop_min_pct"], f"Stop < {p['stop_min_pct']:.0%}"),
                    (dist / preis <= p["stop_max_pct"], f"Stop > {p['stop_max_pct']:.0%}")]:
        if not ok:
            r["gruende"].append(f"{setup}-Signal, aber {txt}")
            return r
    menge = min(equity * risiko_anteil / dist, cash * p["max_cash_anteil"] / preis)
    menge = int(menge * 1e6) / 1e6
    if menge * preis < HART["min_notional"]:
        r["gruende"].append(f"{setup}: Order zu klein")
        return r
    r.update(aktion="KAUFEN", setup=setup, stop=round(stop), stop_limit=round(stop * (1 - p["stop_limit_abstand"])),
             menge=menge, ziel_vorlaeufig=round(preis + p["ziel_r"] * dist))
    r["text"].append(f"SIGNAL {setup}: ~{preis:,.0f}, Stop {stop:,.0f} ({dist / preis:.2%}), "
                     f"Menge {menge:.6f} (~{menge * preis:,.0f} $, Risiko ~{menge * dist:,.2f} $)")
    return r


# ---------- Ergebnis eines Trades ----------
def ergebnis(einstieg, stop, ausstieg, menge, gebuehr):
    risiko = einstieg - stop
    r_brutto = (ausstieg - einstieg) / risiko
    r_netto = r_brutto - 2 * gebuehr * einstieg / risiko
    usd = (ausstieg - einstieg) * menge - gebuehr * (einstieg + ausstieg) * menge
    return round(r_brutto, 2), round(r_netto, 2), round(usd, 2)


# ---------- Statistik ----------
def stats(pfad):
    pfad = Path(pfad)
    if not pfad.exists():
        return ["Noch keine Trades."]
    with pfad.open(encoding="utf-8") as f:
        zeilen = [z for z in csv.DictReader(f) if z.get("r_netto")]
    if not zeilen:
        return ["Noch keine abgeschlossenen Trades."]
    out = []

    def block(name, zs):
        rr = [float(z["r_netto"]) for z in zs]
        g = [x for x in rr if x > 0]
        v = [x for x in rr if x <= 0]
        pf = sum(g) / abs(sum(v)) if v and sum(v) != 0 else float("inf")
        usd = sum(float(z.get("gewinn_usd") or 0) for z in zs)
        out.append(f"{name}: {len(rr)} Trades | Treffer {len(g) / len(rr):.0%} | Schnitt {sum(rr) / len(rr):+.2f}R | "
                   f"Summe {sum(rr):+.2f}R | Profit-Faktor {pf:.2f} | {usd:+.2f} $")

    block("GESAMT", zeilen)
    for s in sorted({z["setup"] for z in zeilen}):
        block(f"  {s}", [z for z in zeilen if z["setup"] == s])
    for reg in sorted({z.get("regime", "") for z in zeilen}):
        block(f"  Trend {reg}", [z for z in zeilen if z.get("regime", "") == reg])
    out.append(f"Verlustserie aktuell: {verlustserie(zeilen)}")
    out.append(f"Ziel beruehrt, aber nicht erreicht: "
               f"{sum(1 for z in zeilen if 'verpasst' in (z.get('notiz') or '').lower())}x")
    return out


def verlustserie(zeilen):
    n = 0
    for z in reversed(zeilen):
        if float(z["r_netto"]) <= 0:
            n += 1
        else:
            break
    return n
