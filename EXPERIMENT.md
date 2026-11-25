# Experiment: Lohnt sich Traden mit KI?

> Diese Regeln stehen **vorher** fest und werden während des Experiments **nicht geändert**.
> Sonst könnte man sich das Ergebnis schönrechnen.

## Die Frage
Macht ein Bot mit KI (Claude) mit Spielgeld auf Dauer Gewinn, und ist er besser als einfache Alternativen?

## Die 4 Varianten
| Variante | Was passiert |
|---|---|
| 🤖 **Bot (Regeln + KI)** | Die echten Paper-Trades. Der Bot handelt nach festen Regeln. Claude gibt jeden Morgen eine **KI-Ampel**: sperren (ROT), halbes Risiko (GELB), normal (GRÜN) + Sperrzeiten bei wichtigen US-Terminen. |
| 📏 **Nur Regeln** | Was passiert wäre **ohne** KI: echte Trades mit vollem Risiko + alle Signale, die die KI gesperrt hat (**Schatten-Trades**, nur ausgerechnet). |
| 🪙 **Bitcoin halten** | Die 500 $ am Starttag komplett in Bitcoin und nie verkaufen. |
| 💵 **Nichts tun** | 500 $ bleiben 500 $. |

## Ablauf
- Start: erster Bot-Lauf nach dem Umbau (25./26.11.2026), Startwerte in `daten/experiment.json`
- Zwischenstand: laufend in **BERICHT.md**, jeden Sonntag schreibt Claude einen Rückblick (ERKENNTNISSE.md)
- **Erstes Urteil frühestens nach 30 Trades UND 8 Wochen.** Vorher kann alles Zufall sein.
- Endauswertung nach ca. 3 Monaten (Datum in BERICHT.md)

## Die 5 Fragen (für „lohnt sich" müssen 1–4 erfüllt sein)
1. **Gewinn nach Gebühren?** Durchschnitt > 0R pro Trade und Profit-Faktor ≥ 1,2
2. **Besser als nichts tun?** Kontostand über 500 $
3. **Besser als Bitcoin halten?** Mehr Prozent als Bitcoin im gleichen Zeitraum
4. **Sicher genug?** Größter Rückgang vom Höchststand unter 15 %
5. **Hilft die KI?** KI-Bot (GELB zählt halb) hat mindestens so viele R wie „Nur Regeln"

## Was während des Experiments erlaubt ist
- Claude darf **1 Einstellung pro Woche** ändern (Regeln in ERKENNTNISSE.md). Jede Änderung wird mit Datum notiert,
  damit man sieht, ab wann etwas anders war.
- Code-Fehler dürfen repariert werden (mit Notiz).
- **Nicht erlaubt:** harte Grenzen ändern, Kriterien oben ändern, Trades nachträglich löschen.

## Ehrlich bleiben
- 30 Trades sind wenig. Das Ergebnis ist ein **Hinweis, kein Beweis**.
- Spielgeld ist nicht Echtgeld: Echt kommen Gefühle, Ausführung und Steuern dazu.
- Auch wenn es klappt: echtes Geld erst ab 18 und mit den Eltern.
