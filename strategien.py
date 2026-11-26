"""
Strategien + Indikatoren. Reine Rechnungen ohne Internet -> gleich im Bot und im Backtest, testbar mit Fake-Kursen.

Kerzen: Liste von dicts {t, o, h, l, c, v}, nur FERTIGE Kerzen, alt -> neu.
vorberechnen() rechnet alle Indikatoren einmal. Wert an Stelle i nutzt nur Kerzen 0..i (keine Zukunfts-Daten).
signal(name, ind, i, s) bewertet die Kerze i mit den Einstellungen s (aus config.json -> strategien -> name).
"""
from collections import deque

# Welche Strategie auf welchen Kerzen und fuer welche Werte laeuft
ART = {"breakout_tag": "tag", "ruecksetzer_tag": "tag", "umkehr_tag": "tag",
       "breakout_4h": "4h", "ruecksetzer_4h": "4h", "umkehr_4h": "4h", "breakout_1h": "1h"}
GRUPPE = {"tag": "aktien", "4h": "krypto", "1h": "krypto"}  # Tages-Strategien = Aktien/ETFs, 4h/1h = Krypto
STUNDEN = {"tag": 24, "4h": 4, "1h": 1}


# ---------------- Indikatoren ----------------
def sma(x, n):
    out, s = [None] * len(x), 0.0
    for i, v in enumerate(x):
        s += v
        if i >= n:
            s -= x[i - n]
        if i >= n - 1:
            out[i] = s / n
    return out


def ema(x, n):
    out = [None] * len(x)
    if len(x) < n:
        return out
    e = sum(x[:n]) / n
    out[n - 1] = e
    a = 2 / (n + 1)
    for i in range(n, len(x)):
        e = a * x[i] + (1 - a) * e
        out[i] = e
    return out


def rsi(c, n=14):
    out = [None] * len(c)
    if len(c) <= n:
        return out
    g = v = 0.0
    for i in range(1, n + 1):
        d = c[i] - c[i - 1]
        g += max(d, 0)
        v += max(-d, 0)
    g, v = g / n, v / n
    out[n] = 100.0 if v == 0 else 100 - 100 / (1 + g / v)
    for i in range(n + 1, len(c)):
        d = c[i] - c[i - 1]
        g = (g * (n - 1) + max(d, 0)) / n
        v = (v * (n - 1) + max(-d, 0)) / n
        out[i] = 100.0 if v == 0 else 100 - 100 / (1 + g / v)
    return out


def atr(h, l, c, n=14):
    out = [None] * len(c)
    if len(c) <= n:
        return out
    tr = [h[0] - l[0]] + [max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1])) for i in range(1, len(c))]
    a = sum(tr[1:n + 1]) / n
    out[n] = a
    for i in range(n + 1, len(c)):
        a = (a * (n - 1) + tr[i]) / n
        out[i] = a
    return out


def roll(x, n, groesstes=True):
    """Max (oder Min) der letzten n Werte INKLUSIVE i. O(n) mit deque."""
    out, dq = [None] * len(x), deque()
    for i, v in enumerate(x):
        while dq and ((x[dq[-1]] <= v) if groesstes else (x[dq[-1]] >= v)):
            dq.pop()
        dq.append(i)
        if dq[0] <= i - n:
            dq.popleft()
        if i >= n - 1:
            out[i] = x[dq[0]]
    return out


def vorberechnen(kerzen, lookbacks=(10, 12, 20, 24, 30, 40, 48, 55, 72)):
    o = [k["o"] for k in kerzen]
    h = [k["h"] for k in kerzen]
    l = [k["l"] for k in kerzen]
    c = [k["c"] for k in kerzen]
    v = [float(k.get("v") or 0) for k in kerzen]
    ind = {"t": [k["t"] for k in kerzen], "o": o, "h": h, "l": l, "c": c, "v": v,
           "sma20": sma(c, 20), "sma50": sma(c, 50), "sma200": sma(c, 200), "ema20": ema(c, 20),
           "rsi": rsi(c), "atr": atr(h, l, c), "vavg20": sma(v, 20), "max_h": {}, "max_c": {}, "min_l": {}}
    for n in sorted(set(lookbacks)):
        ind["max_h"][n] = roll(h, n)
        ind["max_c"][n] = roll(c, n)
        ind["min_l"][n] = roll(l, n, groesstes=False)
    return ind


def _clip(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def _vor(reihe, i):
    """Wert der Reihe bei i-1 (Hoch/Tief der VORHERIGEN n Kerzen, ohne die aktuelle)."""
    return reihe[i - 1] if i >= 1 else None


# ---------------- Signale ----------------
def signal(name, ind, i, s):
    """
    Rueckgabe dict: signal (bool), staerke (0..1), nah (0..1, wie knapp dran - fuer Lern-Trades),
    atr, rsi, info (Text). None, wenn zu wenig Daten.
    """
    c, o, h, l = ind["c"], ind["o"], ind["h"], ind["l"]
    a, r = ind["atr"][i], ind["rsi"][i]
    if a is None or r is None or a <= 0 or i < 3:
        return None
    basis = {"atr": a, "rsi": round(r, 1), "preis": c[i]}
    typ = name.split("_")[0]

    if typ == "breakout" and name.endswith("_tag"):
        n = int(s.get("lookback", 55))
        hoch, sma200 = _vor(ind["max_c"].get(n) or roll(c, n), i), ind["sma200"][i]
        if hoch is None or sma200 is None:
            return None
        sig = c[i] > hoch and c[i] > sma200
        nah = _clip(1 - (hoch - c[i]) / (2 * a)) * (1.0 if c[i] > sma200 else 0.5)
        return {**basis, "signal": sig, "staerke": 1.0 if sig else 0.0, "nah": 1.0 if sig else nah,
                "info": f"Schluss {c[i]:.2f} vs {n}-Tage-Hoch {hoch:.2f}, SMA200 {sma200:.2f}"}

    if typ == "breakout":  # Krypto 4h/1h: mehrere Rueckblicke stimmen ab
        lbs = [int(x) for x in s.get("lookbacks", [10, 20, 30, 40, 55])]
        stimmen, nahs = 0, []
        for n in lbs:
            hoch = _vor(ind["max_h"].get(n) or roll(h, n), i)
            if hoch is None:
                return None
            stimmen += c[i] > hoch
            nahs.append(_clip(1 - (hoch - c[i]) / (2 * a)))
        anteil = stimmen / len(lbs)
        sig = anteil >= float(s.get("min_stimmen", 0.4))
        return {**basis, "signal": sig, "staerke": anteil, "nah": max(anteil, sum(nahs) / len(nahs) * 0.8),
                "stimmen": f"{stimmen}/{len(lbs)}", "info": f"Breakout {stimmen}/{len(lbs)} Rueckblicke"}

    if typ == "ruecksetzer":  # Ruecksetzer im Aufwaertstrend
        e20 = ind["ema20"][i]
        if name.endswith("_tag"):
            ref = ind["sma200"][i]
            trend = ref is not None and c[i] > ref
        else:
            ref = ind["sma50"][i]
            trend = ref is not None and e20 is not None and e20 > ref and c[i] > ref
        if ref is None or e20 is None or None in ind["rsi"][i - 2:i + 1]:
            return None
        pull = min(l[i - 2:i + 1]) <= e20 + float(s.get("ema_toleranz_atr", 0.3)) * a
        rsi_ok = min(ind["rsi"][i - 2:i + 1]) < float(s.get("rsi_max", 45))
        trig = c[i] > o[i] and c[i] > h[i - 1]
        teile = [trend, pull, rsi_ok, trig]
        sig = all(teile)
        return {**basis, "signal": sig, "staerke": 0.7 if sig else 0.0, "nah": sum(teile) / 4,
                "info": "Trend {} Ruecklauf {} RSI {} Ausloeser {}".format(*["ja" if x else "nein" for x in teile])}

    if typ == "umkehr":  # Ueberverkauft-Umkehr: Fall unter altes Tief, Schluss wieder darueber
        n = int(s.get("lookback", 20))
        tief_reihe = ind["min_l"].get(n) or roll(l, n, groesstes=False)
        ref, s20 = (tief_reihe[i - 2] if i >= 2 else None), ind["sma20"][i]
        if ref is None or s20 is None or None in ind["rsi"][i - 2:i + 1]:
            return None
        gedehnt = (min(ind["rsi"][i - 2:i + 1]) < float(s.get("rsi_max", 30))
                   or c[i] < s20 - float(s.get("abstand_atr", 2.5)) * a)
        sweep = min(l[i - 1], l[i]) < ref
        zurueck = c[i] > ref and c[i] > o[i]
        teile = [gedehnt, sweep, zurueck]
        sig = all(teile)
        return {**basis, "signal": sig, "staerke": 0.6 if sig else 0.0, "nah": sum(teile) / 3,
                "info": "ueberverkauft {} unter Tief {} zurueck {}".format(*["ja" if x else "nein" for x in teile])}
    raise ValueError(f"unbekannte Strategie {name}")


def punkte(sig, ind, i, tag_ind=None, gewicht=1.0, lern=False):
    """Rangliste: Signal-Staerke 60 %, Trend 20 %, Volumen 20 %. Bei Lern-Trades zaehlt 'nah' statt 'staerke'."""
    ti = tag_ind if tag_ind is not None else ind
    j = len(ti["c"]) - 1 if tag_ind is not None else i
    s200 = ti["sma200"][j]
    trend = _clip((ti["c"][j] / s200 - 1) * 5) if s200 else 0.5
    va = ind["vavg20"][i]
    vol = _clip(ind["v"][i] / va / 2) if va else 0.5
    st = sig["nah"] if lern else sig["staerke"]
    return round((0.6 * st + 0.2 * trend + 0.2 * vol) * gewicht, 4)


def ausstieg_preise(einstieg, a, s):
    """Stop = stop_atr x ATR unter dem Einstieg, Ziel = ziel_r x Stop-Abstand darueber."""
    dist = float(s.get("stop_atr", 1.5)) * a
    return einstieg - dist, einstieg + float(s.get("ziel_r", 2.0)) * dist


def ueber_200(ind):
    """Markt-Filter: letzter fertiger Schluss ueber dem 200-Tage-Schnitt?"""
    s = ind["sma200"][-1] if ind and ind["sma200"] else None
    return None if s is None else ind["c"][-1] > s


def simuliere(kerzen, ind, name, s, erlaubt=None, gebuehr=0.0, ab=None, bis=None):
    """
    Backtest einer Strategie auf einem Wert. Signal bei Schluss von Kerze i -> Einstieg zur Eroeffnung von i+1.
    Stop zuerst, wenn eine Kerze Stop und Ziel beruehrt. Luecke unter den Stop -> Eroeffnungskurs.
    erlaubt(t) -> bool: Markt-Filter zur Zeit t. gebuehr: pro Seite (Anteil vom Preis).
    Rueckgabe: Liste von Trades {ein_t, aus_t, ein, aus, stop, r, kerzen, grund}.
    """
    trades, n, i = [], len(kerzen), 0
    zeit_k = int(s.get("zeit_kerzen", 5))
    while i < n - 1:
        t = ind["t"][i]
        if (ab and t < ab) or (bis and t >= bis):
            i += 1
            continue
        sg = signal(name, ind, i, s)
        if not sg or not sg["signal"] or (erlaubt and not erlaubt(t)):
            i += 1
            continue
        e = ind["o"][i + 1]
        stop, ziel = ausstieg_preise(e, sg["atr"], s)
        risiko = e - stop
        aus, grund, j = None, None, i + 1
        while j < n:
            k = kerzen[j]
            if k["l"] <= stop:
                aus, grund = min(stop, k["o"]), "Stop"
            elif k["h"] >= ziel:
                aus, grund = max(ziel, k["o"]) if k["o"] > ziel else ziel, "Ziel"
            elif j - i >= zeit_k:
                aus, grund = k["c"], "Zeit"
            if aus is not None:
                break
            j += 1
        if aus is None:
            break  # Trade am Ende der Daten noch offen -> nicht zaehlen
        r = ((aus - e) - gebuehr * (e + aus)) / risiko
        trades.append({"ein_t": ind["t"][i + 1], "aus_t": ind["t"][j], "ein": e, "aus": aus, "stop": stop,
                       "r": round(r, 4), "kerzen": j - i, "grund": grund})
        i = j  # max. 1 Position pro Wert
    return trades
