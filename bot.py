#!/usr/bin/env python3
"""
Jonas' Trading-Bot. Laeuft auf GitHub alle 30 Minuten.
NUR Alpaca PAPER (Spielgeld), nur BTC/USD, nur Long.

  python3 bot.py lauf      -> normaler Lauf (handelt)
  python3 bot.py pruefen   -> nur anschauen: Konto + Kurse + Signal, KEINE Orders, nichts speichern
  python3 bot.py stats     -> Auswertung aller Trades
"""
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import rechner

HIER = Path(__file__).resolve().parent
DATEN = HIER / "daten"
ZUSTAND = DATEN / "zustand.json"
TRADES = DATEN / "trades.csv"
PROTOKOLL = DATEN / "protokoll.csv"
JOURNAL = HIER / "JOURNAL.md"

TRADING = "https://paper-api.alpaca.markets"  # fest eingebaut: nur Paper, nie Echtgeld
DATA = "https://data.alpaca.markets"
SYMBOL, POS_SYMBOL = "BTC/USD", "BTCUSD"
STAUB_USD = 5.0  # Rest-BTC unter 5 $ gilt als "keine Position"
WARNWOERTER = ["hack", "hacked", "exploit", "stolen", "drained", "ban ", "banned", "halts withdrawals",
               "suspends withdrawals", "insolven", "bankrupt", "sec sues", "delist", "outage", "emergency"]
TRADE_SPALTEN = ["id", "setup", "einstieg_zeit", "einstieg", "stop", "ziel", "menge", "ausstieg_zeit",
                 "ausstieg", "grund", "r_brutto", "r_netto", "gewinn_usd", "mae_r", "mfe_r", "regime",
                 "rsi_tag", "rsi_4h", "atr_pct", "notiz"]


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


def zeit(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)


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


def setze_stop(menge, stop, stop_limit, now):
    qty = int(menge * 0.997 * 1e6) / 1e6  # Gebuehr wird in BTC abgezogen -> kleiner Puffer
    return order({"symbol": SYMBOL, "qty": f"{qty:.6f}", "side": "sell", "type": "stop_limit",
                  "time_in_force": "gtc", "stop_price": str(stop), "limit_price": str(stop_limit),
                  "client_order_id": f"bot-{now:%Y%m%d-%H%M%S}-stop"})


# ---------------- Dateien ----------------
def lade_zustand():
    if ZUSTAND.exists():
        return json.loads(ZUSTAND.read_text(encoding="utf-8"))
    return {"position": None, "pause_bis": None, "einstiege": {"datum": "", "anzahl": 0}, "letzte_kerze": None}


def speichere_zustand(z):
    ZUSTAND.write_text(json.dumps(z, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")


def bot_aktiv():
    f = HIER / "BOT_AKTIV.txt"
    return not f.exists() or f.read_text(encoding="utf-8").strip().lower().startswith("ja")


def protokoll(now, preis, regime, aktion, grund):
    neu = not PROTOKOLL.exists()
    zeilen = [] if neu else PROTOKOLL.read_text(encoding="utf-8").splitlines()[1:]
    wien = now + timedelta(hours=1)  # MEZ (im Sommer 1 Std. daneben - egal fuers Protokoll)
    zeilen.append(f"{wien:%Y-%m-%d %H:%M},{preis:.0f},{regime},{aktion},\"{grund}\"")
    zeilen = zeilen[-500:]
    PROTOKOLL.write_text("zeit_wien,preis,trend,aktion,grund\n" + "\n".join(zeilen) + "\n", encoding="utf-8")


def schreibe_trade(zeile):
    neu = not TRADES.exists() or not TRADES.read_text(encoding="utf-8").strip()
    with TRADES.open("a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=TRADE_SPALTEN)
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
    rb, rn, usd = rechner.ergebnis(t["einstieg"], t["stop"], ausstieg, t["menge"], p["gebuehr_pro_seite"])
    nr = sum(1 for _ in TRADES.open(encoding="utf-8")) if TRADES.exists() else 1
    notiz = "; ".join(x for x in [extra, "Ziel beruehrt aber verpasst" if t.get("ziel_beruehrt") and grund != "Ziel" else ""] if x)
    schreibe_trade({"id": nr, "setup": t["setup"], "einstieg_zeit": t["zeit"], "einstieg": t["einstieg"],
                    "stop": t["stop"], "ziel": t["ziel"], "menge": t["menge"], "ausstieg_zeit": now.isoformat(),
                    "ausstieg": round(ausstieg, 2), "grund": grund, "r_brutto": rb, "r_netto": rn, "gewinn_usd": usd,
                    "mae_r": t.get("mae_r", ""), "mfe_r": t.get("mfe_r", ""), "regime": t.get("regime", ""),
                    "rsi_tag": t.get("rsi_tag", ""), "rsi_4h": t.get("rsi_4h", ""), "atr_pct": t.get("atr_pct", ""),
                    "notiz": notiz})
    journal(f"## #{nr} {t['setup']} | {now:%d.%m.%Y} | {rn:+.2f}R netto ({usd:+.2f} $)\n"
            f"| Einstieg | Stop | Ziel | Menge | Ausstieg | Grund |\n|---|---|---|---|---|---|\n"
            f"| {t['einstieg']:,.0f} | {t['stop']:,.0f} | {t['ziel']:,.0f} | {t['menge']} | {ausstieg:,.0f} | {grund} |\n\n"
            f"MAE {t.get('mae_r', '?')}R · MFE {t.get('mfe_r', '?')}R · Trend {t.get('regime', '?')} · {notiz}\n\n"
            f"**Analyse (Claude, Sonntag):** _offen_\n")
    z["position"] = None
    with TRADES.open(encoding="utf-8") as f:
        zeilen = [x for x in csv.DictReader(f) if x.get("r_netto")]
    if rechner.verlustserie(zeilen) >= rechner.HART["verlustserie_pause"]:
        z["pause_bis"] = (now + timedelta(hours=24)).isoformat()
    return f"{grund}: {ausstieg:,.0f} -> {rn:+.2f}R ({usd:+.2f} $)"


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

    pos = api("GET", f"{TRADING}/v2/positions/{POS_SYMBOL}", ok404=True)
    menge = float(pos["qty"]) if pos else 0.0
    if pos and float(pos.get("market_value") or 0) < STAUB_USD:
        menge = 0.0
    offen = [o for o in api("GET", f"{TRADING}/v2/orders?status=open&limit=100")
             if o["symbol"] in (SYMBOL, POS_SYMBOL)]
    preis = letzter_preis()
    tage = kerzen("1Day", 70, now)
    h4 = kerzen("4Hour", 12, now)
    print(f"Konto {konto['account_number']} | Equity {equity:,.2f} $ | Cash {cash:,.2f} $ | BTC {menge} | Preis {preis:,.0f}")

    t = z["position"]
    trade = None
    if t:
        trade = {"setup": t["setup"], "einstieg": t["einstieg"], "stop": t["stop"], "ziel": t["ziel"], "zeit": zeit(t["zeit"])}
    a = rechner.analyse(tage, h4, now, p, equity, cash, preis, trade if menge > 0 else None)
    for zeile in a["text"]:
        print(zeile)
    regime = a.get("regime", "?")
    grund = " | ".join(a["gruende"])
    print(f"AKTION: {a['aktion']} {grund}")
    if nur_pruefen:
        print("(Pruef-Modus: keine Orders, nichts gespeichert)")
        return

    # --- Fall 1: Position offen ---
    if menge > 0:
        if not t:  # Position ohne Daten (z. B. von Hand gekauft) -> absichern
            einstieg = float(pos["avg_entry_price"])
            stop = round(einstieg * 0.97)
            z["position"] = t = {"setup": "MANUELL", "einstieg": einstieg, "stop": stop,
                                 "ziel": round(einstieg + p["ziel_r"] * (einstieg - stop)), "menge": menge,
                                 "zeit": now.isoformat(), "stop_order_id": None}
            grund = "Position ohne Bot-Daten gefunden, Stop 3 % darunter gesetzt"
        t["mfe_r"], t["mae_r"] = a.get("mfe_r"), a.get("mae_r")
        t["ziel_beruehrt"] = t.get("ziel_beruehrt") or a.get("ziel_beruehrt", False)
        stops = [o for o in offen if o["side"] == "sell"]
        if a["aktion"] in ("VERKAUFEN_ZIEL", "VERKAUFEN_ZEIT", "PRUEFEN_STOP"):
            for o in stops:
                api("DELETE", f"{TRADING}/v2/orders/{o['id']}", ok404=True)
            time.sleep(2)
            schluss = api("DELETE", f"{TRADING}/v2/positions/{POS_SYMBOL}")
            fill = warte_auf_fill(schluss["id"]) if schluss and schluss.get("id") else None
            ausstieg = float(fill["filled_avg_price"]) if fill and fill.get("filled_avg_price") else preis
            g = {"VERKAUFEN_ZIEL": "Ziel", "VERKAUFEN_ZEIT": "Zeitstop", "PRUEFEN_STOP": "Stop (Markt)"}[a["aktion"]]
            grund = trade_abschliessen(z, ausstieg, g, now, p)
        elif not stops:
            o = setze_stop(menge, t["stop"], round(t["stop"] * (1 - p["stop_limit_abstand"])), now)
            t["stop_order_id"] = o["id"]
            grund = (grund + " | " if grund else "") + "Stop fehlte -> neu gesetzt"
        speichere_zustand(z)
        if a["aktion"] != "HALTEN" or "Stop" in grund:
            protokoll(now, preis, regime, a["aktion"], grund)
        return

    # --- Fall 2: Position weg, Bot hatte aber eine -> Stop wurde ausgeloest ---
    if t:
        ausstieg, g = preis, "unbekannt (von Hand geschlossen?)"
        if t.get("stop_order_id"):
            so = api("GET", f"{TRADING}/v2/orders/{t['stop_order_id']}", ok404=True)
            if so and so.get("status") == "filled":
                ausstieg, g = float(so["filled_avg_price"]), "Stop"
        grund = trade_abschliessen(z, ausstieg, g, now, p)
        speichere_zustand(z)
        protokoll(now, preis, regime, "GESCHLOSSEN", grund)
        return

    # --- Fall 3: keine Position -> neues Signal nur einmal pro fertiger 4h-Kerze ---
    kerze = a.get("letzte_kerze")
    if kerze is None or (z.get("letzte_kerze") and zeit(z["letzte_kerze"]) >= kerze):
        return  # diese Kerze wurde schon geprueft
    z["letzte_kerze"] = kerze.isoformat()
    heute = f"{now:%Y-%m-%d}"
    if z["einstiege"].get("datum") != heute:
        z["einstiege"] = {"datum": heute, "anzahl": 0}

    sperre = None
    if not bot_aktiv():
        sperre = "Bot ausgeschaltet (BOT_AKTIV.txt)"
    elif z.get("pause_bis") and zeit(z["pause_bis"]) > now:
        sperre = f"Pause bis {z['pause_bis'][:16]} (Verlustserie)"
    elif equity < rechner.HART["notbremse_equity"]:
        sperre = f"NOTBREMSE: Konto {equity:.0f} $ < {rechner.HART['notbremse_equity']:.0f} $"
    elif z["einstiege"]["anzahl"] >= rechner.HART["max_einstiege_tag"]:
        sperre = "heute schon 2 Einstiege"

    if a["aktion"] == "KAUFEN" and not sperre:
        news = warn_news(now)
        if news:
            sperre = f"Warn-News: {news}"
    if a["aktion"] != "KAUFEN" or sperre:
        protokoll(now, preis, regime, "NICHTS", sperre or grund)
        speichere_zustand(z)
        if sperre and sperre.startswith("NOTBREMSE"):
            print(sperre)
            sys.exit(1)  # GitHub schickt Jonas dann eine Mail
        return

    # --- Kaufen ---
    kauf = order({"symbol": SYMBOL, "qty": f"{a['menge']:.6f}", "side": "buy", "type": "market",
                  "time_in_force": "gtc", "client_order_id": f"bot-{now:%Y%m%d-%H%M%S}-kauf"})
    fill = warte_auf_fill(kauf["id"])
    if not fill or fill.get("status") != "filled":
        protokoll(now, preis, regime, "FEHLER", f"Kauf nicht ausgefuehrt: {fill and fill.get('status')}")
        speichere_zustand(z)
        sys.exit(1)
    einstieg, gekauft = round(float(fill["filled_avg_price"]), 2), float(fill["filled_qty"])
    stop = a["stop"]
    try:
        so = setze_stop(gekauft, stop, a["stop_limit"], now)
    except Exception as e:  # nie ohne Stop: sofort wieder verkaufen
        api("DELETE", f"{TRADING}/v2/positions/{POS_SYMBOL}")
        protokoll(now, preis, regime, "FEHLER", f"Stop ging nicht ({e}) -> Position sofort geschlossen")
        speichere_zustand(z)
        sys.exit(1)
    ziel = round(einstieg + p["ziel_r"] * (einstieg - stop))
    z["position"] = {"setup": a["setup"], "einstieg": einstieg, "stop": stop, "stop_limit": a["stop_limit"],
                     "ziel": ziel, "menge": gekauft, "zeit": now.isoformat(), "stop_order_id": so["id"],
                     "kauf_order_id": kauf["id"], "regime": regime, "rsi_tag": a.get("rsi_tag"),
                     "rsi_4h": a.get("rsi_4h"), "atr_pct": a.get("atr_pct")}
    z["einstiege"]["anzahl"] += 1
    speichere_zustand(z)
    protokoll(now, einstieg, regime, f"KAUF {a['setup']}",
              f"{gekauft} BTC zu {einstieg:,.0f}, Stop {stop:,.0f}, Ziel {ziel:,.0f}")
    journal(f"## Einstieg {a['setup']} | {now:%d.%m.%Y %H:%M} UTC\n"
            f"{gekauft} BTC zu {einstieg:,.0f} $ · Stop {stop:,.0f} · Ziel {ziel:,.0f} · Trend {regime} · "
            f"RSI Tag {a.get('rsi_tag')} / 4h {a.get('rsi_4h')} · ATR {a.get('atr_pct')} %\n")


if __name__ == "__main__":
    modus = sys.argv[1] if len(sys.argv) > 1 else "lauf"
    DATEN.mkdir(exist_ok=True)
    if modus == "stats":
        print("\n".join(rechner.stats(TRADES)))
    elif modus in ("lauf", "pruefen"):
        lauf(nur_pruefen=(modus == "pruefen"))
    else:
        print(__doc__)
