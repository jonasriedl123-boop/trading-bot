# Erkenntnisse & Regel-Änderungen

## Lern-Regeln (fix) – Details in WISSEN.md Abschnitt 8
- Max. **1** Wert in `config.json` pro Woche ändern, vorher `python3 lernen.py speichern "Grund"` und Vermutung in `HYPOTHESEN.md`.
- Ein Setup erst feinjustieren, wenn es **≥ 20 Trades** hat.
- Setup abschalten, wenn es nach **≥ 15 Trades** im Schnitt **< −0,3R netto** liegt.
- Jede Änderung hier eintragen (Datum, alt → neu, Grund). Wird es danach schlechter → zurück.
- Harte Grenzen (`bot.py` → `HART`) ändert nur Jonas.

## Regel-Änderungen
| Datum | Was | alt → neu | Grund |
|---|---|---|---|
| 25.11.2026 | Start (v1) | – | Bot zieht vom Laptop auf GitHub um |
| 25.11.2026 | v2: Setup S1 (BITI), KI-Ampel, Experiment, Prognosen | – | Jonas will auch auf fallende Kurse setzen und messen, ob sich KI lohnt. **Experiment startet hier.** |
| 26.11.2026 | **v3: Umbau nach BOT-PLAN.md Teil B** | nur BTC/BITI → ~45 Werte; L1/L2/S1 → Breakout/Rücksetzer/Umkehr + Markt-Filter; max. 1 → 3 Positionen; Lern-Trades, Start-Trade, Schatten für alle Signale, ntfy | v2 hat im Backtest 2023–2026 −18 % gemacht und tagelang nicht gehandelt. Alter Code + Daten in `history/v2-btc/`. |

## Lektionen
_(Claude trägt jeden Sonntag ein, was die Trades gezeigt haben)_

## Wochen-Rückblicke
_(neueste oben)_
