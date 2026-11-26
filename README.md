# Trading-Bot v3 (Alpaca Paper)

Bot von Jonas. Handelt **nur Spielgeld** (Alpaca Paper, 500 $). Läuft auf GitHub alle 30 Min., Laptop kann aus sein.
Plan: **[BOT-PLAN.md](BOT-PLAN.md)** · Stand: **[BERICHT.md](BERICHT.md)** · Backtest: **[BACKTEST.md](BACKTEST.md)**

## Was er macht
- Bewertet jeden Lauf **~45 Werte**: 7 Kryptos (24/7) + 33 US-Aktien/ETFs + GLD/TLT + inverse ETFs (SH, PSQ, BITI) für fallende Kurse.
- Strategien: **Breakout** (Haupt-Strategie), **Rücksetzer im Aufwärtstrend**, **Überverkauft-Umkehr** + Markt-Filter (BTC/SPY über 200-Tage-Schnitt).
- Kauft die **besten** Signale (Rangliste), immer mit Stop. Bis 20:00 kein Trade → **Lern-Trade** mit halbem Risiko.
- Schreibt jedes nicht genommene Signal als **Schatten-Trade** mit und lernt jeden Sonntag daraus.
- Meldet jeden Kauf/Verkauf, Fehler und abends eine Zeile aufs Handy (**ntfy**).

## Wer macht was
| Wer | Wann | Was |
|---|---|---|
| 🤖 `bot.py` | alle 30 Min. (GitHub Actions) | Daten, Signale, Kaufen/Verkaufen, Stops prüfen, Schatten-Trades, Meldungen |
| 🧠 Claude – KI-Ampel | jeden Morgen | News + US-Termine → `daten/ki_ampel.json` (GRÜN/GELB/ROT, Sperrzeiten) |
| 🧠 Claude – Lernen | jeden Sonntag | `lernen.py`, Trades erklären, max. 1 Änderung in `config.json`, Kopie in `history/` |
| 🧪 `backtest.py` | von Hand (Actions → Backtest) | prüft, welche Strategien den Zufall schlagen |

## Dateien
| Datei | Was |
|---|---|
| `bot.py` / `strategien.py` | Bot / Strategien + Indikatoren (gleicher Code wie im Backtest) |
| `config.json` | Einstellungen, die das Lernen langsam verbessert |
| `goal.yaml` | Ziel-Datei (Messlatte) |
| `BERICHT.md` / `JOURNAL.md` / `ANALYSEN.md` | Stand / jeder Trade / Claudes Erklärung |
| `LERNEN.md` / `HYPOTHESEN.md` / `ERKENNTNISSE.md` | Wochen-Analyse / Vermutungen / Änderungen + Rückblicke |
| `history/` | jede alte Version (zurückdrehen möglich) |
| `daten/` | Zustand, Trades, Schatten, Protokoll, Lebenszeichen, KI-Ampel |
| `test_strategien.py`, `test_bot.py` | Tests mit Fake-Kursen und Fake-Alpaca |
| `BOT_AKTIV.txt` | `ja` = darf kaufen, `nein` = **Not-Aus** |

## Von Hand starten
GitHub → **Actions** → **Trading-Bot** → **Run workflow** → `pruefen` (nur anschauen) / `lauf` / `stats`

## Not-Aus
`BOT_AKTIV.txt` auf `nein` → keine neuen Käufe (offene Positionen werden weiter mit Stop verwaltet).
Ganz aus: Actions → Trading-Bot → **⋯** → **Disable workflow**.

## Harte Grenzen (nie ändern ohne Jonas, stehen in `bot.py` → `HART`)
Nur Paper (`PA…`) · kein Hebel · max. 2 % Risiko (normal 1 %, Lern 0,5 %) · immer Stop · max. 3 Positionen, 1 pro Wert ·
Tag −3 % → Stopp · 3 Verluste in Folge → 12 Std. Pause · nach Verlust 2 Std. nicht denselben Wert · Konto < 425 $ → Notbremse.

## Geheimes
Alpaca-Schlüssel und ntfy-Kanal stehen **nur** in GitHub → Settings → Secrets (`APCA_API_KEY_ID`, `APCA_API_SECRET_KEY`, `NTFY_TOPIC`).
Das Repo ist öffentlich → nie in eine Datei schreiben.
