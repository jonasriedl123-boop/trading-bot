#!/usr/bin/env python3
"""
Jonas' Trading-Bot. Laeuft auf GitHub alle 30 Minuten.
NUR Alpaca PAPER (Spielgeld). Kauft nur, nie Short, kein Hebel:
  - BTC/USD   wenn Bitcoin steigen soll (Setups L1, L2)
  - BITI      wenn Bitcoin fallen soll (Setup S1). BITI steigt, wenn BTC faellt. Nur zu US-Boersenzeiten.
Die KI-Ampel (daten/ki_ampel.json, schreibt Claude jeden Morgen) darf Signale sperren oder das Risiko halbieren.
experiment.py vergleicht alles und schreibt BERICHT.md.

  python3 bot.py lauf      -> normaler Lauf (handelt)
  python3 bot.py pruefen   -> nur anschauen: Konto + Kurse + Signal, KEINE Orders, nichts speichern
  python3 bot.py stats     -> Auswertung aller Trades
"""
import csv
import json
import math
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import experiment
import rechner
from rechner import WIEN, zeit

HIER = Path(__file__).resolve().parent
DATEN = HIER / "daten"
ZUSTAND = DATEN / "zustand.json"
TRADES = DATEN / "trades.csv"
PROTOKOLL = DATEN / "protokoll.csv"
AMPEL = DATEN / "ki_ampel.json"
JOURNAL = HIER / "JOURNAL.md"

TRADING = "https://paper-api.alpaca.markets"  # fest eingebaut: nur Paper, nie Echtgeld
DATA = "https://data.alpaca.markets"
SYMBOL, POS_SYMBOL = "BTC/USD", "BTCUSD"
INVERS = "BITI"  # ProShares Short Bitcoin ETF (-1x BTC pro Tag)
STAUB_USD = 5.0  # Rest unter 5 $ gilt als "keine Position"
MIN_BIS_SCHLUSS = timedelta(minutes=15)  # BITI nicht mehr kaufen, wenn die Boerse gleich schliesst
S1_WARTEN = timedelta(hours=20)  # S1-Signal bei geschlossener Boerse wartet max. so lange
WARNWOERTER = ["hack", "hacked", "exploit", "stolen", "drained", "ban ", "banned", "halts withdrawals",
               "suspends withdrawals", "insolven", "bankrupt", "sec sues", "delist", "outage", "emergency"]
TRADE_SPALTEN = ["id", "setup", "einstieg_zeit", "einstieg", "stop", "ziel", "menge", "ausstieg_zeit",
                 "ausstieg", "grund", "r_brutto", "r_netto", "gewinn_usd", "mae_r", "mfe_r", "regime",
                 "rsi_tag", "rsi_4h", "atr_pct", "symbol", "ki", "notiz"]
EREIGNISSE = []


def f(x):
    return f"{x:,.2f}" if abs(x) < 1000 else f"{x:,.0f}"


# ---------------- Alpaca ----------------
def api(methode, url, body=None, ok404=False):
    kopf = {"APCA-API-KEY-ID": os.environ["APCA_API_KEY_ID"].strip(),
            "APCA-API-SECRET-KEY": os.environ["APCA_API_SECRET_KEY"].strip(), "accept": "application/json"}
    daten = None
    if body is not None:
        daten = json.dumps(body).encode()
        kopf["content-type"] = "application/json"
    for versuch in range(3):
        req = urllib.request.Request(url, data=daten, headers=kopf, method=methode)
        try:
            with urllib.request.urlopen(req, timeout=20) as antwort:
                text = antwort.read().decode()
                return json.loads(text) if text else {}
        except urllib.error.HTTPError as e:
            if e.code == 404 and ok404:
                return None
            if e.code in (429, 500, 502, 503, 504) and versuch < 2:
                time.sleep(3)
                continue
            raise RuntimeError(f"{methode} {url} -> {e.code}: {e.read().decode()[:300]}")
        except urllib.error.URLError:
            if versuch < 2:
                time.sleep(3)
                continue
            raise


def kerzen(timeframe, tage, now):
    start = (now - timedelta(days=tage)).strftime("%Y-%m-%dT%H:%M:%SZ")
    alle, token = [], None
    while True:
        q = {"symbols": SYMBOL, "timeframe": timeframe, "start": start, "limit": 1000}
        if token:
            q["page_token"] = token
        r = api("GET", f"{DATA}/v1beta3/crypto/us/bars?" + urllib.parse.urlencode(q))
        alle += (r.get("bars") or {}).get(SYMBOL, [])
        token = r.get("next_page_token")
        if not token:
            break
    return [{"t": zeit(b["t"]), "o": b["o"], "h": b["h"], "l": b["l"], "c": b["c"]} for b in alle]


def letzter_preis():
    r = api("GET", f"{DATA}/v1beta3/crypto/us/latest/trades?" + urllib.parse.urlencode({"symbols": SYMBOL}))
    return float(r["trades"][SYMBOL]["p"])


def biti_preis():
    r = api("GET", f"{DATA}/v2/stocks/{INVERS}/trades/latest?feed=iex")
    return float(r["trade"]["p"])


def warn_news(now):
    q = {"symbols": POS_SYMBOL, "limit": 20, "start": (now - timedelta(hours=6)).strftime("%Y-%m-%dT%H:%M:%SZ")}
    r = api("GET", f"{DATA}/v1beta1/news?" + urllib.parse.urlencode(q))
    for n in r.get("news", []):
        text = f" {n.get('headline', '')} {n.get('summary', '')} ".lower()
        for w in WARNWOERTER:
            if w in text:
                return f"{w.strip()}: {n.get('headline', '')[:120]}"
    return None


def order(body):
    return api("POST", f"{TRADING}/v2/orders", body)


def warte_auf_fill(order_id, sekunden=30):
    o = None
    for _ in range(sekunden // 2):
        o = api("GET", f"{TRADING}/v2/orders/{order_id}")
        if o["status"] == "filled":
            return o
        if o["status"] in ("canceled", "rejected", "expired"):
            break
        time.sleep(2)
    return o


def setze_stop(symbol, menge, stop, stop_limit, now):
    if symbol == INVERS:  # Aktie, ganze Stueck: einfacher Stop, gilt bis zum Verkauf
        return order({"symbol": INVERS, "qty": str(int(menge)), "side": "sell", "type": "stop",
                      "time_in_force": "gtc", "stop_price": f"{stop:.2f}",
                      "client_order_id": f"bot-{now:%Y%m%d-%H%M%S}-stop"})
    qty = int(menge * 0.997 * 1e6) / 1e6  # Krypto-Gebuehr wird in BTC abgezogen -> kleiner Puffer
    return order({"symbol": SYMBOL, "qty": f"{qty:.6f}", "side": "sell", "type": "stop_limit",
                  "time_in_force": "gtc", "stop_price": str(stop), "limit_price": str(stop_limit),
                  "client_order_id": f"bot-{now:%Y%m%d-%H%M%S}-stop"})


# ---------------- KI-Ampel ----------------
def ki_ampel(now):
    """Liest die Ampel von Claude. Fehlt sie oder ist sie abgelaufen -> None (Bot handelt nur nach Regeln)."""
    try:
        amp = json.loads(AMPEL.read_text(encoding="utf-8"))
        return amp if zeit(amp["gueltig_bis"]) >= now else None
    except Exception:
        return None


def ki_check(amp, richtung, now):
    """Rueckgabe (sperre oder None, Risiko-Faktor, Label)."""
    if not amp:
        return None, 1.0, "keine"
    for s in amp.get("sperrzeiten") or []:
        try:
            if zeit(s["von"]) <= now <= zeit(s["bis"]):
                return (f"KI-Termin: {s.get('grund', '?')} (Sperre bis {zeit(s['bis']).astimezone(WIEN):%H:%M})",
                        1.0, "TERMIN")
        except Exception:
            continue
    farbe = str(amp.get(richtung, "GRUEN")).upper().replace("Ü", "UE")
    if farbe == "ROT":
        return f"KI-Ampel ROT: {str(amp.get('begruendung', ''))[:120]}", 1.0, "ROT"
    if farbe == "GELB":
        return None, 0.5, "GELB"
    return None, 1.0, "GRUEN"


# ---------------- Dateien ----------------
def lade_zustand():
    if ZUSTAND.exists():
        return json.loads(ZUSTAND.read_text(encoding="utf-8"))
    return {"position": None, "pause_bis": None, "einstiege": {"datum": "", "anzahl": 0}, "letzte_kerze": None}


def speichere_zustand(z):
    ZUSTAND.write_text(json.dumps(z, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")


def bot_aktiv():
    d = HIER / "BOT_AKTIV.txt"
    return not d.exists() or d.read_text(encoding="utf-8").strip().lower().startswith("ja")


def protokoll(now, preis, regime, aktion, grund, dedupe=False):
    zeilen = PROTOKOLL.read_text(encoding="utf-8").splitlines()[1:] if PROTOKOLL.exists() else []
    grund = str(grund).replace('"', "'")
    neu = f"{now.astimezone(WIEN):%Y-%m-%d %H:%M},{preis:.0f},{regime},{aktion},\"{grund}\""
    if dedupe and zeilen and zeilen[-1].split(",", 3)[-1] == neu.split(",", 3)[-1]:
        return  # gleiche Meldung wie zuletzt -> nicht nochmal
    zeilen.append(neu)
    EREIGNISSE.append(aktion)
    zeilen = zeilen[-1000:]
    PROTOKOLL.write_text("zeit_wien,preis,trend,aktion,grund\n" + "\n".join(zeilen) + "\n", encoding="utf-8")


def schreibe_trade(zeile):
    neu = not TRADES.exists() or not TRADES.read_text(encoding="utf-8").strip()
    with TRADES.open("a", encoding="utf-8", newline="") as d:
        w = csv.DictWriter(d, fieldnames=TRADE_SPALTEN)
        if neu:
            w.writeheader()
        w.writerow(zeile)


def journal(eintrag):
    alt = JOURNAL.read_text(encoding="utf-8") if JOURNAL.exists() else "# Journal\n\n"
    kopf, _, rest = alt.partition("<!-- NEU -->")
    JOURNAL.write_text(kopf + "<!-- NEU -->\n" + eintrag + "\n" + rest, encoding="utf-8")


# ---------------- Ablauf ----------------
def trade_abschliessen(z, ausstieg, grund, now, p, extra=""):
    t = z["position"]
    sym = t.get("symbol", POS_SYMBOL)
    gebuehr = 0.0 if sym == INVERS else p["gebuehr_pro_seite"]  # Aktien: keine Gebuehr bei Alpaca
    rb, rn, usd = rechner.ergebnis(t["einstieg"], t["stop"], ausstieg, t["menge"], gebuehr)
    nr = sum(1 for _ in TRADES.open(encoding="utf-8")) if TRADES.exists() else 1
    notiz = "; ".join(x for x in [extra, "Ziel beruehrt aber verpasst"
                                  if t.get("ziel_beruehrt") and grund != "Ziel" else ""] if x)
    schreibe_trade({"id": nr, "setup": t["setup"], "einstieg_zeit": t["zeit"], "einstieg": t["einstieg"],
                    "stop": t["stop"], "ziel": t["ziel"], "menge": t["menge"], "ausstieg_zeit": now.isoformat(),
                    "ausstieg": round(ausstieg, 2), "grund": grund, "r_brutto": rb, "r_netto": rn, "gewinn_usd": usd,
                    "mae_r": t.get("mae_r", ""), "mfe_r": t.get("mfe_r", ""), "regime": t.get("regime", ""),
                    "rsi_tag": t.get("rsi_tag", ""), "rsi_4h": t.get("rsi_4h", ""), "atr_pct": t.get("atr_pct", ""),
                    "symbol": sym, "ki": t.get("ki", "keine"), "notiz": notiz})
    journal(f"## #{nr} {t['setup']} ({sym}) | {now.astimezone(WIEN):%d.%m.%Y %H:%M} | {rn:+.2f}R netto ({usd:+.2f} $)\n"
            f"| Einstieg | Stop | Ziel | Menge | Ausstieg | Grund | KI |\n|---|---|---|---|---|---|---|\n"
            f"| {f(t['einstieg'])} | {f(t['stop'])} | {f(t['ziel'])} | {t['menge']} | {f(ausstieg)} | {grund} "
            f"| {t.get('ki', 'keine')} |\n\n"
            f"MAE {t.get('mae_r', '?')}R · MFE {t.get('mfe_r', '?')}R · Trend {t.get('regime', '?')} {notiz}\n\n"
            f"Analyse: kommt am Sonntag in ANALYSEN.md (#{nr})\n")
    z["position"] = None
    with TRADES.open(encoding="utf-8") as d:
        zeilen = [x for x in csv.DictReader(d) if x.get("r_netto")]
    if rechner.verlustserie(zeilen) >= rechner.HART["verlustserie_pause"]:
        z["pause_bis"] = (now + timedelta(hours=24)).isoformat()
    return f"{grund}: {f(ausstieg)} -> {rn:+.2f}R ({usd:+.2f} $)"


def menge_von(pos):
    if not pos or float(pos.get("market_value") or 0) < STAUB_USD:
        return 0.0
    return float(pos["qty"])


def lauf(nur_pruefen=False):
    now = datetime.now(timezone.utc)
    DATEN.mkdir(exist_ok=True)
    p = rechner.lade_parameter()
    z = lade_zustand()

    konto = api("GET", f"{TRADING}/v2/account")
    if not str(konto.get("account_number", "")).startswith("PA"):
        print("STOPP: Das ist kein Paper-Konto. Bot handelt nicht.")
        sys.exit(1)
    equity, cash = float(konto["equity"]), float(konto["cash"])
    uhr = api("GET", f"{TRADING}/v2/clock")
    bis_schluss = (zeit(uhr["next_close"]) - now) if uhr.get("next_close") else timedelta(0)
    boerse_ok = bool(uhr.get("is_open")) and bis_schluss >= MIN_BIS_SCHLUSS

    pos_btc = api("GET", f"{TRADING}/v2/positions/{POS_SYMBOL}", ok404=True)
    pos_biti = api("GET", f"{TRADING}/v2/positions/{INVERS}", ok404=True)
    m_btc, m_biti = menge_von(pos_btc), menge_von(pos_biti)
    offen = api("GET", f"{TRADING}/v2/orders?status=open&limit=100")
    preis = letzter_preis()
    tage = kerzen("1Day", 70, now)
    h4 = kerzen("4Hour", 12, now)
    print(f"Konto {konto['account_number']} | Equity {equity:,.2f} $ | Cash {cash:,.2f} $ | BTC {m_btc} | "
          f"BITI {m_biti} | BTC-Preis {preis:,.0f} | US-Boerse {'offen' if uhr.get('is_open') else 'zu'}")

    t = z["position"]
    if t and "symbol" not in t:
        t["symbol"] = POS_SYMBOL
    trade = None
    if t:
        if t["symbol"] == INVERS:
            trade = {"setup": t["setup"], "richtung": "short", "einstieg": t["einstieg_btc"], "stop": t["stop_btc"],
                     "ziel": t["ziel_btc"], "zeit": zeit(t["zeit"])}
        else:
            trade = {"setup": t["setup"], "einstieg": t["einstieg"], "stop": t["stop"], "ziel": t["ziel"],
                     "zeit": zeit(t["zeit"])}
    hat = {POS_SYMBOL: m_btc, INVERS: m_biti}
    a = rechner.analyse(tage, h4, now, p, equity, cash, preis, trade if (t and hat[t["symbol"]] > 0) else None)
    for zeile in a["text"]:
        print(zeile)
    regime = a.get("regime", "?")
    grund = " | ".join(a["gruende"])
    amp = ki_ampel(now)
    print(f"AKTION: {a['aktion']} {grund}")
    print("KI-Ampel: " + (f"steigt {amp.get('long_btc')} | faellt {amp.get('fallend_biti')} | "
                          f"{str(amp.get('begruendung', ''))[:100]}" if amp else "keine gueltige -> nur Regeln"))
    if nur_pruefen:
        print("(Pruef-Modus: keine Orders, nichts gespeichert)")
        return

    exp = experiment.start(now, equity, preis)
    try:
        handeln(z, t, a, p, now, preis, regime, grund, equity, cash, hat, pos_btc, offen, tage, h4,
                uhr, boerse_ok, amp)
    finally:
        try:  # Experiment nachfuehren - darf den Bot nie stoppen
            fertig = experiment.schatten_update(h4, now, p)
            for s in fertig:
                protokoll(now, preis, regime, "SCHATTEN",
                          f"#{s['id']} {s['setup']} (gesperrt: {s['sperre'][:50]}): {s['status']} {float(s['r']):+.2f}R")
            for pr in experiment.prognose_update(now, preis, AMPEL):
                protokoll(now, preis, regime, "PROGNOSE",
                          f"KI sagte '{pr['richtung']}', BTC {pr['aenderung']} -> {pr['ergebnis']}")
            k = a.get("letzte_kerze")
            neu_bar = k is not None and (not z.get("bericht_kerze") or zeit(z["bericht_kerze"]) < k)
            if EREIGNISSE or fertig or neu_bar or not experiment.BERICHT.exists():
                experiment.verlauf_update(now, equity, preis, exp)
                experiment.bericht(now, equity, preis, exp, z, amp, bot_aktiv())
                if k is not None:
                    z["bericht_kerze"] = k.isoformat()
                speichere_zustand(z)
        except Exception as e:
            print(f"WARNUNG Experiment/Bericht: {e!r}")


def handeln(z, t, a, p, now, preis, regime, grund, equity, cash, hat, pos_btc, offen, tage, h4, uhr, boerse_ok, amp):
    # --- Fall 0: Position, die der Bot nicht kennt -> BTC absichern; BITI melden ---
    if not t and (hat[POS_SYMBOL] > 0 or hat[INVERS] > 0):
        if hat[POS_SYMBOL] > 0:
            einstieg = float(pos_btc["avg_entry_price"])
            stop = round(einstieg * 0.97)
            z["position"] = t = {"symbol": POS_SYMBOL, "setup": "MANUELL", "einstieg": einstieg, "stop": stop,
                                 "ziel": round(einstieg + p["ziel_r"] * (einstieg - stop)), "menge": hat[POS_SYMBOL],
                                 "zeit": now.isoformat(), "stop_order_id": None, "ki": "keine"}
            trade = {"setup": "MANUELL", "einstieg": einstieg, "stop": stop, "ziel": t["ziel"], "zeit": now}
            a = rechner.analyse(tage, h4, now, p, equity, cash, preis, trade)
            grund = "BTC-Position ohne Bot-Daten gefunden, Stop 3 % darunter"
        else:
            protokoll(now, preis, regime, "WARNUNG", "BITI-Position ohne Bot-Daten - bitte von Hand pruefen", True)
            speichere_zustand(z)
            return

    # --- Fall 1: Position offen ---
    if t and hat[t["symbol"]] > 0:
        sym = t["symbol"]
        menge = hat[sym]
        t["mfe_r"], t["mae_r"] = a.get("mfe_r"), a.get("mae_r")
        t["ziel_beruehrt"] = t.get("ziel_beruehrt") or a.get("ziel_beruehrt", False)
        meine = (SYMBOL, POS_SYMBOL) if sym == POS_SYMBOL else (INVERS,)
        stops = [o for o in offen if o["side"] == "sell" and o["symbol"] in meine]
        if a["aktion"] in ("VERKAUFEN_ZIEL", "VERKAUFEN_ZEIT", "PRUEFEN_STOP"):
            if sym == INVERS and not uhr.get("is_open"):
                grund = f"{a['aktion']}, aber US-Boerse zu -> verkauft bei Oeffnung (Stop bleibt aktiv)"
            else:
                for o in stops:
                    api("DELETE", f"{TRADING}/v2/orders/{o['id']}", ok404=True)
                time.sleep(2)
                schluss = api("DELETE", f"{TRADING}/v2/positions/{sym}")
                fill = warte_auf_fill(schluss["id"]) if schluss and schluss.get("id") else None
                if fill and fill.get("filled_avg_price"):
                    ausstieg = float(fill["filled_avg_price"])
                else:
                    ausstieg = biti_preis() if sym == INVERS else preis
                g = {"VERKAUFEN_ZIEL": "Ziel", "VERKAUFEN_ZEIT": "Zeitstop", "PRUEFEN_STOP": "Stop (Markt)"}[a["aktion"]]
                grund = trade_abschliessen(z, ausstieg, g, now, p)
        elif not stops:
            sl = round(t["stop"] * (1 - p["stop_limit_abstand"])) if sym == POS_SYMBOL else None
            o = setze_stop(sym, menge, t["stop"], sl, now)
            t["stop_order_id"] = o["id"]
            grund = (grund + " | " if grund else "") + f"{sym}-Stop fehlte -> neu gesetzt"
        speichere_zustand(z)
        if a["aktion"] != "HALTEN" or "Stop" in grund:
            protokoll(now, preis, regime, a["aktion"], grund, dedupe=True)
        return

    # --- Fall 2: Position weg, Bot hatte aber eine -> Stop wurde ausgeloest ---
    if t:
        ausstieg, g = t["stop"], "unbekannt (von Hand geschlossen?)"
        if t.get("stop_order_id"):
            so = api("GET", f"{TRADING}/v2/orders/{t['stop_order_id']}", ok404=True)
            if so and so.get("status") == "filled":
                ausstieg, g = float(so["filled_avg_price"]), "Stop"
        grund = trade_abschliessen(z, ausstieg, g, now, p)
        speichere_zustand(z)
        protokoll(now, preis, regime, "GESCHLOSSEN", grund)
        return

    # --- Fall 3: keine Position ---
    kandidat, quelle = None, None
    atr = a.get("atr") or 0.0

    # 3a) S1-Signal von vorher, das auf die US-Boerse wartet
    w = z.get("s1_wartet")
    if w:
        if zeit(w["bis"]) < now:
            z["s1_wartet"] = None
            protokoll(now, preis, regime, "NICHTS", "S1-Signal verfallen (US-Boerse war zu lange zu)")
        elif boerse_ok:
            z["s1_wartet"] = None
            dist = w["stop"] - preis
            ok, txt = rechner.stop_ok(dist, preis, atr, p)
            if preis > w["signal_preis"] + 0.25 * atr:
                protokoll(now, preis, regime, "NICHTS", "S1 verworfen: Bitcoin ist seit dem Signal gestiegen")
            elif not ok:
                protokoll(now, preis, regime, "NICHTS", f"S1 verworfen: {txt}")
            else:
                kandidat = {"aktion": "KAUFEN", "setup": "S1", "richtung": "short", "stop": w["stop"],
                            "dist_pct": dist / preis, "risiko_anteil": w["risiko_anteil"],
                            "ziel_vorlaeufig": round(preis - p["ziel_r"] * dist)}
                quelle = "wartend"

    # 3b) neues Signal: nur einmal pro fertiger 4h-Kerze pruefen
    kerze = a.get("letzte_kerze")
    neue_kerze = kerze is not None and (not z.get("letzte_kerze") or zeit(z["letzte_kerze"]) < kerze)
    if neue_kerze:
        z["letzte_kerze"] = kerze.isoformat()
        if a["aktion"] == "KAUFEN":
            kandidat, quelle = a, "neu"
            z["s1_wartet"] = None  # neues Signal ersetzt ein wartendes
    if kandidat is None:
        if neue_kerze:
            protokoll(now, preis, regime, "NICHTS",
                      grund + (" | S1 wartet auf US-Boerse" if z.get("s1_wartet") else ""))
        speichere_zustand(z)
        return

    # 3c) Sperren pruefen
    s1 = kandidat["setup"] == "S1"
    heute = f"{now:%Y-%m-%d}"
    if z["einstiege"].get("datum") != heute:
        z["einstiege"] = {"datum": heute, "anzahl": 0}
    sperre, schatten, faktor, ki = None, False, 1.0, "keine"
    if not bot_aktiv():
        sperre = "Bot ausgeschaltet (BOT_AKTIV.txt)"
    elif z.get("pause_bis") and zeit(z["pause_bis"]) > now:
        sperre = f"Pause bis {zeit(z['pause_bis']).astimezone(WIEN):%d.%m. %H:%M} (Verlustserie)"
    elif equity < rechner.HART["notbremse_equity"]:
        sperre = f"NOTBREMSE: Konto {equity:.0f} $ < {rechner.HART['notbremse_equity']:.0f} $"
    elif z["einstiege"]["anzahl"] >= rechner.HART["max_einstiege_tag"]:
        sperre = "heute schon 2 Einstiege"
    if not sperre:
        s_ki, faktor, ki = ki_check(amp, "fallend_biti" if s1 else "long_btc", now)
        if s_ki:
            sperre, schatten = s_ki, True
    if not sperre and s1 and not boerse_ok:
        z["s1_wartet"] = {"stop": kandidat["stop"], "signal_preis": round(preis),
                          "risiko_anteil": kandidat["risiko_anteil"], "bis": (now + S1_WARTEN).isoformat()}
        sperre = "S1-Signal (Bitcoin faellt), US-Boerse zu -> wartet auf Oeffnung (max. 20 Std.)"
    if not sperre:
        news = warn_news(now)
        if news:
            sperre = f"Warn-News: {news}"
    if not sperre:  # Menge ausrechnen (bei KI GELB halbes Risiko)
        if s1:
            b = biti_preis()
            b_stop = round(b * (1 - kandidat["dist_pct"]), 2)
            stueck = math.floor(min(equity * kandidat["risiko_anteil"] * faktor / (b - b_stop),
                                    cash * p["max_cash_anteil"] / b))
            if stueck < 1 or stueck * b < rechner.HART["min_notional"]:
                sperre = f"S1: zu wenig Geld fuer 1 BITI ({b:.2f} $)"
            else:
                kandidat["menge"] = stueck
        else:
            m = int(kandidat["menge"] * faktor * 1e6) / 1e6
            if m * preis < rechner.HART["min_notional"]:
                sperre = f"{kandidat['setup']}: Order zu klein"
            else:
                kandidat["menge"] = m
    if sperre:
        if schatten:
            experiment.schatten_neu(now, zeit(z["letzte_kerze"]) + timedelta(hours=4), kandidat["setup"],
                                    "short" if s1 else "long", preis, kandidat["stop"], kandidat["ziel_vorlaeufig"],
                                    sperre)
        protokoll(now, preis, regime, "NICHTS", sperre)
        speichere_zustand(z)
        if sperre.startswith("NOTBREMSE"):
            print(sperre)
            sys.exit(1)  # GitHub schickt Jonas dann eine Mail
        return

    # 3d) Kaufen
    sym = INVERS if s1 else POS_SYMBOL
    if s1:
        kauf = order({"symbol": INVERS, "qty": str(kandidat["menge"]), "side": "buy", "type": "market",
                      "time_in_force": "day", "client_order_id": f"bot-{now:%Y%m%d-%H%M%S}-kauf"})
    else:
        kauf = order({"symbol": SYMBOL, "qty": f"{kandidat['menge']:.6f}", "side": "buy", "type": "market",
                      "time_in_force": "gtc", "client_order_id": f"bot-{now:%Y%m%d-%H%M%S}-kauf"})
    fill = warte_auf_fill(kauf["id"])
    if not fill or fill.get("status") != "filled":
        protokoll(now, preis, regime, "FEHLER", f"Kauf nicht ausgefuehrt: {fill and fill.get('status')}")
        speichere_zustand(z)
        sys.exit(1)
    einstieg, gekauft = round(float(fill["filled_avg_price"]), 2), float(fill["filled_qty"])
    if s1:
        stop = round(einstieg * (1 - kandidat["dist_pct"]), 2)
        ziel = round(einstieg + p["ziel_r"] * (einstieg - stop), 2)
    else:
        stop = kandidat["stop"]
        ziel = round(einstieg + p["ziel_r"] * (einstieg - stop))
    try:
        so = setze_stop(sym, gekauft, stop, kandidat.get("stop_limit"), now)
    except Exception as e:  # nie ohne Stop: sofort wieder verkaufen
        api("DELETE", f"{TRADING}/v2/positions/{sym}")
        protokoll(now, preis, regime, "FEHLER", f"Stop ging nicht ({e}) -> Position sofort geschlossen")
        speichere_zustand(z)
        sys.exit(1)
    z["position"] = {"symbol": sym, "setup": kandidat["setup"], "einstieg": einstieg, "stop": stop, "ziel": ziel,
                     "menge": gekauft, "zeit": now.isoformat(), "stop_order_id": so["id"], "kauf_order_id": kauf["id"],
                     "regime": regime, "rsi_tag": a.get("rsi_tag"), "rsi_4h": a.get("rsi_4h"),
                     "atr_pct": a.get("atr_pct"), "ki": ki, "quelle": quelle}
    if s1:
        z["position"].update(richtung="short", einstieg_btc=round(preis), stop_btc=kandidat["stop"],
                             ziel_btc=round(preis - p["ziel_r"] * (kandidat["stop"] - preis)))
    z["einstiege"]["anzahl"] += 1
    speichere_zustand(z)
    was = f"{gekauft:g} {sym} zu {f(einstieg)}, Stop {f(stop)}, Ziel {f(ziel)}, KI {ki}"
    if s1:
        was += (f" (BTC {preis:,.0f}, BTC-Stop {kandidat['stop']:,.0f}, "
                f"BTC-Ziel {z['position']['ziel_btc']:,.0f})")
    protokoll(now, preis, regime, f"KAUF {kandidat['setup']}", was)
    journal(f"## Einstieg {kandidat['setup']} ({sym}) | {now.astimezone(WIEN):%d.%m.%Y %H:%M}\n"
            f"{was} · Trend {regime} · RSI Tag {a.get('rsi_tag')} / 4h {a.get('rsi_4h')} · ATR {a.get('atr_pct')} %\n")


if __name__ == "__main__":
    modus = sys.argv[1] if len(sys.argv) > 1 else "lauf"
    DATEN.mkdir(exist_ok=True)
    if modus == "stats":
        print("\n".join(rechner.stats(TRADES)))
    elif modus in ("lauf", "pruefen"):
        lauf(nur_pruefen=(modus == "pruefen"))
    else:
        print(__doc__)
