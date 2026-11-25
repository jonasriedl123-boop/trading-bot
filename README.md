# Trading-Bot (Alpaca Paper)

Bot von Jonas. Handelt **nur Spielgeld** (Alpaca Paper), **nur Bitcoin**, **nur kaufen** (kein Short, kein Hebel).

## Wie er läuft
- GitHub startet ihn **alle 30 Minuten** (`.github/workflows/bot.yml`). Dein Laptop kann aus sein.
- Er prüft: Konto ist Paper? → Position offen? → Stop da? → Ziel/Zeit erreicht? → neues Signal?
- Neue Käufe prüft er nur, wenn eine neue 4-Std.-Kerze fertig ist.
- Jeder Kauf bekommt sofort einen Stop. Geht das nicht → er verkauft sofort wieder.
- Ergebnisse landen in `daten/` und `JOURNAL.md`.

## Dateien
| Datei | Was |
|---|---|
| `bot.py` | Der Bot (redet mit Alpaca) |
| `rechner.py` | Rechnet Signale, Stop, Menge (+ harte Grenzen) |
| `parameter.json` | Einstellungen, die Claude langsam verbessert |
| `BOT_AKTIV.txt` | `ja` = darf kaufen, `nein` = **Not-Aus** (keine neuen Käufe) |
| `daten/zustand.json` | Was der Bot gerade weiß (Position, Pause …) |
| `daten/trades.csv` | Alle fertigen Trades |
| `daten/protokoll.csv` | Was er bei jeder neuen Kerze entschieden hat |
| `JOURNAL.md` | Trades zum Lesen |
| `ERKENNTNISSE.md` | Was gelernt wurde + Regel-Änderungen |

## Von Hand starten
GitHub → **Actions** → **Trading-Bot** → **Run workflow** → Modus wählen:
- `pruefen` = nur anschauen, kauft nix
- `lauf` = normaler Lauf
- `stats` = Auswertung

## Not-Aus
`BOT_AKTIV.txt` auf `nein` ändern → keine neuen Käufe. Offene Position wird weiter mit Stop verwaltet.
Ganz aus: Actions → Trading-Bot → **⋯** → **Disable workflow**.

## Harte Grenzen (nie ändern ohne Jonas)
Nur Paper-Konto (beginnt mit `PA`) · nur BTC · nur Long · max. 2 % Risiko · immer Stop · max. 1 Position · max. 2 Käufe/Tag · 3 Verluste in Folge → 24 Std. Pause · Konto < 425 $ → keine Käufe mehr.

## Schlüssel
Die Alpaca-Schlüssel stehen **nur** in GitHub → Settings → Secrets (`APCA_API_KEY_ID`, `APCA_API_SECRET_KEY`). Nie in eine Datei schreiben, nie Screenshots davon.
