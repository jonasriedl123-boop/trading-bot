# WISSEN – alles, was Claude für diesen Bot wissen muss

> Lies das am Anfang **jedes** Claude-Laufs (KI-Ampel am Morgen, Lernen am Sonntag).
> Ziel: Claude soll den Bot so gut führen wie im Chat mit Jonas, nur ohne Gefühle und immer gleich.

## 1. Worum es geht
- Jonas testet, ob sich **Traden mit KI lohnt** → Regeln in `EXPERIMENT.md`, Stand in `BERICHT.md`.
- Nur **Alpaca Paper** (Spielgeld, 500 $ Start, Konto beginnt mit `PA`). Nie echtes Geld.
- Der Bot (`bot.py`) läuft auf GitHub ca. alle 30–60 Min. Claude handelt **nie selbst**, sondern gibt
  1x pro Tag die **KI-Ampel** und lernt 1x pro Woche.

## 2. Wie der Bot handelt (Kurzfassung, Details in `rechner.py`)
| Setup | Wann | Was er kauft | Risiko |
|---|---|---|---|
| **L1** Rücklauf im Aufwärtstrend | Tagestrend AUF (Schluss > SMA30, SMA30 steigt), 4h über SMA40, Rücklauf zur EMA20, RSI(4h) war < 45, grüne Kerze schließt über dem letzten Hoch | Bitcoin | 2 % |
| **L2** Ausverkauf + Umkehr | Tag überverkauft (RSI < 32 oder > 12 % unter SMA30), Kurs sticht unter das Tief der letzten 30 Kerzen und schließt grün wieder darüber | Bitcoin | 1 % (Test) |
| **S1** Rücklauf im Abwärtstrend (Bitcoin fällt) | Tagestrend AB, 4h unter SMA40, Rücklauf hoch zur EMA20, RSI(4h) war > 55, rote Kerze schließt unter dem letzten Tief | **BITI** | 2 % |

- Stop hinter das letzte Hoch/Tief (6 Kerzen) + 0,3 ATR, Abstand 0,8–3 ATR und 1–6 %. Ziel = 2R. Zeitstop nach 12 Kerzen (2 Tage).
- Neue Signale nur 1x pro fertiger 4-Std.-Kerze (Kerzen enden 01, 05, 09, 13, 17, 21 Uhr Wien).
- S1 bei geschlossener US-Börse: Signal wartet max. 20 Std. auf die Öffnung und wird verworfen, wenn Bitcoin inzwischen gestiegen ist.
- Harte Grenzen (nie ändern): nur Paper · nur BTC/BITI · nur kaufen · kein Hebel · max. 2 % Risiko · immer Stop ·
  max. 1 Position · max. 2 Käufe/Tag · 3 Verluste in Folge → 24 Std. Pause · Konto < 425 $ → keine Käufe.
- Eigener News-Filter: Wörter wie hack, exploit, banned, delist, insolvent in den letzten 6 Std. → kein Kauf.

## 3. Alpaca – Fakten
- Krypto-Gebühr 0,15 % (Maker) / **0,25 % (Taker)** pro Seite, wird in der gekauften Währung abgezogen. Aktien/ETFs: keine Provision.
- Krypto: nur `market`, `limit`, `stop_limit`, Gültigkeit `gtc`/`ioc`. Mindestorder 10 $. Kein Short, kein Hebel bei Krypto.
- Symbole: Orders/Kurse `BTC/USD`, Position `BTCUSD`.
- Short mit Aktien geht erst ab 2.000 $ Konto → deshalb **BITI** statt Short.
- Kursdaten für Aktien kostenlos nur über `feed=iex`.

## 4. BITI – Fakten
- ProShares Short Bitcoin ETF: macht **−1x die Tagesbewegung** von Bitcoin (über CME-Futures). Fällt BTC, steigt BITI.
- Nur zu US-Börsenzeiten handelbar: Mo–Fr 15:30–22:00 Wien (Sommerzeit-Wechsel beachten: USA 08.03.2027, EU 28.03.2027 → 3 Wochen lang 14:30–21:00).
- Verliert langfristig Wert (tägliche Umschichtung, ca. 1 % Kosten pro Jahr) → **nur kurz halten** (max. 2 Tage im Bot).
- Kann über Nacht/Wochenende eine Lücke machen (Bitcoin handelt 24/7, BITI nicht). Der Stop greift dann erst bei Öffnung.

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
**Datei:** `daten/ki_ampel.json`. Der Bot liest nur diese Datei. Fehlt sie oder ist sie abgelaufen, handelt er nur nach Regeln.

```json
{
  "erstellt": "2026-11-26T07:45:00+01:00",
  "gueltig_bis": "2026-11-27T10:00:00+01:00",
  "long_btc": "GRUEN",
  "fallend_biti": "GELB",
  "sperrzeiten": [
    {"von": "2026-11-26T13:30:00+01:00", "bis": "2026-11-26T15:30:00+01:00", "grund": "US BIP + Arbeitslosenanträge 14:30"}
  ],
  "prognose_24h": "faellt",
  "begruendung": "Max. 200 Zeichen, Deutsch, einfache Wörter",
  "lage": {"btc": 60100, "trend_tag": "fallend", "funding": "leicht negativ", "etf_fluesse": "-120 Mio $ gestern",
           "nasdaq": "+0,4 %", "dollar": "stabil", "wichtigste_news": "…"},
  "quellen": ["https://…"]
}
```
- Werte nur `GRUEN`, `GELB`, `ROT`. Zeiten **immer mit Zeitzone** (+01:00 Winter, +02:00 Sommer).
- `gueltig_bis` = nächster Tag 10:00 Wien (damit es bis zum nächsten Lauf reicht).
- `prognose_24h`: `steigt` (> +1 %), `faellt` (< −1 %) oder `seitwaerts`. Wird nach 24 Std. automatisch geprüft
  (`daten/prognosen.csv`). Ehrlich schätzen, nicht raten: lieber `seitwaerts`, wenn nichts klar ist.

**Regeln für die Ampel (wichtig für ein faires Experiment):**
- **Standard ist GRÜN.** ROT nur mit einem **konkreten, nachprüfbaren Grund** (News/Daten mit Quelle).
- `long_btc` **ROT** z. B. bei: Hack/Pleite einer großen Börse, Verbot/harter Regulierung, große ETF-Abflüsse
  mehrere Tage + Bruch einer wichtigen Unterstützung mit schlechten News, Schock bei US-Daten (Risk-off).
- `fallend_biti` **ROT** z. B. bei: starken guten News (große ETF-Zuflüsse, positive Regulierung, Zinssenkung),
  Funding stark negativ + Open Interest steigt (Short-Squeeze-Gefahr), Bitcoin deutlich stärker als Nasdaq.
- **GELB** (halbes Risiko): Lage gemischt, wichtiger Termin in den nächsten 24 Std. (außerhalb der Sperrzeit),
  Funding extrem in Trade-Richtung (alle stehen auf einer Seite), Claude unsicher.
- **Sperrzeiten:** wichtige US-Daten von 60 Min. vorher bis 60 Min. nachher. FOMC: 30 Min. vor dem Entscheid bis
  90 Min. danach. Auch große Krypto-Termine mit fester Uhrzeit. Heute + morgen eintragen.
- Nicht ständig umschalten: Die Ampel bewertet **Nachrichten und Termine**, nicht die Chart-Signale (das macht der Bot).

## 8. Lernen am Sonntag – Regeln
- Max. **1** Wert in `parameter.json` pro Woche ändern, nur mit Grund aus den Daten. In `ERKENNTNISSE.md` eintragen (Datum, alt → neu, Grund).
- Ein Setup erst feinjustieren, wenn es **≥ 20 Trades** hat. Setup abschalten (`*_aktiv: false`), wenn es nach **≥ 15 Trades** im Schnitt **< −0,3R** liegt.
- Wird es nach einer Änderung schlechter → zurück auf den alten Wert.
- Nie ändern: harte Grenzen (`rechner.py` → `HART`), `EXPERIMENT.md`, alte Trades.
- Jeden fertigen Trade in `ANALYSEN.md` erklären: Was hat den Kurs bewegt (News suchen!), war es Können/Pech/Glück/Fehler?
- Schatten-Trades + Prognosen auswerten: Wo lag die KI richtig/falsch? Daraus Regeln für die Ampel ableiten (Abschnitt 7 verbessern).
- Diese Datei aktuell halten: Abschnitt 6 (Lektionen) und 9 (Lage).

## 9. Lage (Stand 25.11.2026, wird jeden Sonntag aktualisiert)
- Bitcoin ca. **60.000 $**, Tagestrend **fallend**: 16 % unter SMA30 (~71.200), RSI(Tag) ~25 (stark überverkauft).
- 4h: unter EMA20/SMA40, ATR ca. 2,2 %.
- L2 wartet auf einen Rutsch unter ca. **55.100** und eine grüne Umkehr. S1 wartet auf einen Rücklauf hoch zur EMA20 (4h).
- Seit Jahresbeginn ist Bitcoin über 20 % gefallen (BITI dafür gestiegen).

## 10. Was Claude nie tun darf
- Keine Orders bei Alpaca, keine Schlüssel anfassen oder anzeigen, nichts an GitHub-Einstellungen/Secrets ändern.
- Nichts löschen (Trades, Protokolle, Schatten, Prognosen).
- Keine echten Geld-Tipps für Jonas oder andere. Kein Drängen zu echtem Geld.
