# Backtest v3 (Methode aus Video 1)

Erstellt: 26.11.2026 21:42 UTC · Regeln aus `config.json` (vorher festgeschrieben) · 1 % Risiko pro Trade · Gebühren eingerechnet

| Strategie | Bestanden | Versteckt: Trades · Schnitt · PF · Ertrag · Absturz | Üben: Schnitt | Halten (versteckt) | Zufall geschlagen | Nachbarn ok |
|---|---|---|---|---|---|---|
| breakout_tag | ❌ | 1219 · +0.02R · 1.06 · +26.0% · 22.9% | +0.03R (2674) | +71.4% / −20% | 3/10 | 4/4 |
| breakout_4h | ❌ | 385 · -0.17R · 0.75 · -50.2% · 51.9% | -0.17R (755) | -56.3% / −69% | 4/10 | 0/4 |
| breakout_1h | ❌ | 1440 · -0.36R · 0.47 · -99.5% · 99.5% | -0.34R (2750) | -56.3% / −69% | 6/10 | 0/4 |
| ruecksetzer_tag | ❌ | 715 · +0.03R · 1.05 · +13.8% · 48.1% | +0.01R (1313) | +71.4% / −20% | 3/10 | 3/4 |
| ruecksetzer_4h | ❌ | 78 · -0.11R · 0.82 · -9.0% · 20.5% | -0.18R (189) | -56.3% / −69% | 7/10 | 1/4 |
| umkehr_tag | ❌ | 184 · -0.12R · 0.81 · -20.2% · 23.3% | -0.10R (243) | +71.4% / −20% | 1/10 | 0/4 |
| umkehr_4h | ❌ | 99 · +0.06R · 1.1 · +4.8% · 17.4% | -0.12R (169) | -56.3% / −69% | 10/10 | 2/4 |

## Ehrlich in 3 Zeilen

- **Keine** Strategie besteht alle Prüfungen. Der Bot macht deshalb nur Lern-Trades (halbes Risiko).
- Nicht bestanden (nur als Lern-Trades erlaubt): breakout_tag, breakout_4h, breakout_1h, ruecksetzer_tag, ruecksetzer_4h, umkehr_tag, umkehr_4h.
- Vergangenheit ≠ Zukunft. Bestanden heißt nur: wahrscheinlich kein reines Glück.

## Details pro Strategie

### breakout_tag (2016-01-04 bis 2026-11-25, versteckt ab 2023-08-19)

- ✅ mind. 20 Trades (versteckt)
- ✅ Gewinn nach Gebühren (versteckt)
- ✅ versteckt mind. halb so gut wie Üben
- ❌ besser als Halten (Ertrag/Absturz)
- ❌ besser als Zufall (≥ 8 von 10 Zwillingen)
- ❌ max. 50 % Absturz
- ✅ Nachbar-Einstellungen gehen auch (≥ 3 von 4)
- Jahre: 2016: 80 Tr. +13.0R · 2017: 533 Tr. +24.7R · 2018: 377 Tr. -2.6R · 2019: 438 Tr. -10.8R · 2020: 422 Tr. +56.7R · 2021: 465 Tr. +32.4R · 2022: 86 Tr. -27.7R · 2023: 396 Tr. +14.4R · 2024: 474 Tr. +9.2R · 2025: 338 Tr. +10.0R · 2026: 284 Tr. +1.5R
- Nachbarn: lookback -10: +0.03R (1288) · lookback +10: +0.01R (1174) · stop_atr -0.25: +0.04R (1266) · stop_atr +0.25: +0.04R (1194)
- Ausstiege: {'Ziel': 297, 'Stop': 1142, 'Zeit': 2454} · Zwillinge (Summe %): echt +1.10 vs Zufall [0.708, 2.242, 1.312, 1.707, 1.457, 2.378, -1.163, 3.786, 0.236, 2.652]

### breakout_4h (2021-01-01 bis 2026-11-25, versteckt ab 2025-02-17)

- ✅ mind. 20 Trades (versteckt)
- ❌ Gewinn nach Gebühren (versteckt)
- ❌ versteckt mind. halb so gut wie Üben
- ❌ besser als Halten (Ertrag/Absturz)
- ❌ besser als Zufall (≥ 8 von 10 Zwillingen)
- ❌ max. 50 % Absturz
- ❌ Nachbar-Einstellungen gehen auch (≥ 3 von 4)
- Jahre: 2021: 118 Tr. -27.5R · 2023: 241 Tr. -69.3R · 2024: 340 Tr. -34.1R · 2025: 350 Tr. -46.3R · 2026: 91 Tr. -15.6R
- Nachbarn: min_stimmen -0.2: -0.23R (548) · min_stimmen +0.2: -0.17R (309) · stop_atr -0.25: -0.21R (411) · stop_atr +0.25: -0.13R (359)
- Ausstiege: {'Ziel': 281, 'Stop': 611, 'Zeit': 248} · Zwillinge (Summe %): echt -2.70 vs Zufall [-1.066, -1.752, -1.727, -3.836, -3.39, -3.263, -2.019, -2.026, -3.479, -2.054]

### breakout_1h (2021-01-01 bis 2026-11-25, versteckt ab 2025-02-17)

- ✅ mind. 20 Trades (versteckt)
- ❌ Gewinn nach Gebühren (versteckt)
- ❌ versteckt mind. halb so gut wie Üben
- ❌ besser als Halten (Ertrag/Absturz)
- ❌ besser als Zufall (≥ 8 von 10 Zwillingen)
- ❌ max. 50 % Absturz
- ❌ Nachbar-Einstellungen gehen auch (≥ 3 von 4)
- Jahre: 2021: 424 Tr. -94.5R · 2023: 824 Tr. -279.0R · 2024: 1283 Tr. -488.5R · 2025: 1293 Tr. -474.4R · 2026: 366 Tr. -127.0R
- Nachbarn: min_stimmen -0.25: -0.39R (2040) · min_stimmen +0.25: -0.36R (997) · stop_atr -0.25: -0.45R (1512) · stop_atr +0.25: -0.31R (1391)
- Ausstiege: {'Ziel': 562, 'Stop': 1582, 'Zeit': 2046} · Zwillinge (Summe %): echt -7.17 vs Zufall [-7.104, -8.009, -7.557, -7.138, -8.211, -7.824, -7.347, -6.71, -6.517, -8.244]

### ruecksetzer_tag (2016-01-04 bis 2026-11-25, versteckt ab 2023-08-19)

- ✅ mind. 20 Trades (versteckt)
- ✅ Gewinn nach Gebühren (versteckt)
- ✅ versteckt mind. halb so gut wie Üben
- ❌ besser als Halten (Ertrag/Absturz)
- ❌ besser als Zufall (≥ 8 von 10 Zwillingen)
- ❌ max. 50 % Absturz
- ✅ Nachbar-Einstellungen gehen auch (≥ 3 von 4)
- Jahre: 2016: 50 Tr. +5.1R · 2017: 230 Tr. +61.5R · 2018: 184 Tr. -10.4R · 2019: 190 Tr. -3.2R · 2020: 195 Tr. -21.1R · 2021: 302 Tr. +8.6R · 2022: 71 Tr. -21.7R · 2023: 189 Tr. +16.5R · 2024: 233 Tr. +47.9R · 2025: 181 Tr. -21.9R · 2026: 203 Tr. -29.9R
- Nachbarn: rsi_max -5: +0.10R (379) · rsi_max +5: -0.00R (1116) · stop_atr -0.2: +0.03R (724) · stop_atr +0.2: +0.04R (706)
- Ausstiege: {'Ziel': 237, 'Stop': 794, 'Zeit': 997} · Zwillinge (Summe %): echt -0.09 vs Zufall [0.368, 2.698, 0.595, -0.191, 1.433, 1.338, -0.22, 1.401, -0.388, 0.934]

### ruecksetzer_4h (2021-01-01 bis 2026-11-25, versteckt ab 2025-02-17)

- ✅ mind. 20 Trades (versteckt)
- ❌ Gewinn nach Gebühren (versteckt)
- ❌ versteckt mind. halb so gut wie Üben
- ✅ besser als Halten (Ertrag/Absturz)
- ❌ besser als Zufall (≥ 8 von 10 Zwillingen)
- ✅ max. 50 % Absturz
- ❌ Nachbar-Einstellungen gehen auch (≥ 3 von 4)
- Jahre: 2021: 26 Tr. -12.7R · 2023: 68 Tr. -5.0R · 2024: 85 Tr. -7.4R · 2025: 74 Tr. -13.9R · 2026: 14 Tr. -3.1R
- Nachbarn: rsi_max -5: +0.13R (10) · rsi_max +5: -0.16R (199) · stop_atr -0.2: -0.26R (79) · stop_atr +0.2: -0.06R (77)
- Ausstiege: {'Ziel': 67, 'Stop': 138, 'Zeit': 62} · Zwillinge (Summe %): echt -0.27 vs Zufall [-0.647, -0.265, 0.296, -0.675, -0.711, -0.954, -0.599, -0.606, -0.077, -0.8]

### umkehr_tag (2016-01-04 bis 2026-11-25, versteckt ab 2023-08-19)

- ✅ mind. 20 Trades (versteckt)
- ❌ Gewinn nach Gebühren (versteckt)
- ❌ versteckt mind. halb so gut wie Üben
- ❌ besser als Halten (Ertrag/Absturz)
- ❌ besser als Zufall (≥ 8 von 10 Zwillingen)
- ✅ max. 50 % Absturz
- ❌ Nachbar-Einstellungen gehen auch (≥ 3 von 4)
- Jahre: 2016: 16 Tr. +2.2R · 2017: 26 Tr. +3.9R · 2018: 42 Tr. -10.1R · 2019: 34 Tr. -8.2R · 2020: 44 Tr. -13.1R · 2021: 41 Tr. +8.6R · 2022: 22 Tr. -6.5R · 2023: 57 Tr. -5.8R · 2024: 49 Tr. -12.2R · 2025: 36 Tr. +2.5R · 2026: 60 Tr. -8.2R
- Nachbarn: rsi_max -5: -0.07R (118) · rsi_max +5: -0.03R (387) · stop_atr -0.2: -0.11R (186) · stop_atr +0.2: -0.12R (179)
- Ausstiege: {'Ziel': 121, 'Stop': 210, 'Zeit': 96} · Zwillinge (Summe %): echt -0.74 vs Zufall [-0.288, 0.502, 0.801, -0.136, 1.129, -0.134, 0.049, 0.418, -0.49, -0.818]

### umkehr_4h (2021-01-01 bis 2026-11-25, versteckt ab 2025-02-17)

- ✅ mind. 20 Trades (versteckt)
- ✅ Gewinn nach Gebühren (versteckt)
- ❌ versteckt mind. halb so gut wie Üben
- ✅ besser als Halten (Ertrag/Absturz)
- ✅ besser als Zufall (≥ 8 von 10 Zwillingen)
- ✅ max. 50 % Absturz
- ❌ Nachbar-Einstellungen gehen auch (≥ 3 von 4)
- Jahre: 2021: 9 Tr. -4.9R · 2023: 64 Tr. +10.8R · 2024: 80 Tr. -30.1R · 2025: 86 Tr. +18.7R · 2026: 29 Tr. -10.1R
- Nachbarn: rsi_max -5: +0.42R (43) · rsi_max +5: -0.17R (204) · stop_atr -0.2: -0.12R (100) · stop_atr +0.2: +0.12R (95)
- Ausstiege: {'Ziel': 109, 'Stop': 128, 'Zeit': 31} · Zwillinge (Summe %): echt +0.58 vs Zufall [-1.027, -0.281, -0.06, -0.65, -0.422, -0.928, -1.034, -0.649, 0.042, -1.095]

## Vereinfachungen

- Jede Strategie einzeln, Trades verschiedener Werte gleichzeitig werden nacheinander verrechnet.
- Aktien-Daten mit Split-Anpassung, ohne Dividenden. Inverse ETFs (SH, PSQ, BITI) nur mit eigenen Kursen.
- Die KI-Ampel kann man nicht rückwirkend testen.
