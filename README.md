# Trading-Bot (Alpaca Paper) + Experiment „Lohnt sich Traden mit KI?"

Bot von Jonas. Handelt **nur Spielgeld** (Alpaca Paper). Kauft nur, kein Short, kein Hebel:
- **Bitcoin** (BTC/USD), wenn Bitcoin steigen soll
- **BITI** (Fonds, der steigt, wenn Bitcoin fällt), wenn Bitcoin fallen soll. Nur Mo–Fr 15:30–22:00

👉 **Wie läuft's?** → **[BERICHT.md](BERICHT.md)**

## Wer macht was
| Wer | Wann | Was |
|---|---|---|
| 🤖 Bot (`bot.py`) | ca. alle 30–60 Min. auf GitHub | Prüft Kurse, kauft/verkauft nach festen Regeln, setzt immer einen Stop, schreibt alles mit |
| 🧠 Claude – KI-Ampel | jeden Morgen | Liest News + US-Termine, sagt GRÜN / GELB (halbes Risiko) / ROT (gesperrt), Sperrzeiten, Prognose für 24 Std. |
| 🧠 Claude – Lernen | jeden Sonntag | Erklärt jeden Trade, prüft die KI, ändert max. 1 Einstellung, schreibt Rückblick |
| 📊 Experiment (`experiment.py`) | bei jedem Lauf | Vergleicht Bot vs. nur Regeln vs. Bitcoin halten vs. nichts tun |

Dein Laptop kann aus sein.

## Dateien
| Datei | Was |
|---|---|
| `BERICHT.md` | **Stand des Experiments** (automatisch) |
| `EXPERIMENT.md` | Regeln des Experiments (stehen fest) |
| `WISSEN.md` | Alles, was Claude wissen muss (Regeln, Markt, Lektionen, KI-Ampel) |
| `JOURNAL.md` / `ANALYSEN.md` | Trades zum Lesen / Claudes Erklärung dazu |
| `ERKENNTNISSE.md` | Was gelernt wurde + jede Regel-Änderung |
| `bot.py`, `rechner.py`, `experiment.py` | Der Bot |
| `parameter.json` | Einstellungen, die Claude langsam verbessert |
| `BOT_AKTIV.txt` | `ja` = darf kaufen, `nein` = **Not-Aus** |
| `daten/` | Zustand, Trades, Protokoll, KI-Ampel, Schatten-Trades, Prognosen, Verlauf |

## Von Hand starten
GitHub → **Actions** → **Trading-Bot** → **Run workflow** → `pruefen` (nur anschauen) / `lauf` / `stats`

## Not-Aus
`BOT_AKTIV.txt` auf `nein` → keine neuen Käufe (offene Position wird weiter mit Stop verwaltet).
Ganz aus: Actions → Trading-Bot → **⋯** → **Disable workflow**.

## Harte Grenzen (nie ändern ohne Jonas)
Nur Paper-Konto (`PA…`) · nur BTC/BITI · nur kaufen · max. 2 % Risiko · immer Stop · max. 1 Position ·
max. 2 Käufe/Tag · 3 Verluste in Folge → 24 Std. Pause · Konto < 425 $ → keine Käufe mehr.

## Schlüssel
Die Alpaca-Schlüssel stehen **nur** in GitHub → Settings → Secrets. Nie in eine Datei schreiben, nie Screenshots davon.
