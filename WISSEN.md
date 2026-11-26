# WISSEN – alles, was Claude für diesen Bot wissen muss

> Lies das am Anfang **jedes** Claude-Laufs (KI-Ampel am Morgen, Lernen am Sonntag).
> Plan und Wünsche von Jonas: `BOT-PLAN.md` (Teil B). Stand: `BERICHT.md`. Backtest: `BACKTEST.md`.

## 1. Worum es geht
- Nur **Alpaca Paper** (Spielgeld, 500 $ Start, Konto beginnt mit `PA`). Nie echtes Geld.
- Der Bot (`bot.py`, v3) läuft auf GitHub **alle 30 Min.**, 24/7. Claude handelt **nie selbst**: KI-Ampel jeden Morgen,
  Lernen jeden Sonntag.
- Ziel als Messlatte: +50 % in einem Monat (`goal.yaml`). Ehrlich: sehr hoch. Risiko wird dafür **nie** erhöht.
- Das Repo ist **öffentlich** → nie Schlüssel, Kanal-Namen oder Persönliches in Dateien schreiben.

## 2. Wie der Bot handelt (Details in `strategien.py`, Einstellungen in `config.json`)
| Strategie | Werte | Wann kaufen | Stop / Ziel / Zeitstop |
|---|---|---|---|
| `breakout_tag` | Aktien/ETFs | Tagesschluss über höchstem Schluss der letzten 55 Tage **und** über SMA200 | 1,5 ATR / 2R / 5 Tage |
| `breakout_4h`, `breakout_1h` | Krypto | Mehrere Rückblicke stimmen ab (Schluss über Hoch der letzten X Kerzen). Mehr Stimmen = mehr Risiko (0,5–1,5 %) | 1,5 ATR / 2R / 2 Tage bzw. 6 Std. |
| `ruecksetzer_tag/_4h` | Aktien / Krypto | Aufwärtstrend, Rücklauf an EMA20, RSI < 45, grüne Kerze über Vorhoch | 1,2 ATR / 2R |
| `umkehr_tag/_4h` | Aktien / Krypto | Überverkauft (RSI < 30 oder weit unter SMA20), Fall unter altes Tief, Schluss wieder drüber | 1 ATR / 1,5R |

- **Markt-Filter:** BTC über SMA200 (Tag) → Krypto-Käufe erlaubt, sonst nur BITI. SPY über SMA200 → Aktien, sonst nur SH/PSQ. GLD/TLT immer.
- **Rangliste:** Signal-Stärke 60 % + Trend 20 % + Volumen 20 % (× `gewicht` der Strategie). Beste zuerst.
- **Normal handeln** nur Strategien, die den Backtest bestanden haben (`daten/backtest_ergebnis.json`) oder in `freigegeben` stehen.
- **Lern-Trades:** Solange heute kein normaler Trade war: um 10, 15 und 20 Uhr Wien (`lern_zeiten_wien`) je 1 Lern-Trade mit dem besten Kandidaten, 0,5 % Risiko (darf alles testen, markiert `lern=ja`).
- **`nur_schatten`** in `config.json`: nie echt handeln, nur als Schatten-Trade mitrechnen (seit 26.11.: `breakout_1h`, Gebühren zu hoch). Am Sonntag prüfen, ob es live doch Sinn macht.
- **`freigegeben`** in `config.json`: Strategien, die Claude am Sonntag trotz Backtest freischaltet (Jonas hat am 26.11. zugestimmt). Dann zuerst `risiko_normal` 0.005, nach 20 Trades prüfen → 0.01 oder wieder raus.
- **Start-Trade:** einmalig ~15 $ BTC mit Stop, nach 1 Std. verkauft → Handy „✅ Start-Trade hat funktioniert“.
- **Schatten-Trades** (`daten/schatten.csv`): jedes Signal, das nicht genommen wurde, und was daraus geworden wäre.
- **Harte Grenzen** (`HART` in `bot.py`, nie ändern): nur Paper · kein Hebel · Risiko max. 2 % · immer Stop · max. 3 Positionen,
  1 pro Wert · Tag −3 % → Stopp für heute · 3 Verluste in Folge → 12 Std. Pause · nach Verlust denselben Wert 2 Std. nicht ·
  Konto < 425 $ → Notbremse · Kurse älter als 1 Std. oder API-Fehler → nichts kaufen.
- Meldungen aufs Handy über ntfy (Kanal nur im GitHub-Secret `NTFY_TOPIC`). Claude kann Jonas etwas schicken, indem es
  den Text in `daten/nachricht.txt` schreibt – der nächste Bot-Lauf schickt ihn und leert die Datei.

## 3. Alpaca – Fakten
- Krypto-Gebühr 0,15 % (Maker) / **0,25 % (Taker)** pro Seite, in der gekauften Münze abgezogen → Stop-Menge × 0,997.
  Aktien/ETFs: keine Provision.
- Krypto: `market`, `limit`, `stop_limit`, Gültigkeit `gtc`/`ioc`. Kein Short. Orders/offene Orders mit `BTC/USD` suchen, Position heißt `BTCUSD`.
- Aktien ganze Stück → **Bracket-Order** (Stop + Ziel bei Alpaca, `gtc`). Bruchteile können keine Bracket-Order und nur
  `day` → der Bot setzt den Stop jeden Handelstag beim ersten Lauf nach Börsenstart neu (Lücke ~15–30 Min. nach 15:30).
- **PDT-Regel** (< 25.000 $): max. 3 Daytrades in 5 Tagen → Aktien mind. über Nacht halten. Bot kauft keine Aktien mehr ab 3 Daytrades.
- Kursdaten: Krypto gratis; Aktien-Tageskerzen SIP (15 Min. verzögert gratis), Live-Kurse IEX.
- US-Börse Mo–Fr 15:30–22:00 Wien (Sommerzeit-Wechsel: USA 08.03.2027, EU 28.03.2027 → 3 Wochen 14:30–21:00).
- Inverse ETFs ohne Hebel: **SH** (S&P fällt), **PSQ** (Nasdaq fällt), **BITI** (Bitcoin fällt). Verlieren langfristig Wert → nur kurz halten.

## 4. Kosten im Kopf behalten
- Krypto kostet hin und zurück ca. **0,5 %** (2 × 0,25 %). Bei einem Stop von 3 % sind das schon ~0,17R pro Trade.
- Aktien/ETFs kosten keine Gebühr → für viele kleine Trades billiger. Deshalb handelt der Bot beides.

## 5. Markt lesen – was in Jonas' Tests wichtig war
1. **Zuerst der Trend** (Tag, dann 4h). Nur mit dem Trend handeln.
2. **Nie dem Kurs hinterherrennen:** Short nur nach einem Rücklauf an einen Widerstand, nie unten am Tagestief.
   Long nur an einer Unterstützung, nie oben am Hoch.
3. **Stop hinter das letzte Hoch/Tief**, mind. 1 ATR, nie genau hinter eine runde Zahl (60.000 wird gern kurz durchstochen).
4. **US-Daten bewegen Bitcoin stark:** meist 14:30 Wien (CPI, PCE, Arbeitsmarkt/NFP, GDP, PPI, Einzelhandel),
   FOMC-Zinsentscheid 20:00 Wien + Pressekonferenz 20:30. 1 Std. vorher/nachher kein neuer Trade.
5. Vor einem Trade auf fallende Kurse: **Funding** (sehr negativ = viele Shorts = Gefahr eines Short-Squeeze) und
   **Bitcoin vs. Nasdaq** (Bitcoin stärker als Nasdaq = eher nicht gegen Bitcoin wetten).
6. **ETF-Zuflüsse/-Abflüsse** (US-Spot-ETFs) zeigen, ob große Käufer kaufen oder verkaufen.
7. Mind. **3 Gründe in dieselbe Richtung**, nichts Großes dagegen. Kein klares Setup = kein Trade („warten" ist ein Ergebnis).
8. Wochenende: weniger Handel, öfter Fehlausbrüche.

## 6. Lektionen bis jetzt
| Datum | Was passiert ist | Lektion |
|---|---|---|
| 24.11.2026 | TradingView #1: Short 59.528, Stop 60.050 nach 1 Std. getroffen (−115 $) | Short zu nah am Tief / Stop zu eng → erst Rücklauf abwarten, Stop hinter echtes Hoch |
| 24.11.2026 | TradingView #2: Short 60.041 → Ziel 59.420 erst nach 2 Std. erreicht (+193 $). Mit fixer Schlusszeit wären es nur +75 $ gewesen | Ziele brauchen Zeit; feste Schlusszeiten kosten Gewinn → Bot hält bis Ziel/Stop/Zeitstop (2 Tage) |
| 25.11.2026 | US-PCE-Daten 14:30, Bitcoin unruhig davor/danach | Rund um US-Daten nicht neu einsteigen (→ Sperrzeiten in der KI-Ampel) |
| 25.11.2026 | Bitcoin ca. 60.000, 16 % unter SMA30, RSI(Tag) ~25: stark überverkauft, aber Trend klar nach unten | Überverkauft heißt nicht „sofort kaufen" → L2 wartet auf Sweep + Umkehr (unter ~55.100) |

_(Claude ergänzt diese Tabelle jeden Sonntag.)_

## 7. KI-Ampel – so entscheidet Claude jeden Morgen
**Datei:** `daten/ki_ampel.json`. Fehlt sie oder ist sie abgelaufen, handelt der Bot nur nach Regeln.

```json
{
  "erstellt": "2026-11-27T07:45:00+01:00",
  "gueltig_bis": "2026-11-28T10:00:00+01:00",
  "krypto": "GRUEN",
  "aktien": "GRUEN",
  "fallend": "GELB",
  "gesperrt": ["COIN"],
  "sperrzeiten": [
    {"von": "2026-11-27T13:30:00+01:00", "bis": "2026-11-27T15:30:00+01:00", "grund": "US BIP 14:30"}
  ],
  "prognose_24h": "faellt",
  "begruendung": "Max. 200 Zeichen, Deutsch, einfache Wörter",
  "lage": {"btc": 60100, "spy": 590, "trend": "…", "etf_fluesse": "…", "wichtigste_news": "…"},
  "quellen": ["https://…"]
}
```
- `krypto` = Krypto kaufen, `aktien` = Aktien/ETFs/GLD/TLT kaufen, `fallend` = inverse ETFs (SH, PSQ, BITI).
  Werte nur `GRUEN` (normal), `GELB` (halbes Risiko), `ROT` (keine neuen Käufe dieser Gruppe).
- `gesperrt`: einzelne Werte mit schlimmen News (z. B. Gewinnwarnung, Hack, Klage). Nur Symbole aus `config.json`.
- `sperrzeiten`: in dieser Zeit **gar keine** neuen Trades (alle Werte). Wichtige US-Daten 60 Min. vorher bis 60 Min. nachher,
  FOMC 30 Min. vorher bis 90 Min. danach. Heute + morgen eintragen. Zeiten **immer mit Zeitzone** (+01:00 Winter, +02:00 Sommer).
- `gueltig_bis` = nächster Tag 10:00 Wien. `prognose_24h` (Bitcoin): `steigt` / `faellt` / `seitwaerts` (Schwelle ±1 %).

**Nur frische Infos:** News, Termine, Flüsse nur aus den **letzten 48 Std.** (Datum jeder Quelle prüfen).
**Gedächtnis:** Vorher `daten/trades.csv` und `daten/schatten.csv` der letzten 7 Tage lesen. Gleiche Fehler nicht zweimal.

**Regeln:** Standard ist **GRÜN**. ROT nur mit konkretem, nachprüfbarem Grund (Quelle). GELB bei gemischter Lage oder großem
Termin in den nächsten 24 Std. Die Ampel bewertet **Nachrichten und Termine**, nicht die Chart-Signale (das macht der Bot).
- `krypto` ROT z. B.: Hack/Pleite einer großen Börse, Verbot, Schock bei US-Daten.
- `aktien` ROT z. B.: Crash-Tag mit klarer Ursache (Krieg, Bankenpleite), Schock bei US-Daten.
- `fallend` ROT z. B.: sehr gute News (Zinssenkung, riesige Zuflüsse), Short-Squeeze-Gefahr.

## 8. Lernen am Sonntag – Regeln (BOT-PLAN Teil B 9)
1. `python3 lernen.py analyse` → `LERNEN.md` (nach Wert, Strategie, Uhrzeit, Wochentag, Trend, KI, Lern vs. normal,
   Schatten-Trades, Zufalls-Zwillinge, Kurz-Urteil pro Trade).
2. Jeden fertigen Trade in `ANALYSEN.md` erklären (News zur Trade-Zeit suchen): **Können / Pech / Glück / Fehler**.
3. `HYPOTHESEN.md`: alte Vermutungen prüfen (nach 20 Trades). Neue Vermutung **vor** einer Änderung aufschreiben.
4. **Max. 1 Änderung pro Woche** in `config.json`, nur mit genug Daten: ≥ 20 Trades zum Feinjustieren, ≥ 15 zum Abschalten
   (`aktiv: false`, oder Wert in `gesperrte_werte`). Gute Strategien → mehr `gewicht` (max. 2). Oft ist „nichts ändern“ richtig.
5. **Vorher** `python3 lernen.py speichern "Grund"` (Kopie nach `history/`). Wird es schlechter → `python3 lernen.py zurueck history/<datei>`.
6. Nie ändern: `HART` in `bot.py`, Risiko über 2 %, Paper-Prüfung, Stop-Logik, `goal.yaml`, alte Trades.
7. Ergebnis (max. 5 Zeilen, einfache Wörter) in `daten/nachricht.txt` → kommt aufs Handy.

## 9. Lage (Stand 25.11.2026, wird jeden Sonntag aktualisiert)
- Bitcoin ca. **60.000 $**, Tagestrend **fallend**: 16 % unter SMA30 (~71.200), RSI(Tag) ~25 (stark überverkauft),
  unter dem 200-Wochen-Schnitt. Tief am 22./23.11. ca. **55.100** (tiefster Stand seit Sept. 2024).
- 4h: unter EMA20/SMA40, ATR ca. 2,2 %.
- **Warum es fällt:** November = Rekord-Abflüsse aus US-Bitcoin-ETFs (ca. −4,9 Mrd $, 6 Tage in Folge), der Markt erwartet eine
  **Zinserhöhung der Fed am 09.12.2026**, Tech-Aktien schwach (Zweifel an KI-Bewertungen), am 25.11. Bericht über neue
  US-Zölle (2,4 Bio. $ Importe) → Bitcoin kurz unter 59.000. Angst-Index (Fear & Greed) bei 8 = extreme Angst.
- **Termine:** Do 26.11. Thanksgiving (US-Börse zu, BITI nicht handelbar), Fr 27.11. Börse nur bis 19:00 Wien, FOMC 09.12. (20:00 Wien).
- L2 wartet auf einen Rutsch unter ca. **55.100** und eine grüne Umkehr. S1 wartet auf einen Rücklauf hoch zur EMA20 (4h).
- Seit Jahresbeginn ist Bitcoin über 20 % gefallen (BITI dafür gestiegen).

## 10. Was Claude nie tun darf
- Keine Orders bei Alpaca, keine Schlüssel anfassen oder anzeigen, nichts an GitHub-Einstellungen/Secrets ändern.
- Nichts löschen (Trades, Protokolle, Schatten).
- Keine echten Geld-Tipps. Echtes Geld erst nach mind. 100 Trades, die besser als Zufall **und** Halten sind – und nur, wenn Jonas es ausdrücklich sagt.
