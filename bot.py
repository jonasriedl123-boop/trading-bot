#!/usr/bin/env python3
"""
Jonas' Trading-Bot v3. Laeuft auf GitHub alle 30 Minuten. NUR Alpaca PAPER (Spielgeld).

Handelt Krypto (24/7) und US-Aktien/ETFs (Mo-Fr Boersenzeit). Fallende Kurse nur ueber inverse ETFs ohne Hebel.
Jeder Lauf: Daten holen, alle Werte bewerten, offene Positionen + Stops pruefen, beste Signale kaufen,
Schatten-Trades notieren, Meldungen per ntfy aufs Handy. Details: BOT-PLAN.md Teil B, Strategien: strategien.py.

  python3 bot.py lauf      -> normaler Lauf (handelt)
  python3 bot.py pruefen   -> nur anschauen, KEINE Orders, nichts speichern
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
from decimal import Decimal, ROUND_DOWN
from pathlib import Path

import strategien as st

try:
    from zoneinfo import ZoneInfo
    WIEN, NY = ZoneInfo("Europe/Vienna"), ZoneInfo("America/New_York")
except Exception:
    WIEN, NY = timezone(timedelta(hours=1)), timezone(timedelta(hours=-5))

# ---------- Harte Grenzen: gelten immer. Nur Jonas aendert die (nie das Lernen). ----------
HART = {
    "risiko_max": 0.02,          # max. 2 % vom Konto pro Trade
    "max_positionen": 3,
    "tageslimit": -0.03,         # -3 % an einem Tag -> heute keine neuen Trades
    "verlustserie": 3,           # 3 Verluste in Folge -> 12 Std. Pause
    "pause_std": 12,
    "sperre_nach_verlust_std": 2,  # denselben Wert 2 Std. nicht neu kaufen
    "notbremse": 425.0,          # Konto unter 425 $ -> keine neuen Trades
    "max_cash_anteil": 0.95,
    "min_krypto_usd": 10.0,
    "daten_max_alter_min": 60,   # Kurse aelter als 1 Std. -> nicht kaufen
}
HEBEL_VERBOTEN = ("SQQQ", "TQQQ", "SPXU", "SPXS", "SDS", "QID", "UPRO", "SSO", "QLD", "SBIT", "BITX")

HIER = Path(__file__).resolve().parent
DATEN = HIER / "daten"
ZUSTAND, TRADES, SCHATTEN = DATEN / "zustand.json", DATEN / "trades.csv", DATEN / "schatten.csv"
PROTOKOLL, LEBEN, AMPEL = DATEN / "protokoll.csv", DATEN / "lebenszeichen.json", DATEN / "ki_ampel.json"
NACHRICHT, BT_ERGEBNIS = DATEN / "nachricht.txt", DATEN / "backtest_ergebnis.json"
JOURNAL, BERICHT, CONFIG = HIER / "JOURNAL.md", HIER / "BERICHT.md", HIER / "config.json"

TRADING = "https://paper-api.alpaca.markets"  # fest eingebaut: nur Paper, nie Echtgeld
DATA = "https://data.alpaca.markets"
TRADE_SPALTEN = ["id", "symbol", "strategie", "lern", "einstieg_zeit", "einstieg", "stop", "ziel", "menge",
                 "ausstieg_zeit", "ausstieg", "grund", "gewinn_usd", "gebuehr_usd", "r", "mfe_r", "mae_r",
                 "trend", "rsi", "atr_pct", "uhrzeit_wien", "wochentag", "ki", "news", "punkte", "info"]
SCH_SPALTEN = ["id", "schluessel", "symbol", "strategie", "zeit", "kerze_t", "einstieg", "stop", "ziel",
               "zeit_kerzen", "warum_nicht", "status", "ausstieg", "ausstieg_zeit", "r"]
TAGE = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
WARNWOERTER = ["hack", "hacked", "exploit", "stolen", "drained", "banned", "halts withdrawals", "suspends withdrawals",
               "insolven", "bankrupt", "sec sues", "delist", "fraud", "halted"]
LOG = []


# ---------------- kleine Helfer ----------------
def zeit(s):
    d = s if isinstance(s, datetime) else datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    return (d if d.tzinfo else d.replace(tzinfo=WIEN)).astimezone(timezone.utc)


def zahl(x):
    """Deutsche Schreibweise: 2.410 / 24,15 / 0,1234"""
    x = float(x)
    if abs(x) >= 1000:
        return f"{x:,.0f}".replace(",", ".")
    if abs(x) >= 1:
        return f"{x:.2f}".replace(".", ",")
    return f"{x:.4f}".replace(".", ",")


def dez(x, n=2):
    """+4,10 statt +4.10"""
    return f"{x:+.{n}f}".replace(".", ",")


def kurz(sym):
    return sym.replace("/USD", "")


def ist_krypto(sym):
    return "/" in sym


def pos_sym(sym):
    return sym.replace("/", "")


def runde_ab(x, schritt):
    s = Decimal(str(schritt))
    return (Decimal(str(x)) / s).to_integral_value(rounding=ROUND_DOWN) * s


def preis_txt(p, schritt=None):
    if schritt:
        return str((Decimal(str(p)) / Decimal(str(schritt))).to_integral_value() * Decimal(str(schritt)))
    return f"{p:.2f}" if p >= 1 else f"{p:.4f}"


def lies_csv(pfad):
    if not pfad.exists():
        return []
    with pfad.open(encoding="utf-8") as d:
        return list(csv.DictReader(d))


def schreib_csv(pfad, spalten, zeilen):
    with pfad.open("w", encoding="utf-8", newline="") as d:
        w = csv.DictWriter(d, fieldnames=spalten, extrasaction="ignore")
        w.writeheader()
        w.writerows(zeilen)


def lade_config():
    c = json.loads(CONFIG.read_text(encoding="utf-8"))
    c["risiko_normal"] = min(float(c["risiko_normal"]), HART["risiko_max"])
    c["risiko_lern"] = min(float(c["risiko_lern"]), HART["risiko_max"])
    c["risiko_max_abstimmung"] = min(float(c.get("risiko_max_abstimmung", 0.015)), HART["risiko_max"])
    for liste in ("aktien", "neutral", "invers_aktien", "invers_krypto"):
        c[liste] = [s for s in c.get(liste, []) if s not in HEBEL_VERBOTEN]
    return c


def melden(text, prio=None):
    """Kurze Nachricht aufs Handy (ntfy). Fehler hier stoppen den Bot nie."""
    print("NTFY:", text)
    LOG.append(text)
    kanal = os.environ.get("NTFY_TOPIC") or (lade_config().get("ntfy_kanal") if CONFIG.exists() else None)
    if not kanal or os.environ.get("BOT_TEST"):
        return
    kopf = {"Title": "Trading-Bot"}
    if prio:
        kopf["Priority"] = prio
    try:
        urllib.request.urlopen(urllib.request.Request(f"https://ntfy.sh/{kanal}", data=text.encode("utf-8"),
                                                      headers=kopf, method="POST"), timeout=10)
    except Exception as e:
        print(f"WARNUNG ntfy: {e!r}")


def warnung(z, schluessel, text, now, stunden=3):
    """Gleiche Warnung max. alle 3 Std. aufs Handy."""
    alt = z.setdefault("warnungen", {}).get(schluessel)
    if not alt or zeit(alt) + timedelta(hours=stunden) <= now:
        z["warnungen"][schluessel] = now.isoformat()
        melden(text, prio="high")


def protokoll(now, aktion, text):
    zeilen = PROTOKOLL.read_text(encoding="utf-8").splitlines()[1:] if PROTOKOLL.exists() else []
    neu = f"{now.astimezone(WIEN):%Y-%m-%d %H:%M},{aktion},\"{str(text).replace(chr(34), chr(39))[:300]}\""
    if zeilen and zeilen[-1].split(",", 1)[-1] == neu.split(",", 1)[-1]:
        return
    zeilen = (zeilen + [neu])[-1500:]
    PROTOKOLL.write_text("zeit_wien,aktion,text\n" + "\n".join(zeilen) + "\n", encoding="utf-8")
    print(f"[{aktion}] {text}")


def journal(eintrag):
    alt = JOURNAL.read_text(encoding="utf-8") if JOURNAL.exists() else "# Journal (neueste oben)\n\n<!-- NEU -->\n"
    kopf, _, rest = alt.partition("<!-- NEU -->")
    JOURNAL.write_text(kopf + "<!-- NEU -->\n" + eintrag + "\n" + rest, encoding="utf-8")


def bot_aktiv():
    d = HIER / "BOT_AKTIV.txt"
    return not d.exists() or d.read_text(encoding="utf-8").strip().lower().startswith("ja")


# ---------------- Alpaca ----------------
def api(methode, url, body=None, ok404=False):
    kopf = {"APCA-API-KEY-ID": os.environ["APCA_API_KEY_ID"].strip(),
            "APCA-API-SECRET-KEY": os.environ["APCA_API_SECRET_KEY"].strip(), "accept": "application/json"}
    daten = json.dumps(body).encode() if body is not None else None
    if body is not None:
        kopf["content-type"] = "application/json"
    for versuch in range(3):
        try:
            req = urllib.request.Request(url, data=daten, headers=kopf, method=methode)
            with urllib.request.urlopen(req, timeout=20) as antwort:
                text = antwort.read().decode()
                return json.loads(text) if text else {}
        except urllib.error.HTTPError as e:
            if e.code == 404 and ok404:
                return None
            if e.code in (429, 500, 502, 503, 504) and versuch < 2:
                time.sleep(3)
                continue
            raise RuntimeError(f"{methode} {url.split('?')[0]} -> {e.code}: {e.read().decode()[:300]}")
        except urllib.error.URLError:
            if versuch < 2:
                time.sleep(3)
                continue
            raise


def _kerzen_holen(url_basis, symbole, q):
    alle, token = {s: [] for s in symbole}, None
    while True:
        qq = dict(q, symbols=",".join(symbole), limit=10000)
        if token:
            qq["page_token"] = token
        r = api("GET", url_basis + "?" + urllib.parse.urlencode(qq))
        for s, bars in (r.get("bars") or {}).items():
            alle.setdefault(s, []).extend(bars)
        token = r.get("next_page_token")
        if not token:
            break
    return {s: [{"t": zeit(b["t"]), "o": b["o"], "h": b["h"], "l": b["l"], "c": b["c"], "v": b.get("v", 0)}
                for b in bars] for s, bars in alle.items()}


def krypto_kerzen(symbole, tf, start, ende=None):
    q = {"timeframe": tf, "start": start.strftime("%Y-%m-%dT%H:%M:%SZ")}
    if ende:
        q["end"] = ende.strftime("%Y-%m-%dT%H:%M:%SZ")
    return _kerzen_holen(f"{DATA}/v1beta3/crypto/us/bars", symbole, q)


def aktien_kerzen(symbole, start, ende):
    """Tageskerzen. SIP (alle Boersen, 15 Min. verzoegert gratis), sonst IEX."""
    q = {"timeframe": "1Day", "start": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
         "end": ende.strftime("%Y-%m-%dT%H:%M:%SZ"), "adjustment": "split", "feed": "sip"}
    try:
        return _kerzen_holen(f"{DATA}/v2/stocks/bars", symbole, q)
    except RuntimeError:
        q["feed"] = "iex"
        return _kerzen_holen(f"{DATA}/v2/stocks/bars", symbole, q)


def fertige(kerzen, stunden, now):
    return [k for k in sorted(kerzen, key=lambda k: k["t"]) if k["t"] + timedelta(hours=stunden) <= now]


def letzte_preise(krypto, aktien):
    out = {}
    if krypto:
        r = api("GET", f"{DATA}/v1beta3/crypto/us/latest/trades?" + urllib.parse.urlencode({"symbols": ",".join(krypto)}))
        for s, t in (r.get("trades") or {}).items():
            out[s] = (float(t["p"]), zeit(t["t"]))
    if aktien:
        r = api("GET", f"{DATA}/v2/stocks/trades/latest?" + urllib.parse.urlencode(
            {"symbols": ",".join(aktien), "feed": "iex"}))
        for s, t in (r.get("trades") or {}).items():
            out[s] = (float(t["p"]), zeit(t["t"]))
    return out


def warn_news(sym, now):
    try:
        q = {"symbols": pos_sym(sym), "limit": 20, "start": (now - timedelta(hours=6)).strftime("%Y-%m-%dT%H:%M:%SZ")}
        r = api("GET", f"{DATA}/v1beta1/news?" + urllib.parse.urlencode(q))
    except Exception:
        return None, ""
    news = r.get("news", [])
    for n in news:
        text = f" {n.get('headline', '')} {n.get('summary', '')} ".lower()
        for w in WARNWOERTER:
            if w in text:
                return f"{w}: {n.get('headline', '')[:100]}", ""
    return None, (news[0].get("headline", "")[:120] if news else "")


def order(body):
    return api("POST", f"{TRADING}/v2/orders", body)


def warte_auf_fill(order_id, sekunden=20):
    o = None
    for _ in range(max(1, sekunden // 2)):
        o = api("GET", f"{TRADING}/v2/orders/{order_id}?nested=true")
        if o["status"] == "filled" or o["status"] in ("canceled", "rejected", "expired"):
            return o
        time.sleep(2)
    if o and o["status"] not in ("filled",):
        api("DELETE", f"{TRADING}/v2/orders/{order_id}", ok404=True)
        time.sleep(1)
        o = api("GET", f"{TRADING}/v2/orders/{order_id}?nested=true")
    return o


def assets_laden(z, cfg, now):
    """Asset-Infos (handelbar? Bruchteile? Schrittweiten) 1x pro Tag."""
    heute = f"{now:%Y-%m-%d}"
    a = z.get("assets") or {}
    if a.get("_datum") == heute:
        return a
    a = {"_datum": heute}
    for x in api("GET", f"{TRADING}/v2/assets?asset_class=crypto&status=active"):
        a[x["symbol"]] = {"ok": bool(x.get("tradable")), "min_qty": float(x.get("min_order_size") or 0),
                          "schritt": float(x.get("min_trade_increment") or 1e-9),
                          "preis_schritt": float(x.get("price_increment") or 0.01)}
    for s in cfg["aktien"] + cfg["neutral"] + cfg["invers_aktien"] + cfg["invers_krypto"]:
        x = api("GET", f"{TRADING}/v2/assets/{s}", ok404=True)
        a[s] = {"ok": bool(x and x.get("tradable") and x.get("status") == "active"),
                "bruchteil": bool(x and x.get("fractionable"))}
    z["assets"] = a
    return a


# ---------------- KI-Ampel ----------------
def ki_ampel(now):
    try:
        amp = json.loads(AMPEL.read_text(encoding="utf-8"))
        return amp if zeit(amp["gueltig_bis"]) >= now else None
    except Exception:
        return None


def ki_sperrzeit(amp, now):
    for s in (amp or {}).get("sperrzeiten") or []:
        try:
            if zeit(s["von"]) <= now <= zeit(s["bis"]):
                return f"KI-Termin: {s.get('grund', '?')} (bis {zeit(s['bis']).astimezone(WIEN):%H:%M})"
        except Exception:
            continue
    return None


def ki_farbe(amp, gruppe):
    """gruppe: krypto / aktien / fallend. Alte Schluessel (long_btc, fallend_biti) gehen auch."""
    if not amp:
        return "keine", 1.0
    alt = {"krypto": "long_btc", "fallend": "fallend_biti"}
    farbe = str(amp.get(gruppe) or amp.get(alt.get(gruppe, "")) or "GRUEN").upper().replace("Ü", "UE")
    return farbe, {"ROT": 0.0, "GELB": 0.5}.get(farbe, 1.0)


# ---------------- Zustand ----------------
def lade_zustand():
    z = json.loads(ZUSTAND.read_text(encoding="utf-8")) if ZUSTAND.exists() else {}
    if z.get("version") != 3:  # Umbau: alten Zustand aufheben, neu anfangen
        z = {"version": 3, "alt_v2": z}
    z.setdefault("positionen", {})
    z.setdefault("gesehen", {})
    return z


def speichere_zustand(z):
    ZUSTAND.write_text(json.dumps(z, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")


def gruppe_von(sym, cfg):
    for g in ("krypto", "aktien", "neutral", "invers_aktien", "invers_krypto"):
        if sym in cfg[g]:
            return g
    return "aktien"


def filter_ok(sym, cfg, filt):
    g = gruppe_von(sym, cfg)
    return {"krypto": filt["btc"] is True, "aktien": filt["spy"] is True, "neutral": True,
            "invers_aktien": filt["spy"] is False, "invers_krypto": filt["btc"] is False}[g]


def ampel_gruppe(sym, cfg):
    g = gruppe_von(sym, cfg)
    return {"krypto": "krypto", "aktien": "aktien", "neutral": "aktien"}.get(g, "fallend")


# ---------------- Trades abschliessen ----------------
def trade_abschliessen(z, sym, ausstieg, grund, now, cfg):
    t = z["positionen"].pop(sym)
    e, s, m = float(t["einstieg"]), float(t["stop"]), float(t["menge"])
    gebuehr = cfg["gebuehr_krypto"] * (e + ausstieg) * m if ist_krypto(sym) else 0.0
    usd = (ausstieg - e) * m - gebuehr
    r = usd / ((e - s) * m) if e > s and m > 0 else 0.0
    alle = lies_csv(TRADES)
    nr = len(alle) + 1
    ein = zeit(t["zeit"]).astimezone(WIEN)
    zeile = {"id": nr, "symbol": sym, "strategie": t["strategie"], "lern": "ja" if t.get("lern") else "nein",
             "einstieg_zeit": t["zeit"], "einstieg": e, "stop": s, "ziel": t["ziel"], "menge": m,
             "ausstieg_zeit": now.isoformat(), "ausstieg": round(ausstieg, 6), "grund": grund,
             "gewinn_usd": round(usd, 2), "gebuehr_usd": round(gebuehr, 2), "r": round(r, 2),
             "mfe_r": t.get("mfe_r", ""), "mae_r": t.get("mae_r", ""), "trend": t.get("trend", ""),
             "rsi": t.get("rsi", ""), "atr_pct": t.get("atr_pct", ""), "uhrzeit_wien": f"{ein:%H:%M}",
             "wochentag": TAGE[ein.weekday()], "ki": t.get("ki", ""), "news": t.get("news", ""),
             "punkte": t.get("punkte", ""), "info": t.get("info", "")}
    schreib_csv(TRADES, TRADE_SPALTEN, alle + [zeile])
    journal(f"## #{nr} {kurz(sym)} {t['strategie']}{' (Lern-Trade)' if t.get('lern') else ''} | "
            f"{now.astimezone(WIEN):%d.%m.%Y %H:%M} | {r:+.2f}R ({usd:+.2f} $)\n"
            f"Einstieg {zahl(e)} · Stop {zahl(s)} · Ziel {zahl(t['ziel'])} · Ausstieg {zahl(ausstieg)} ({grund}) · "
            f"MFE {t.get('mfe_r', '?')}R · MAE {t.get('mae_r', '?')}R · KI {t.get('ki', '?')}\n"
            f"Warum rein: {t.get('info', '')}\n")
    protokoll(now, "VERKAUF", f"{sym} {grund} {zahl(ausstieg)} -> {usd:+.2f} $ ({r:+.2f}R)")
    if t["strategie"] == "START":
        z["start_trade"] = "fertig"
        melden(f"✅ Start-Trade hat funktioniert: Kauf, Stop und Verkauf bei Alpaca ok ({usd:+.2f} $). Der Bot läuft.")
        return
    melden(f"🔴 Verkauf {kurz(sym)} {dez(usd)} $ ({dez(r, 1)}R) · {grund}")
    if r <= 0:
        z.setdefault("sperre_wert", {})[sym] = (now + timedelta(hours=HART["sperre_nach_verlust_std"])).isoformat()
    serie = 0
    for x in reversed(lies_csv(TRADES)):
        if x["strategie"] == "START":
            continue
        if float(x["r"]) <= 0:
            serie += 1
        else:
            break
    if serie >= HART["verlustserie"]:
        z["pause_bis"] = (now + timedelta(hours=HART["pause_std"])).isoformat()
        melden(f"⏸️ {serie} Verluste in Folge → 12 Std. Pause.")


def schluss_info(sym, seit):
    """Wie wurde die Position bei Alpaca geschlossen? (Stop / Ziel)"""
    q = {"status": "closed", "symbols": sym, "after": seit, "direction": "desc", "limit": 50}
    for o in api("GET", f"{TRADING}/v2/orders?" + urllib.parse.urlencode(q)) or []:
        if o.get("side") == "sell" and o.get("status") == "filled" and o.get("filled_avg_price"):
            grund = {"stop": "Stop", "stop_limit": "Stop", "limit": "Ziel"}.get(o.get("type"), "Markt")
            return float(o["filled_avg_price"]), grund
    return None, "unbekannt (von Hand?)"


def verkaufen(sym, offene):
    for o in offene:
        if o["side"] == "sell" and o["symbol"] in (sym, pos_sym(sym)):
            api("DELETE", f"{TRADING}/v2/orders/{o['id']}", ok404=True)
    time.sleep(2)
    r = api("DELETE", f"{TRADING}/v2/positions/{urllib.parse.quote(pos_sym(sym))}", ok404=True)
    fill = warte_auf_fill(r["id"], 20) if r and r.get("id") else None
    return float(fill["filled_avg_price"]) if fill and fill.get("filled_avg_price") else None


def stop_setzen(sym, menge, stop, assets, now, bruchteil=False):
    if ist_krypto(sym):
        a = assets.get(sym, {})
        qty = runde_ab(menge * 0.997, a.get("schritt", 1e-9))  # Gebuehr wird in Krypto abgezogen
        ps = a.get("preis_schritt", 0.01)
        return order({"symbol": sym, "qty": str(qty), "side": "sell", "type": "stop_limit", "time_in_force": "gtc",
                      "stop_price": preis_txt(stop, ps), "limit_price": preis_txt(stop * 0.995, ps),
                      "client_order_id": f"bot-{now:%Y%m%d%H%M%S}-{pos_sym(sym)}-stop"})
    qty = str(runde_ab(menge, 0.000001)) if bruchteil else str(int(menge))
    return order({"symbol": sym, "qty": qty, "side": "sell", "type": "stop",
                  "time_in_force": "day" if bruchteil else "gtc", "stop_price": preis_txt(stop),
                  "client_order_id": f"bot-{now:%Y%m%d%H%M%S}-{sym}-stop"})


# ---------------- Positionen verwalten ----------------
def positionen_verwalten(z, cfg, now, alp_pos, offene, preise, inds, uhr, assets, konto):
    boerse = bool(uhr.get("is_open"))
    for sym, t in list(z["positionen"].items()):
        ap = alp_pos.get(pos_sym(sym))
        rest = max(2.0, 0.02 * float(t["einstieg"]) * float(t["menge"]))  # Krypto-Gebuehr laesst Staub uebrig
        menge = float(ap["qty"]) if ap and abs(float(ap.get("market_value") or 0)) >= rest else 0.0
        if menge <= 0:  # bei Alpaca weg -> Stop oder Ziel hat ausgeloest
            aus, grund = schluss_info(sym, t["zeit"])
            trade_abschliessen(z, sym, aus if aus else float(t["stop"]), grund, now, cfg)
            continue
        preis = preise.get(sym, (float(ap.get("current_price") or t["einstieg"]), now))[0]
        e, s, ziel = float(t["einstieg"]), float(t["stop"]), float(t["ziel"])
        risiko = e - s
        k = inds.get((sym, t["art"]))
        seit = [i for i, tt in enumerate(k["t"]) if tt >= zeit(t["zeit"]) - timedelta(hours=st.STUNDEN[t["art"]])] if k else []
        hoch = max([k["h"][i] for i in seit] + [preis]) if k else preis
        tief = min([k["l"][i] for i in seit] + [preis]) if k else preis
        t["mfe_r"] = round(max(float(t.get("mfe_r") or 0), (hoch - e) / risiko), 2)
        t["mae_r"] = round(min(float(t.get("mae_r") or 0), (tief - e) / risiko), 2)
        t["menge"] = menge
        aktie = not ist_krypto(sym)
        kann = boerse or not aktie
        gleicher_tag = aktie and zeit(t["zeit"]).astimezone(NY).date() == now.astimezone(NY).date()
        ein = zeit(t["zeit"])
        if aktie:  # fertige Handelstage nach dem Kauftag
            kerzen_seit = sum(1 for tt in (k["t"] if k else []) if tt.astimezone(NY).date() > ein.astimezone(NY).date())
        else:  # fertige Kerzen, die nach dem Kauf begonnen haben
            kerzen_seit = sum(1 for tt in (k["t"] if k else []) if tt >= ein)
        grund = None
        if t["strategie"] == "START":
            if now - zeit(t["zeit"]) >= timedelta(hours=1):
                grund = "Start-Test fertig"
        elif preis >= ziel and not t.get("bracket") and not (gleicher_tag and int(konto.get("daytrade_count", 0)) >= 2):
            grund = "Ziel"
        elif kerzen_seit >= int(t["zeit_kerzen"]) and not gleicher_tag:
            grund = "Zeit"
        elif preis <= s:
            grund = "Stop (Markt)"
        if grund and kann:
            aus = verkaufen(sym, offene)
            trade_abschliessen(z, sym, aus if aus else preis, grund, now, cfg)
            continue
        # Stop pruefen: bei Krypto offene Orders mit "BTC/USD" suchen, nicht "BTCUSD"
        stops = [o for o in offene if o["side"] == "sell" and o["symbol"] in (sym, pos_sym(sym))]
        if not stops and kann:
            try:
                o = stop_setzen(sym, menge, s, assets, now, bruchteil=t.get("bruchteil", False))
                t["stop_order_id"] = o["id"]
                if not t.get("bruchteil"):
                    protokoll(now, "STOP", f"{sym}: Stop fehlte -> neu gesetzt bei {zahl(s)}")
            except Exception as ex:
                warnung(z, f"stop-{sym}", f"❌ Stop für {kurz(sym)} geht nicht: {str(ex)[:120]}", now)


def unbekannte_positionen(z, cfg, now, alp_pos, offene, assets):
    """Positionen bei Alpaca, die der Bot nicht kennt -> mit Stop 3 % absichern und uebernehmen."""
    bekannte = {pos_sym(s) for s in z["positionen"]}
    for ps, ap in alp_pos.items():
        if ps in bekannte or abs(float(ap.get("market_value") or 0)) < 5:
            continue
        sym = next((s for s in cfg["krypto"] if pos_sym(s) == ps), ps)
        if ap.get("asset_class") == "crypto" and "/" not in sym:
            sym = ps[:-3] + "/USD"
        e = float(ap["avg_entry_price"])
        z["positionen"][sym] = {"symbol": sym, "strategie": "MANUELL", "art": "4h" if ist_krypto(sym) else "tag",
                                "einstieg": e, "stop": round(e * 0.97, 6), "ziel": round(e * 1.06, 6),
                                "menge": float(ap["qty"]), "zeit": now.isoformat(), "zeit_kerzen": 12,
                                "bruchteil": not ist_krypto(sym) and float(ap["qty"]) % 1 != 0, "lern": False}
        protokoll(now, "WARNUNG", f"{sym}: Position ohne Bot-Daten gefunden -> Stop 3 % darunter")


# ---------------- Kaufen ----------------
def kaufen(z, cfg, now, k, risiko, lern, konto, assets, offene_anz):
    sym, preis = k["symbol"], k["preis"]
    equity, cash = float(konto["equity"]), float(konto["cash"])
    stop, ziel = k["stop"], k["ziel"]
    dist = preis - stop
    if dist <= 0:
        return False, "Stop ueber Preis"
    menge = equity * risiko / dist
    menge = min(menge, cash * HART["max_cash_anteil"] / preis, equity * cfg["max_anteil_pro_position"] / preis)
    cid = f"bot-{now:%Y%m%d%H%M%S}-{pos_sym(sym)}"
    bracket = bruchteil = False
    if ist_krypto(sym):
        a = assets.get(sym, {})
        qty = runde_ab(menge, a.get("schritt", 1e-9))
        if float(qty) * preis < HART["min_krypto_usd"] or float(qty) < a.get("min_qty", 0):
            return False, "Order zu klein"
        # Limit 1 % ueber dem Kurs (Schutz vor Ausreissern). Duenne Krypto-Orderbuecher -> 0,3 % war zu knapp.
        o = order({"symbol": sym, "qty": str(qty), "side": "buy", "type": "limit", "time_in_force": "ioc",
                   "limit_price": preis_txt(preis * 1.01, a.get("preis_schritt")), "client_order_id": cid})
        f0 = warte_auf_fill(o["id"], 6)
        if not f0 or float(f0.get("filled_qty") or 0) <= 0:  # nichts bekommen -> Markt-Order
            o = order({"symbol": sym, "qty": str(qty), "side": "buy", "type": "market", "time_in_force": "gtc",
                       "client_order_id": cid + "-m"})
    else:
        ganz = math.floor(menge)
        if ganz >= 1:  # ganze Stueck -> Bracket-Order (Stop + Ziel gleich bei Alpaca)
            bracket = True
            o = order({"symbol": sym, "qty": str(ganz), "side": "buy", "type": "limit", "time_in_force": "gtc",
                       "limit_price": preis_txt(preis * 1.002), "order_class": "bracket",
                       "take_profit": {"limit_price": preis_txt(ziel)}, "stop_loss": {"stop_price": preis_txt(stop)},
                       "client_order_id": cid})
        else:  # Bruchteil -> Kauf, dann Stop (Bruchteile koennen keine Bracket-Order)
            if not assets.get(sym, {}).get("bruchteil"):
                return False, "keine Bruchteile moeglich"
            bruchteil = True
            qty = runde_ab(menge, 0.001)
            if float(qty) * preis < 5:
                return False, "Order zu klein"
            o = order({"symbol": sym, "qty": str(qty), "side": "buy", "type": "limit", "time_in_force": "day",
                       "limit_price": preis_txt(preis * 1.002), "client_order_id": cid})
    fill = warte_auf_fill(o["id"], 20)
    if not fill or float(fill.get("filled_qty") or 0) <= 0:
        return False, f"Kauf nicht ausgefuehrt ({fill and fill.get('status')})"
    einstieg, gekauft = float(fill["filled_avg_price"]), float(fill["filled_qty"])
    stop_id = None
    if bracket:
        legs = fill.get("legs") or []
        stop_id = next((x["id"] for x in legs if x.get("type") in ("stop", "stop_limit")), None)
    else:
        try:
            stop_id = stop_setzen(sym, gekauft, stop, assets, now, bruchteil=bruchteil)["id"]
        except Exception as ex:  # nie ohne Stop: sofort wieder verkaufen
            api("DELETE", f"{TRADING}/v2/positions/{urllib.parse.quote(pos_sym(sym))}", ok404=True)
            melden(f"❌ Stop für {kurz(sym)} ging nicht → sofort verkauft. {str(ex)[:100]}", prio="high")
            return False, f"Stop ging nicht: {ex}"
    z["positionen"][sym] = {
        "symbol": sym, "strategie": k["strategie"], "lern": lern, "art": k["art"], "einstieg": einstieg,
        "stop": stop, "ziel": ziel, "menge": gekauft, "zeit": now.isoformat(), "zeit_kerzen": k["zeit_kerzen"],
        "stop_order_id": stop_id, "bracket": bracket, "bruchteil": bruchteil, "trend": k.get("trend"),
        "rsi": k.get("rsi"), "atr_pct": k.get("atr_pct"), "ki": k.get("ki"), "news": k.get("news", ""),
        "punkte": k.get("punkte"), "info": k.get("info"), "kerze_t": k.get("kerze_t")}
    tag = z["tag"]
    if k["strategie"] != "START":
        tag["einstiege"] += 1
    extra = " (Lern-Trade, halbes Risiko)" if lern else ""
    if k["strategie"] == "START":
        so = api("GET", f"{TRADING}/v2/orders/{stop_id}", ok404=True) if stop_id else None
        ok = ("Stop bei Alpaca ✓" if so and so.get("status") in ("new", "accepted", "pending_new", "held")
              else "⚠️ Stop nicht gefunden")
        melden(f"🧪 Start-Trade: Kauf {kurz(sym)} {zahl(einstieg)} $ ({gekauft * einstieg:.0f} $) · {ok}. "
               f"Verkauf in 1 Std.")
    else:
        melden(f"🟢 Kauf {kurz(sym)} {zahl(einstieg)} $ · Stop {zahl(stop)} · Ziel {zahl(ziel)}{extra}")
    protokoll(now, "KAUF", f"{sym} {k['strategie']}{extra}: {gekauft:g} zu {zahl(einstieg)}, Stop {zahl(stop)}, "
                           f"Ziel {zahl(ziel)}, Punkte {k.get('punkte')}, KI {k.get('ki')}")
    journal(f"## Einstieg {kurz(sym)} {k['strategie']}{extra} | {now.astimezone(WIEN):%d.%m.%Y %H:%M}\n"
            f"{gekauft:g} zu {zahl(einstieg)} · Stop {zahl(stop)} · Ziel {zahl(ziel)} · {k.get('info', '')} · "
            f"Markt-Filter {k.get('trend')} · RSI {k.get('rsi')} · ATR {k.get('atr_pct')} % · KI {k.get('ki')}\n")
    return True, ""


# ---------------- Schatten-Trades ----------------
def schatten_neu(z, k, now, warum):
    zeilen = lies_csv(SCHATTEN)
    zeilen.append({"id": len(zeilen) + 1, "schluessel": k["schluessel"], "symbol": k["symbol"],
                   "strategie": k["strategie"], "zeit": now.isoformat(), "kerze_t": k["kerze_t"],
                   "einstieg": k["preis"], "stop": round(k["stop"], 6), "ziel": round(k["ziel"], 6),
                   "zeit_kerzen": k["zeit_kerzen"], "warum_nicht": warum[:120], "status": "offen",
                   "ausstieg": "", "ausstieg_zeit": "", "r": ""})
    schreib_csv(SCHATTEN, SCH_SPALTEN, zeilen)


def schatten_update(inds, cfg):
    zeilen, fertig = lies_csv(SCHATTEN), []
    for s in zeilen:
        if s["status"] != "offen":
            continue
        art = st.ART.get(s["strategie"], "tag")
        k = inds.get((s["symbol"], art))
        if not k:
            continue
        e, stop, ziel = float(s["einstieg"]), float(s["stop"]), float(s["ziel"])
        n = 0
        for i, t in enumerate(k["t"]):
            if t <= zeit(s["kerze_t"]):
                continue
            n += 1
            aus = None
            if k["l"][i] <= stop:
                aus, g = min(stop, k["o"][i]), "Stop"
            elif k["h"][i] >= ziel:
                aus, g = ziel, "Ziel"
            elif n >= int(s["zeit_kerzen"]):
                aus, g = k["c"][i], "Zeit"
            if aus is not None:
                fee = cfg["gebuehr_krypto"] if ist_krypto(s["symbol"]) else cfg["slippage_aktie"]
                s.update(status=g, ausstieg=round(aus, 6), ausstieg_zeit=t.isoformat(),
                         r=round(((aus - e) - fee * (e + aus)) / (e - stop), 2))
                fertig.append(s)
                break
    if fertig:
        schreib_csv(SCHATTEN, SCH_SPALTEN, zeilen)
    return fertig


# ---------------- Bericht ----------------
def statistik(zeilen):
    rr = [float(z["r"]) for z in zeilen]
    if not rr:
        return "0 Trades"
    g = [x for x in rr if x > 0]
    v = [x for x in rr if x <= 0]
    pf = sum(g) / abs(sum(v)) if v and sum(v) else float("inf")
    usd = sum(float(z["gewinn_usd"]) for z in zeilen)
    return (f"{len(rr)} Trades · Treffer {len(g) / len(rr):.0%} · Schnitt {sum(rr) / len(rr):+.2f}R · "
            f"Summe {sum(rr):+.1f}R · PF {pf:.2f} · {usd:+.2f} $")


def stats_text():
    zeilen = [x for x in lies_csv(TRADES) if x["strategie"] != "START"]
    out = [f"GESAMT: {statistik(zeilen)}",
           f"  normal: {statistik([x for x in zeilen if x['lern'] == 'nein'])}",
           f"  Lern-Trades: {statistik([x for x in zeilen if x['lern'] == 'ja'])}"]
    for s in sorted({x["strategie"] for x in zeilen}):
        out.append(f"  {s}: {statistik([x for x in zeilen if x['strategie'] == s])}")
    sch = [x for x in lies_csv(SCHATTEN) if x["status"] != "offen"]
    out.append(f"Schatten-Trades (nicht genommen): {len(sch)} fertig, Summe "
               f"{sum(float(x['r']) for x in sch):+.1f}R")
    return out


def bericht(z, cfg, now, konto, filt, kandidaten, amp):
    eq = float(konto["equity"])
    start = z.get("start", {})
    s_eq = start.get("equity", 500.0)
    zeilen = [f"# Bericht – Trading-Bot v3\n",
              f"Stand: **{now.astimezone(WIEN):%d.%m.%Y %H:%M}** Wien · Paper-Konto · automatisch geschrieben\n",
              "| | Wert |", "|---|---|",
              f"| Konto | **{zahl(eq)} $** ({eq / s_eq - 1:+.1%} seit Start {start.get('datum', '?')}) |",
              f"| Ziel (+50 % in 1 Monat, sehr hoch) | {zahl(s_eq * 1.5)} $ |"]
    for name, key in (("Bitcoin halten", "btc"), ("S&P 500 (SPY) halten", "spy")):
        if start.get(key) and z.get("letzte_preise", {}).get(key):
            zeilen.append(f"| {name} | {z['letzte_preise'][key] / start[key] - 1:+.1%} |")
    zeilen += [f"| Markt-Filter | Bitcoin über 200-Tage-Schnitt: {filt['btc']} · SPY: {filt['spy']} |",
               f"| KI-Ampel | {('Krypto ' + ki_farbe(amp, 'krypto')[0] + ' · Aktien ' + ki_farbe(amp, 'aktien')[0] + ' · fallend ' + ki_farbe(amp, 'fallend')[0]) if amp else 'keine gültige'} |",
               f"| Bot | {'an' if bot_aktiv() else 'AUS (BOT_AKTIV.txt)'} |", "",
               "## Offene Positionen", ""]
    if z["positionen"]:
        zeilen += ["| Wert | Strategie | Einstieg | Stop | Ziel | seit |", "|---|---|---|---|---|---|"]
        for s, t in z["positionen"].items():
            zeilen.append(f"| {s} | {t['strategie']}{' (Lern)' if t.get('lern') else ''} | {zahl(t['einstieg'])} | "
                          f"{zahl(t['stop'])} | {zahl(t['ziel'])} | {zeit(t['zeit']).astimezone(WIEN):%d.%m. %H:%M} |")
    else:
        zeilen.append("keine")
    zeilen += ["", "## Trades", "```", *stats_text(), "```", "",
               "## Beste Kandidaten gerade (Rangliste)", "",
               "| Wert | Strategie | Signal | Punkte | Info |", "|---|---|---|---|---|"]
    for k in sorted(kandidaten, key=lambda x: -x["punkte_lern"])[:10]:
        zeilen.append(f"| {k['symbol']} | {k['strategie']} | {'JA' if k['signal'] else 'nein'} | "
                      f"{k['punkte_lern']:.2f} | {k['info']} |")
    zeilen += ["", "_Ehrlich: Ein Urteil gibt es erst nach ca. 30 Trades. +50 % im Monat schaffen auch gute Bots "
               "praktisch nie – das Risiko wird dafür nicht erhöht._", ""]
    BERICHT.write_text("\n".join(zeilen), encoding="utf-8")


# ---------------- Hauptlauf ----------------
def lauf(nur_pruefen=False):
    now = datetime.now(timezone.utc)
    DATEN.mkdir(exist_ok=True)
    cfg = lade_config()
    z = lade_zustand()
    try:
        _lauf(z, cfg, now, nur_pruefen)
    finally:
        if not nur_pruefen:
            speichere_zustand(z)  # auch bei einem Fehler: gekaufte Positionen nie vergessen


def _lauf(z, cfg, now, nur_pruefen):
    wien = now.astimezone(WIEN)

    # Lebenszeichen: war der Bot lange weg?
    if LEBEN.exists() and not nur_pruefen:
        try:
            alt = zeit(json.loads(LEBEN.read_text(encoding="utf-8"))["zeit"])
            if now - alt > timedelta(hours=3):
                melden(f"⚠️ Bot war {(now - alt).total_seconds() / 3600:.0f} Std. nicht aktiv. Jetzt läuft er wieder.")
        except Exception:
            pass

    konto = api("GET", f"{TRADING}/v2/account")
    if not str(konto.get("account_number", "")).startswith("PA"):
        melden("🛑 STOPP: Das ist kein Paper-Konto! Bot handelt nicht.", prio="urgent")
        sys.exit(1)
    equity, cash = float(konto["equity"]), float(konto["cash"])
    last_eq = float(konto.get("last_equity") or equity)
    uhr = api("GET", f"{TRADING}/v2/clock")
    boerse = bool(uhr.get("is_open"))
    bis_schluss = (zeit(uhr["next_close"]) - now) if uhr.get("next_close") else timedelta(0)
    aktien_kauf_ok = boerse and bis_schluss >= timedelta(minutes=20)

    heute = f"{wien:%Y-%m-%d}"
    if (z.get("tag") or {}).get("datum") != heute:
        z["tag"] = {"datum": heute, "einstiege": 0, "lern": False, "start_equity": equity}
    kw = f"{wien:%G-W%V}"
    if (z.get("woche") or {}).get("kw") != kw:
        z["woche"] = {"kw": kw, "equity": equity}
    z.setdefault("start", {"datum": f"{wien:%d.%m.%Y}", "equity": round(equity, 2)})

    assets = assets_laden(z, cfg, now)
    krypto = [s for s in cfg["krypto"] if assets.get(s, {}).get("ok")]
    aktien_alle = cfg["aktien"] + cfg["neutral"] + cfg["invers_aktien"] + cfg["invers_krypto"]
    aktien = [s for s in aktien_alle if assets.get(s, {}).get("ok")]
    if "SPY" not in aktien:
        aktien.append("SPY")

    alp_pos = {p["symbol"]: p for p in api("GET", f"{TRADING}/v2/positions")}
    offene = api("GET", f"{TRADING}/v2/orders?status=open&limit=500")

    # ---- Daten ----
    daten_ok, inds, preise = True, {}, {}
    try:
        roh = {"1h": krypto_kerzen(krypto, "1Hour", now - timedelta(days=6)),
               "4h": krypto_kerzen(krypto, "4Hour", now - timedelta(days=45)),
               "kt": krypto_kerzen(krypto, "1Day", now - timedelta(days=320)),
               "tag": aktien_kerzen(aktien, now - timedelta(days=380), now - timedelta(minutes=20))}
        for art, daten in roh.items():
            stunden = {"1h": 1, "4h": 4, "kt": 24, "tag": 24}[art]
            for s, k in daten.items():
                k = fertige(k, stunden, now)
                if len(k) >= 30:
                    inds[(s, "tag" if art == "kt" else art)] = st.vorberechnen(k)
        preise = letzte_preise(krypto, aktien)
    except Exception as e:
        daten_ok = False
        warnung(z, "daten", f"⚠️ Daten-Fehler, kaufe nichts: {str(e)[:150]}", now)
        protokoll(now, "FEHLER", f"Daten: {e}")

    filt = {"btc": st.ueber_200(inds.get(("BTC/USD", "tag"))), "spy": st.ueber_200(inds.get(("SPY", "tag")))}
    z["letzte_preise"] = {"btc": preise.get("BTC/USD", (None,))[0], "spy": preise.get("SPY", (None,))[0]}
    for key, sym in (("btc", "BTC/USD"), ("spy", "SPY")):
        if not z["start"].get(key) and z["letzte_preise"][key]:
            z["start"][key] = z["letzte_preise"][key]
    amp = ki_ampel(now)
    print(f"Konto {konto['account_number']} | Equity {equity:.2f} $ | Cash {cash:.2f} $ | Positionen "
          f"{list(z['positionen'])} | Boerse {'offen' if boerse else 'zu'} | Filter {filt} | Daten {len(inds)}")

    # ---- alle Werte bewerten ----
    passt = {}
    if BT_ERGEBNIS.exists():
        try:
            passt = {k: v.get("bestanden") for k, v in json.loads(BT_ERGEBNIS.read_text())["strategien"].items()}
        except Exception:
            passt = {}
    kandidaten = []
    for name, s in cfg["strategien"].items():
        art = st.ART[name]
        werte = krypto if st.GRUPPE[art] == "krypto" else [x for x in aktien if x in aktien_alle]
        for sym in werte:
            ind = inds.get((sym, art))
            if not ind:
                continue
            i = len(ind["c"]) - 1
            sg = st.signal(name, ind, i, s)
            if not sg:
                continue
            p_alt = preise.get(sym)
            alt_min = (now - p_alt[1]).total_seconds() / 60 if p_alt else 9999
            preis = p_alt[0] if p_alt else ind["c"][i]
            stop, ziel = st.ausstieg_preise(preis, sg["atr"], s)
            tag_ind = inds.get((sym, "tag"))
            kandidaten.append({
                "symbol": sym, "strategie": name, "art": art, "signal": sg["signal"], "info": sg["info"],
                "preis": preis, "stop": stop, "ziel": ziel, "zeit_kerzen": s["zeit_kerzen"],
                "kerze_t": ind["t"][i].isoformat(), "schluessel": f"{sym}|{name}|{ind['t'][i]:%Y%m%d%H}",
                "rsi": sg["rsi"], "atr_pct": round(sg["atr"] / preis * 100, 2), "frisch": alt_min <= HART["daten_max_alter_min"],
                "filter": filter_ok(sym, cfg, filt),
                "strategie_ok": bool(s.get("aktiv")) and name not in cfg.get("nur_schatten", [])
                and (bool(passt.get(name)) or name in cfg.get("freigegeben", [])),
                "trend": "AUF" if filter_ok(sym, cfg, filt) else "AB",
                "punkte": st.punkte(sg, ind, i, tag_ind, float(s.get("gewicht", 1))),
                "punkte_lern": st.punkte(sg, ind, i, tag_ind, 1.0, lern=True), "staerke": sg["staerke"]})
    # KI-Tipps ("beobachten" in der KI-Ampel): kleiner Bonus in der Rangliste
    tipps = {}
    for t in (amp or {}).get("beobachten") or []:
        if isinstance(t, dict) and t.get("symbol") in krypto + aktien and t.get("richtung", "steigt") == "steigt":
            tipps[t["symbol"]] = str(t.get("grund", ""))[:80]
    for k in kandidaten:
        if k["symbol"] in tipps:
            k["punkte"] = round(k["punkte"] + 0.1, 4)
            k["punkte_lern"] = round(k["punkte_lern"] + 0.1, 4)
            k["info"] += f" | KI-Tipp: {tipps[k['symbol']]}"
    signale = [k for k in kandidaten if k["signal"]]
    print(f"{len(kandidaten)} Bewertungen, {len(signale)} Signale: "
          + ", ".join(f"{k['symbol']} {k['strategie']}" for k in signale[:15]))
    if nur_pruefen:
        for k in sorted(kandidaten, key=lambda x: -x["punkte_lern"])[:15]:
            print(f"  {k['symbol']:9} {k['strategie']:16} Signal {k['signal']!s:5} Punkte {k['punkte']:.2f} "
                  f"nah {k['punkte_lern']:.2f} Filter {k['filter']} | {k['info']}")
        print("(Pruef-Modus: keine Orders, nichts gespeichert)")
        return

    # ---- offene Positionen ----
    unbekannte_positionen(z, cfg, now, alp_pos, offene, assets)
    positionen_verwalten(z, cfg, now, alp_pos, offene, preise, inds, uhr, assets, konto)

    # ---- Sperren ----
    sperre = None
    if not bot_aktiv():
        sperre = "Bot ausgeschaltet (BOT_AKTIV.txt)"
    elif equity < HART["notbremse"]:
        sperre = f"NOTBREMSE: Konto {equity:.0f} $ < {HART['notbremse']:.0f} $"
        warnung(z, "notbremse", f"🛑 Notbremse: Konto {zahl(equity)} $ (unter 425 $). Keine neuen Trades. "
                                f"Bitte sag Claude, wie es weitergehen soll.", now, stunden=24)
    elif last_eq > 0 and equity / last_eq - 1 <= HART["tageslimit"]:
        sperre = f"Tageslimit: {equity / last_eq - 1:.1%} heute"
        warnung(z, "tageslimit", f"⏸️ Heute {equity / last_eq - 1:.1%} → keine neuen Trades bis morgen.", now, 12)
    elif z.get("pause_bis") and zeit(z["pause_bis"]) > now:
        sperre = f"Pause bis {zeit(z['pause_bis']).astimezone(WIEN):%d.%m. %H:%M} (Verlustserie)"
    elif not daten_ok:
        sperre = "Daten-Fehler"
    elif ki_sperrzeit(amp, now):
        sperre = ki_sperrzeit(amp, now)

    # ---- Start-Trade (einmalig nach dem Umbau) ----
    if not z.get("start_trade") and not sperre and "BTC/USD" in krypto and "BTC/USD" not in z["positionen"]:
        p = preise.get("BTC/USD", (None,))[0]
        if p:
            k = {"symbol": "BTC/USD", "strategie": "START", "art": "1h", "preis": p, "stop": p * 0.97,
                 "ziel": p * 1.5, "zeit_kerzen": 99, "info": "Test, ob Kauf + Stop + Verkauf klappen", "ki": "-"}
            usd = max(cfg["start_trade_usd"], assets.get("BTC/USD", {}).get("min_qty", 0) * p * 1.1, 11)
            menge_risiko = usd / p * (p - k["stop"]) / equity
            ok, warum = kaufen(z, cfg, now, k, menge_risiko, False, konto, assets, len(z["positionen"]))
            z["start_trade"] = "offen" if ok else f"fehler: {warum}"
            if not ok:
                melden(f"❌ Start-Trade ging nicht: {warum}", prio="high")

    # ---- neue Trades: beste Signale zuerst ----
    def blockiert(k):
        sym = k["symbol"]
        if sym in z["positionen"]:
            return "schon drin"
        if len(z["positionen"]) >= HART["max_positionen"]:
            return "max. 3 Positionen"
        if sym in cfg.get("gesperrte_werte", []) or sym in ((amp or {}).get("gesperrt") or []):
            return "Wert gesperrt"
        sw = z.get("sperre_wert", {}).get(sym)
        if sw and zeit(sw) > now:
            return "2 Std. Pause nach Verlust"
        if not k["frisch"]:
            return "Kurs aelter als 1 Std."
        if not ist_krypto(sym) and not aktien_kauf_ok:
            return "US-Boerse zu"
        if not ist_krypto(sym) and int(konto.get("daytrade_count", 0)) >= 3:
            return "PDT-Regel: 3 Daytrades"
        if z["tag"]["einstiege"] >= cfg["max_einstiege_tag"]:
            return "max. Einstiege heute"
        farbe, faktor = ki_farbe(amp, ampel_gruppe(sym, cfg))
        if faktor == 0:
            return f"KI-Ampel ROT ({ampel_gruppe(sym, cfg)})"
        return None

    gesehen = z["gesehen"]
    for s_key in list(gesehen):
        if zeit(gesehen[s_key]) < now - timedelta(days=7):
            del gesehen[s_key]
    n_gesperrt = {}
    for k in sorted(signale, key=lambda x: -x["punkte"]):
        if k["schluessel"] in gesehen:
            continue
        warum = sperre or (None if k["filter"] else "Markt-Filter") or (
            None if k["strategie_ok"] else "Strategie hat den Backtest nicht bestanden") or blockiert(k)
        if warum and warum.startswith(("US-Boerse", "Kurs aelter", "KI-Termin", "Daten")):
            continue  # nur kurz gesperrt -> naechster Lauf probiert es wieder
        if not warum:
            news, schlagzeile = warn_news(k["symbol"], now)
            k["news"] = schlagzeile
            warum = f"Warn-News: {news}" if news else None
        if not warum:
            farbe, faktor = ki_farbe(amp, ampel_gruppe(k["symbol"], cfg))
            k["ki"] = farbe
            risiko = cfg["risiko_normal"]
            if k["strategie"] in ("breakout_4h", "breakout_1h"):  # Abstimmung: mehr Zustimmung = mehr Risiko
                risiko = 0.005 + (cfg["risiko_max_abstimmung"] - 0.005) * k["staerke"]
            risiko = min(risiko * faktor, HART["risiko_max"])
            ok, warum = kaufen(z, cfg, now, k, risiko, False, konto, assets, len(z["positionen"]))
            if ok:
                gesehen[k["schluessel"]] = now.isoformat()
                konto = api("GET", f"{TRADING}/v2/account")
                continue
        gesehen[k["schluessel"]] = now.isoformat()
        schatten_neu(z, k, now, warum)
        n_gesperrt.setdefault(warum, []).append(f"{kurz(k['symbol'])} {k['strategie']}")
    for warum, liste in n_gesperrt.items():
        protokoll(now, "NICHT", f"{warum}: {len(liste)} Signale -> Schatten ({', '.join(liste[:6])}"
                                f"{' ...' if len(liste) > 6 else ''})")

    # ---- Lern-Trades: bis zu N pro Tag zu festen Uhrzeiten (zusaetzlich zu normalen Trades) ----
    zeiten = [int(x) for x in cfg.get("lern_zeiten_wien", [cfg.get("lern_trade_ab_wien", 20)])]
    lern_n = int(z["tag"].get("lern_n", 0))
    normal_n = z["tag"]["einstiege"] - lern_n
    faellig = sum(1 for h in zeiten if wien.hour >= h)
    if lern_n < faellig and (normal_n == 0 or not cfg.get("lern_nur_ohne_normal", False)):
        if sperre:
            protokoll(now, "LERN", f"Lern-Trade gerade nicht moeglich: {sperre}")
        else:
            moegliche = [k for k in kandidaten if not blockiert(k) and k["strategie"] not in cfg.get("nur_schatten", [])]
            if moegliche:
                k = max(moegliche, key=lambda x: x["punkte_lern"])
                news, k["news"] = warn_news(k["symbol"], now)
                if news:
                    protokoll(now, "LERN", f"{k['symbol']}: Warn-News {news}")
                else:
                    farbe, faktor = ki_farbe(amp, ampel_gruppe(k["symbol"], cfg))
                    k["ki"] = farbe
                    ok, warum = kaufen(z, cfg, now, k, cfg["risiko_lern"] * faktor, True, konto, assets,
                                       len(z["positionen"]))
                    if ok:
                        z["tag"]["lern_n"] = lern_n + 1
                        z["tag"]["lern"] = True
                    else:
                        protokoll(now, "LERN", f"{k['symbol']}: {warum}")
            else:
                protokoll(now, "LERN", "gerade kein moeglicher Kandidat")

    # ---- KI-Tipps als eigene Schatten-Trades (1x pro Tag und Wert): waren die News-Tipps gut? ----
    for sym, grund in tipps.items():
        ind = inds.get((sym, "tag"))
        schl = f"{sym}|news_tipp|{heute}"
        if not ind or schl in z["gesehen"] or ind["atr"][-1] is None:
            continue
        preis = preise.get(sym, (ind["c"][-1],))[0]
        s_tipp = {"stop_atr": 1.5, "ziel_r": 2.0}
        stop, ziel = st.ausstieg_preise(preis, ind["atr"][-1], s_tipp)
        z["gesehen"][schl] = now.isoformat()
        schatten_neu(z, {"schluessel": schl, "symbol": sym, "strategie": "news_tipp", "kerze_t": ind["t"][-1].isoformat(),
                         "preis": preis, "stop": stop, "ziel": ziel, "zeit_kerzen": 5}, now, f"News-Tipp: {grund}")
        protokoll(now, "TIPP", f"{sym}: KI-Tipp als Schatten-Trade notiert ({grund})")

    # ---- Schatten nachrechnen ----
    for s in schatten_update(inds, cfg):
        protokoll(now, "SCHATTEN", f"#{s['id']} {s['symbol']} {s['strategie']} ({s['warum_nicht'][:40]}): "
                                   f"{s['status']} {float(s['r']):+.2f}R")

    # ---- Meldungen ----
    if NACHRICHT.exists() and NACHRICHT.read_text(encoding="utf-8").strip():
        melden(NACHRICHT.read_text(encoding="utf-8").strip()[:1500])
        NACHRICHT.write_text("", encoding="utf-8")
    konto = api("GET", f"{TRADING}/v2/account")
    equity = float(konto["equity"])
    if wien.hour >= 21 and z.get("abend") != heute:
        z["abend"] = heute
        n = sum(1 for x in lies_csv(TRADES) if x["strategie"] != "START"
                and zeit(x["ausstieg_zeit"]).astimezone(WIEN).date().isoformat() == heute)
        melden(f"📊 Heute {z['tag']['einstiege']} Käufe, {n} Verkäufe · Konto {zahl(equity)} $ "
               f"({dez((equity / z['tag']['start_equity'] - 1) * 100, 1)} %) · "
               f"Woche {dez((equity / z['woche']['equity'] - 1) * 100, 1)} %")
    bericht(z, cfg, now, konto, filt, kandidaten, amp)


def main():
    modus = sys.argv[1] if len(sys.argv) > 1 else "lauf"
    DATEN.mkdir(exist_ok=True)
    if modus == "stats":
        print("\n".join(stats_text()))
        return
    if modus not in ("lauf", "pruefen"):
        print(__doc__)
        return
    now = datetime.now(timezone.utc)
    status = "ok"
    try:
        lauf(nur_pruefen=(modus == "pruefen"))
    except SystemExit:
        status = "stopp"
        raise
    except Exception as e:
        status = f"fehler: {str(e)[:200]}"
        z = lade_zustand()
        warnung(z, "absturz", f"❌ Bot-Fehler: {str(e)[:160]}", now)
        speichere_zustand(z)
        protokoll(now, "FEHLER", repr(e))
        raise
    finally:
        if modus == "lauf":
            LEBEN.write_text(json.dumps({"zeit": now.isoformat(), "wien": f"{now.astimezone(WIEN):%d.%m.%Y %H:%M}",
                                         "status": status}, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
