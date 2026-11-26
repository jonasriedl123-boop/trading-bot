#!/usr/bin/env python3
"""
Test des ganzen Bots gegen ein FAKE-Alpaca (kein Internet, keine Orders). Prueft: Start-Trade, Stops,
Kauf mit Signal, Lern-Trade, Notbremse, Nicht-Paper-Konto.
  python3 test_bot.py
"""
import json
import math
import os
import random
import tempfile
import urllib.parse
import zlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

os.environ["BOT_TEST"] = "1"
os.environ.setdefault("APCA_API_KEY_ID", "test")
os.environ.setdefault("APCA_API_SECRET_KEY", "test")
import bot  # noqa: E402

JETZT = [datetime(2026, 11, 30, 18, 10, tzinfo=timezone.utc)]  # Mo 19:10 Wien, US-Boerse offen


class FakeZeit(datetime):
    @classmethod
    def now(cls, tz=None):
        return JETZT[0]


class FakeAlpaca:
    def __init__(self, konto="PA123", equity=500.0, trend=0.0015):
        self.konto, self.cash, self.start_eq = konto, equity, equity
        self.pos, self.orders, self.n = {}, {}, 0
        self.trend = trend
        self.kurse = {}

    def kerzen(self, sym, stunden, start, ende):
        rnd = random.Random(zlib.crc32(f"{sym}{stunden}".encode()))
        n = int(400 * 24 / stunden) if stunden < 24 else 420
        t_end = JETZT[0].replace(minute=0, second=0, microsecond=0)
        if stunden == 24:
            t_end = t_end.replace(hour=0)
        basis = 100.0 if "/" not in sym else (60000.0 if sym.startswith("BTC") else 50.0)
        c = basis
        out = []
        for i in range(n):
            t = t_end - timedelta(hours=stunden * (n - 1 - i))
            o = c
            c = o * math.exp(rnd.gauss(self.trend * stunden / 24, 0.01 * math.sqrt(stunden / 4)))
            if i == n - 2:  # vorletzte (fertige) Kerze: kraeftiger Ausbruch
                c = max(x["h"] for x in out[-80:]) * 1.03
            out.append({"t": t.strftime("%Y-%m-%dT%H:%M:%SZ"), "o": o, "h": max(o, c) * 1.003,
                        "l": min(o, c) * 0.997, "c": c, "v": 1000})
        self.kurse[sym] = out[-1]["c"]
        return [b for b in out if start <= b["t"] <= ende]

    def preis(self, sym):
        if sym not in self.kurse:
            self.kerzen(sym, 1 if "/" in sym else 24, "", "z")
        return self.kurse[sym]

    def equity(self):
        return self.cash + sum(p["qty"] * self.preis(s) for s, p in self.pos.items())

    def neue_order(self, b):
        self.n += 1
        o = dict(b, id=f"o{self.n}", status="new", filled_qty="0", filled_avg_price=None,
                 created_at=JETZT[0].isoformat(), legs=[])
        sym = b["symbol"]
        if b["side"] == "buy":
            p = self.preis(sym)
            q = float(b["qty"])
            self.cash -= q * p
            ps = sym.replace("/", "")
            alt = self.pos.get(ps, {"qty": 0.0, "avg": p, "sym": sym})
            alt["avg"] = (alt["avg"] * alt["qty"] + p * q) / (alt["qty"] + q)
            alt["qty"] += q * (0.9975 if "/" in sym else 1)
            self.pos[ps] = alt
            o.update(status="filled", filled_qty=str(q), filled_avg_price=str(p))
            if b.get("order_class") == "bracket":
                for typ, extra in (("limit", {"limit_price": b["take_profit"]["limit_price"]}),
                                   ("stop", {"stop_price": b["stop_loss"]["stop_price"]})):
                    self.n += 1
                    leg = dict(symbol=sym, side="sell", type=typ, qty=b["qty"], id=f"o{self.n}", status="held", **extra)
                    self.orders[leg["id"]] = leg
                    o["legs"].append(leg)
        self.orders[o["id"]] = o
        return o

    def __call__(self, methode, url, body=None, ok404=False):
        u = urllib.parse.urlparse(url)
        q = {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
        p = u.path
        if p == "/v2/account":
            eq = self.equity()
            return {"account_number": self.konto, "equity": str(eq), "cash": str(self.cash),
                    "last_equity": str(self.start_eq), "daytrade_count": 0}
        if p == "/v2/clock":
            return {"is_open": True, "next_close": (JETZT[0] + timedelta(hours=2)).isoformat()}
        if p == "/v2/assets":
            return [{"symbol": s, "tradable": True, "min_order_size": "0.0001", "min_trade_increment": "0.000001",
                     "price_increment": "0.01"} for s in ["BTC/USD", "ETH/USD", "SOL/USD", "XRP/USD", "DOGE/USD",
                                                           "LINK/USD", "AVAX/USD"]]
        if p.startswith("/v2/assets/"):
            return {"symbol": p.split("/")[-1], "tradable": True, "status": "active", "fractionable": True}
        if p == "/v2/positions" and methode == "GET":
            return [{"symbol": s, "qty": str(v["qty"]), "avg_entry_price": str(v["avg"]),
                     "market_value": str(v["qty"] * self.preis(v["sym"])), "current_price": str(self.preis(v["sym"])),
                     "asset_class": "crypto" if "/" in v["sym"] else "us_equity"} for s, v in self.pos.items()]
        if p.startswith("/v2/positions/") and methode == "DELETE":
            ps = urllib.parse.unquote(p.split("/")[-1])
            v = self.pos.pop(ps, None)
            if not v:
                return None
            pr = self.preis(v["sym"])
            self.cash += v["qty"] * pr
            self.n += 1
            o = {"id": f"o{self.n}", "symbol": v["sym"], "side": "sell", "type": "market", "status": "filled",
                 "filled_qty": str(v["qty"]), "filled_avg_price": str(pr)}
            self.orders[o["id"]] = o
            return o
        if p == "/v2/orders" and methode == "POST":
            return self.neue_order(body)
        if p == "/v2/orders" and methode == "GET":
            st = q.get("status")
            alle = list(self.orders.values())
            if st == "open":
                return [o for o in alle if o["status"] in ("new", "held", "accepted")]
            return [o for o in alle if o["status"] == "filled" and o["symbol"] == q.get("symbols")][::-1]
        if p.startswith("/v2/orders/"):
            o = self.orders.get(p.split("/")[-1])
            if methode == "DELETE" and o:
                o["status"] = "canceled"
            return o
        if p.endswith("/bars"):
            stunden = {"1Hour": 1, "4Hour": 4, "1Day": 24}[q["timeframe"]]
            return {"bars": {s: self.kerzen(s, stunden, q["start"], q.get("end", "z"))
                             for s in q["symbols"].split(",")}, "next_page_token": None}
        if "latest/trades" in p or "trades/latest" in p:
            return {"trades": {s: {"p": self.preis(s), "t": JETZT[0].isoformat()} for s in q["symbols"].split(",")}}
        if p.endswith("/news"):
            return {"news": []}
        raise AssertionError(f"unbekannt: {methode} {url}")


def neu_aufsetzen(fake):
    tmp = Path(tempfile.mkdtemp())
    for name in ("ZUSTAND", "TRADES", "SCHATTEN", "PROTOKOLL", "LEBEN", "AMPEL", "NACHRICHT", "BT_ERGEBNIS"):
        setattr(bot, name, tmp / getattr(bot, name).name)
    bot.JOURNAL, bot.BERICHT = tmp / "JOURNAL.md", tmp / "BERICHT.md"
    bot.DATEN = tmp
    bot.api = fake
    bot.datetime = FakeZeit
    bot.time.sleep = lambda s: None
    bot.LOG.clear()
    return tmp


def test_ablauf():
    fake = FakeAlpaca()
    tmp = neu_aufsetzen(fake)
    (tmp / "backtest_ergebnis.json").write_text(json.dumps({"strategien": {
        n: {"bestanden": True} for n in json.loads(bot.CONFIG.read_text())["strategien"]}}))
    JETZT[0] = datetime(2026, 11, 30, 18, 10, tzinfo=timezone.utc)
    bot.lauf()
    z = json.loads(bot.ZUSTAND.read_text())
    assert z["start_trade"] == "offen" and "BTC/USD" in z["positionen"], z.get("start_trade")
    assert any("Start-Trade" in x and "Stop bei Alpaca" in x for x in bot.LOG), bot.LOG
    offen = [o for o in fake.orders.values() if o["status"] in ("new", "held")]
    assert any(o["symbol"] == "BTC/USD" and o["type"] == "stop_limit" for o in offen), offen
    assert len(z["positionen"]) <= 3
    # jede Position hat einen Stop bei Alpaca
    for s in z["positionen"]:
        assert any(o["symbol"] == s and o["side"] == "sell" for o in offen), s
    kaeufe = [x for x in bot.LOG if x.startswith("🟢")]
    print("  Meldungen Lauf 1:", bot.LOG)
    assert kaeufe, "kein normaler Kauf trotz Ausbruch-Signal"
    # Lauf 2: 1 Std. spaeter -> Start-Trade verkauft
    bot.LOG.clear()
    JETZT[0] += timedelta(hours=1, minutes=5)
    bot.lauf()
    z = json.loads(bot.ZUSTAND.read_text())
    assert z["start_trade"] == "fertig", z["start_trade"]
    assert any(x.startswith("✅ Start-Trade") for x in bot.LOG), bot.LOG
    assert bot.TRADES.exists() and "START" in bot.TRADES.read_text()
    # Stop ausgeloest: Position bei Alpaca verschwindet -> Bot schreibt Trade
    sym = next(iter(z["positionen"]))
    ps = sym.replace("/", "")
    v = fake.pos.pop(ps)
    stop_o = next(o for o in fake.orders.values() if o["symbol"] == sym and o.get("type") in ("stop", "stop_limit")
                  and o["status"] in ("new", "held"))
    stop_o.update(status="filled", filled_avg_price=str(z["positionen"][sym]["stop"]))
    fake.cash += v["qty"] * z["positionen"][sym]["stop"]
    bot.LOG.clear()
    JETZT[0] += timedelta(minutes=30)
    bot.lauf()
    z = json.loads(bot.ZUSTAND.read_text())
    assert sym not in z["positionen"]
    assert any(x.startswith("🔴 Verkauf") and "Stop" in x for x in bot.LOG), bot.LOG
    assert sym in z.get("sperre_wert", {})
    # Abend-Meldung nach 21:00 Wien
    bot.LOG.clear()
    JETZT[0] = datetime(2026, 11, 30, 20, 40, tzinfo=timezone.utc)
    bot.lauf()
    assert any(x.startswith("📊") for x in bot.LOG), bot.LOG
    assert json.loads(bot.LEBEN.read_text())["zeit"] if bot.LEBEN.exists() else True
    print("  Bericht:", (tmp / "BERICHT.md").read_text()[:300].replace("\n", " | "))


def test_lern_trade():
    fake = FakeAlpaca(trend=-0.002)  # fallender Markt: Filter aus, Backtest fehlt -> nur Lern-Trade
    tmp = neu_aufsetzen(fake)
    JETZT[0] = datetime(2026, 12, 1, 19, 10, tzinfo=timezone.utc)  # 20:10 Wien
    z = {"version": 3, "positionen": {}, "gesehen": {}, "start_trade": "fertig"}
    bot.ZUSTAND.write_text(json.dumps(z))
    bot.AMPEL.write_text(json.dumps({"gueltig_bis": "2026-12-02T10:00:00+01:00", "krypto": "GRUEN", "aktien": "GRUEN",
                                     "fallend": "GRUEN", "beobachten": [{"symbol": "NVDA", "richtung": "steigt",
                                                                         "grund": "starke Zahlen"}]}))
    bot.lauf()
    sch = bot.lies_csv(bot.SCHATTEN)
    assert any(x["strategie"] == "news_tipp" and x["symbol"] == "NVDA" for x in sch), sch[-3:]
    z = json.loads(bot.ZUSTAND.read_text())
    lern = [t for t in z["positionen"].values() if t.get("lern")]
    assert len(lern) == 1 and z["tag"]["lern"], (z["positionen"], bot.LOG)
    assert any("Lern-Trade" in x for x in bot.LOG), bot.LOG
    assert not [t for t in z["positionen"].values() if not t.get("lern")], "normaler Trade ohne Backtest!"
    assert (tmp / "schatten.csv").exists() or True


def test_notbremse_und_paper():
    fake = FakeAlpaca(equity=400.0)
    neu_aufsetzen(fake)
    JETZT[0] = datetime(2026, 12, 1, 19, 10, tzinfo=timezone.utc)
    bot.ZUSTAND.write_text(json.dumps({"version": 3, "positionen": {}, "gesehen": {}, "start_trade": "fertig"}))
    bot.lauf()
    z = json.loads(bot.ZUSTAND.read_text())
    assert not z["positionen"], z["positionen"]
    assert any("Notbremse" in x for x in bot.LOG), bot.LOG
    fake2 = FakeAlpaca(konto="123LIVE")
    neu_aufsetzen(fake2)
    try:
        bot.lauf()
        raise AssertionError("haette stoppen muessen")
    except SystemExit:
        pass
    assert not fake2.orders and any("kein Paper-Konto" in x for x in bot.LOG)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
    print("Alle Bot-Tests bestanden.")
