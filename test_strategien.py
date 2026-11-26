#!/usr/bin/env python3
"""
Tests mit Fake-Kursen (BOT-PLAN Teil B 10.4): rechnet der Code richtig und nutzt er KEINE Zukunfts-Daten?
  python3 test_strategien.py
"""
import json
import math
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

import strategien as st

CFG = json.loads((Path(__file__).resolve().parent / "config.json").read_text(encoding="utf-8"))


def fake_kerzen(n, seed=1, start=100.0, drift=0.0005, vola=0.02):
    rnd = random.Random(seed)
    t0 = datetime(2022, 1, 1, tzinfo=timezone.utc)
    out, c = [], start
    for i in range(n):
        o = c
        c = max(1.0, o * math.exp(rnd.gauss(drift, vola)))
        h = max(o, c) * (1 + abs(rnd.gauss(0, vola / 2)))
        l = min(o, c) * (1 - abs(rnd.gauss(0, vola / 2)))
        out.append({"t": t0 + timedelta(hours=4 * i), "o": o, "h": h, "l": l, "c": c, "v": rnd.uniform(100, 1000)})
    return out


def test_indikatoren():
    x = [1, 2, 3, 4, 5, 6]
    assert st.sma(x, 3)[2:] == [2, 3, 4, 5]
    assert st.roll(x, 3)[2:] == [3, 4, 5, 6]
    assert st.roll([5, 4, 3, 2, 1, 0], 3, groesstes=False)[2:] == [3, 2, 1, 0]
    assert st.rsi([float(i) for i in range(30)])[-1] == 100.0
    k = fake_kerzen(50)
    a = st.atr([b["h"] for b in k], [b["l"] for b in k], [b["c"] for b in k])
    assert a[13] is None and a[14] > 0


def test_keine_zukunftsdaten():
    """Signal an Stelle i muss gleich sein, egal ob die Kerzen danach existieren oder komplett anders sind."""
    k = fake_kerzen(700, seed=7)
    voll = st.vorberechnen(k)
    for name, s in CFG["strategien"].items():
        for i in range(260, 700, 37):
            kurz_ind = st.vorberechnen(k[:i + 1])
            anders = k[:i + 1] + fake_kerzen(50, seed=99, start=k[i]["c"] * 3)  # verrueckte Zukunft
            anders_ind = st.vorberechnen(anders)
            a, b, c = (st.signal(name, voll, i, s), st.signal(name, kurz_ind, i, s), st.signal(name, anders_ind, i, s))
            assert a == b == c, (name, i, a, b)


def test_breakout_erkennt_ausbruch():
    k = [{"t": datetime(2020, 1, 1, tzinfo=timezone.utc) + timedelta(days=i), "o": 100, "h": 101, "l": 99,
          "c": 100 + (i % 3) * 0.1, "v": 1} for i in range(260)]
    k[-1] = dict(k[-1], o=100, h=110, c=109)  # klarer Ausbruch
    ind = st.vorberechnen(k)
    sg = st.signal("breakout_tag", ind, len(k) - 1, CFG["strategien"]["breakout_tag"])
    assert sg["signal"], sg
    sg4 = st.signal("breakout_4h", ind, len(k) - 1, CFG["strategien"]["breakout_4h"])
    assert sg4["signal"] and sg4["staerke"] == 1.0
    sg_vor = st.signal("breakout_tag", ind, len(k) - 2, CFG["strategien"]["breakout_tag"])
    assert not sg_vor["signal"]


def test_simulation_rechnet_richtig():
    """Fake-Trade: Einstieg 100, ATR bekannt -> Ziel muss genau +ziel_r R bringen (ohne Gebuehr)."""
    t0 = datetime(2020, 1, 1, tzinfo=timezone.utc)
    k = [{"t": t0 + timedelta(days=i), "o": 100, "h": 101, "l": 99, "c": 100, "v": 1} for i in range(260)]
    k.append({"t": t0 + timedelta(days=260), "o": 100, "h": 106, "l": 99.5, "c": 105, "v": 1})  # Ausbruch
    k.append({"t": t0 + timedelta(days=261), "o": 105, "h": 105.5, "l": 104.8, "c": 105.2, "v": 1})  # Einstieg 105
    k.append({"t": t0 + timedelta(days=262), "o": 105.2, "h": 200, "l": 105, "c": 150, "v": 1})  # Ziel sicher
    ind = st.vorberechnen(k)
    s = CFG["strategien"]["breakout_tag"]
    tr = st.simuliere(k, ind, "breakout_tag", s)
    assert len(tr) == 1 and tr[0]["grund"] == "Ziel" and tr[0]["ein"] == 105, tr
    assert abs(tr[0]["r"] - s["ziel_r"]) < 1e-9, tr
    tr_g = st.simuliere(k, ind, "breakout_tag", s, gebuehr=0.0025)
    assert tr_g[0]["r"] < tr[0]["r"]
    # Stop: Kerze faellt durch den Stop -> genau -1R (ohne Luecke)
    k2 = k[:-1] + [{"t": t0 + timedelta(days=262), "o": 105.2, "h": 105.3, "l": 50, "c": 60, "v": 1}]
    tr2 = st.simuliere(k2, st.vorberechnen(k2), "breakout_tag", s)
    assert tr2[0]["grund"] == "Stop" and abs(tr2[0]["r"] + 1) < 1e-9, tr2
    # Luecke unter den Stop -> Eroeffnungskurs (schlechter als -1R)
    k3 = k[:-1] + [{"t": t0 + timedelta(days=262), "o": 80, "h": 81, "l": 79, "c": 80, "v": 1}]
    tr3 = st.simuliere(k3, st.vorberechnen(k3), "breakout_tag", s)
    assert tr3[0]["aus"] == 80 and tr3[0]["r"] < -1


def test_zufall_hat_keinen_vorteil():
    """Auf reinem Zufall (ohne Trend) darf keine Strategie systematisch viel gewinnen -> Code schummelt nicht."""
    for name, s in CFG["strategien"].items():
        summe, n = 0.0, 0
        for seed in range(6):
            k = fake_kerzen(1500, seed=seed, drift=0.0)
            tr = st.simuliere(k, st.vorberechnen(k), name, s)
            summe += sum(t["r"] for t in tr)
            n += len(tr)
        assert n > 0, name
        assert summe / n < 0.35, (name, summe / n, n)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
    print("Alle Tests bestanden.")
