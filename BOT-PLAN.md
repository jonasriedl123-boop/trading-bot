# BOT-PLAN – Jonas' Trading-Bot (Endversion)

Stand: 26.11.2026 · Alpaca **Paper**-Konto (Spielgeld, 500 $) · läuft auf GitHub (Repo `jonasriedl123-boop/trading-bot`)

---

## Teil A – Was Jonas tun muss (5 Schritte)

1. Diese Datei herunterladen.
2. Auf **github.com** → dein Repo **trading-bot** → oben **„Add file“** → **„Upload files“** → Datei reinziehen → unten **„Commit changes“**.
3. Auf **claude.ai** einen **neuen Chat** mit Claude Code öffnen, das Repo **trading-bot** auswählen und reinschreiben:
   > Lies BOT-PLAN.md in meinem Repo und setze Teil B komplett um. Frag mich nur, wenn es wirklich nicht anders geht. Antworte kurz.
4. Handy-App **ntfy** installieren (gratis). Der Chat sagt dir den Kanal-Namen → dort abonnieren. Dann bekommst du jeden Trade aufs Handy.
5. In der Claude-App die alte geplante Aufgabe **„Trading-Bot (Alpaca Paper)“** löschen (ist schon ausgeschaltet).

Danach musst du nichts mehr tun. Laptop kann aus sein.

---

## Teil B – Auftrag an Claude (umsetzen)

### 1. Was Jonas will
- Bot handelt **automatisch, 24/7**, Laptop aus.
- **Mindestens 1 Trade pro Tag**, besser 3–4. Nie eine Woche ohne Trade.
- Handelt **das, was gerade am besten geht** – nicht nur Bitcoin.
- **Direkt beim Start ein Trade**, damit Jonas sieht, dass alles funktioniert.
- **Beobachtet den Markt immer**, auch wenn gerade kein guter Zeitpunkt ist.
- **Lernt jede Woche** aus guten und schlechten Trades und wird besser.
- Ziel: Konto von 500 $ auf **~750 (+50 %) in einem Monat**. Ehrlich: Das ist sehr hoch. Gute Bots schaffen eher ein paar % pro Monat. Das Ziel bleibt als Messlatte, aber das Risiko wird dafür **nicht** über die Grenzen erhöht.
- Weitere Wünsche aus alten Chats: auch auf **fallende Kurse** setzen können · nur **aktuelle** Infos nutzen · **nach einem Verlust nicht sofort wieder kaufen** · jeden Trade genau analysieren (warum ist es so gelaufen, welche News) · nach ~30 Trades sehen, ob er Plus macht · Nachrichten an Jonas **kurz und in einfachen Wörtern**.

### 2. Harte Grenzen (nie ändern, auch nicht beim Lernen)
| Regel | Wert |
|---|---|
| Konto | nur Paper (`account_number` beginnt mit **PA**), sonst sofort Stopp + Meldung |
| Hebel | keiner (keine 2x/3x-ETFs, keine Optionen) |
| Risiko pro Trade | normal 1 %, Lern-Trade 0,5 %, **max. 2 %** |
| Stop | **immer**, sofort beim Kauf (Aktien: Bracket-Order; Krypto: Stop-Order direkt danach, jeden Lauf prüfen) |
| Positionen | max. 3 gleichzeitig, max. 1 pro Wert |
| Tageslimit | −3 % an einem Tag → heute keine neuen Trades |
| Verlustserie | 3 Verluste in Folge → 12 Std. Pause |
| Nach Verlust | denselben Wert 2 Std. nicht neu kaufen |
| Notbremse | Konto unter 425 $ → keine neuen Trades, Jonas fragen |
| Schlüssel | nur in GitHub Secrets, nie im Code |

### 3. Was gehandelt wird (Handels-Liste)
- **Krypto (24/7):** die liquidesten Paare, die Alpaca anbietet, z. B. BTC, ETH, SOL, XRP, DOGE, LINK, AVAX (vorher mit der Asset-Liste prüfen). Nur Long (Alpaca kann Krypto nicht shorten).
- **US-Aktien & ETFs (Mo–Fr 15:30–22:00 Wien):** ca. 30 große Aktien (Apple, Microsoft, Nvidia, Amazon, Meta, Google, Tesla, JPMorgan, Coca-Cola, …) + ETFs SPY, QQQ, IWM, GLD, TLT. Bruchteils-Aktien nutzen (geht mit 500 $).
- **Fallende Kurse:** über **inverse ETFs ohne Hebel** (SH = S&P fällt, PSQ = Nasdaq fällt, BITI = Bitcoin fällt), nur wenn bei Alpaca handelbar.
- **Warum mehr Werte?** Mehr Werte = öfter ein Signal, ohne die Regeln schlechter zu machen. Aktien kosten bei Alpaca **keine Gebühr**, Krypto 0,15–0,25 % pro Seite → für viele Trades sind Aktien billiger.
- **Achtung PDT-Regel:** Bei Konten unter 25.000 $ sind bei Aktien max. 3 Daytrades in 5 Tagen erlaubt (aktuelle Regel prüfen). Aktien-Trades deshalb mindestens über Nacht halten (Swing 1–5 Tage). Schnelle Trades nur mit Krypto.

### 4. Strategien
Alle Strategien laufen gleichzeitig. Jeder Lauf bewertet **jeden Wert** und wählt die **besten** Kandidaten (Rangliste nach Signal-Stärke, Trend, Volumen).

1. **Breakout (Haupt-Strategie, Gewinner aus Video 1 + 2)**
   - Aktien/ETFs: Kauf, wenn Tagesschluss über dem höchsten Schluss der letzten 55 Tage **und** über dem 200-Tage-Schnitt.
   - Krypto: 4h- und 1h-Kerzen, Kauf über dem Hoch der letzten X Kerzen. **Abstimmung:** mehrere Breakout-Varianten (verschiedene Rückblicke) stimmen ab – je mehr zustimmen, desto größer die Position (bis max. Risiko).
2. **Rücksetzer im Aufwärtstrend** (altes L1): Trend hoch, Kurs läuft zurück an die EMA20, RSI unter 45, grüne Kerze über dem Vorhoch.
3. **Überverkauft-Umkehr** (altes L2 / Video 2 „oversold bounce“): RSI tief oder Kurs weit unter dem Schnitt, Fall unter ein altes Tief und Schluss wieder darüber.
4. **Markt-Filter (Video 1):** Bitcoin über 200-Tage-Schnitt → Krypto-Käufe erlaubt. Darunter → keine Krypto-Käufe, stattdessen BITI erlaubt. Gleich bei Aktien mit SPY (darunter → SH/PSQ statt Aktien).
5. **KI-Ampel** (gibt es schon): Bei großen Terminen (Zinsentscheid, CPI, Arbeitsmarkt) oder schlimmen News 1 Std. vorher bis 1 Std. danach keine neuen Trades.

Ausstieg für alle: Stop = 1–1,5 × ATR, Ziel = 1,5–2 × Stop, Zeitstop (Krypto 1h: 6 Std., Krypto 4h: 2 Tage, Aktien: 5 Tage). Limit-Orders wo möglich (weniger Gebühren).

### 5. Mindestens 1 Trade pro Tag
- Gab es bis **20:00 Wien** noch keinen Trade → der Bot nimmt den **besten Kandidaten des Tages** als **Lern-Trade** mit **halbem Risiko (0,5 %)**.
- Lern-Trades werden extra markiert und getrennt ausgewertet. So lernt der Bot, ob „fast-Signale“ auch funktionieren, ohne die echten Zahlen zu verfälschen.

### 6. Start-Trade
- Beim ersten Lauf nach dem Umbau: kleiner Test-Trade (ca. 15 $) mit Stop. Prüfen, ob Kauf + Stop bei Alpaca angekommen sind. Nach 1 Std. verkaufen. Handy-Nachricht: „✅ Start-Trade hat funktioniert“ (oder was kaputt ist).

### 7. Immer aktiv
- GitHub Actions läuft **alle 30 Min** (öfter nicht: privates Repo hat 2.000 Gratis-Minuten pro Monat).
- Jeder Lauf: Daten holen, alle Werte bewerten, offene Positionen + Stops prüfen, **Schatten-Trades** notieren (Signale, die er nicht genommen hat, und was daraus geworden wäre).
- Daten älter als 1 Std. oder API-Fehler → nichts kaufen, Meldung an Jonas.
- **Lebenszeichen:** Jeder Lauf schreibt Uhrzeit + Status. Fehlt es 3 Std. → Meldung.
- Der Bot macht bei jedem Lauf einen Commit (Protokoll). Das hält das Repo aktiv, sonst schaltet GitHub geplante Abläufe nach 60 Tagen ab.

### 8. Was zu jedem Trade gespeichert wird
Wert, Strategie, Lern-Trade ja/nein, Zeit, Einstieg, Stop, Ziel, Menge, Ausstieg, Grund (Ziel/Stop/Zeit), Ergebnis in $ und R (nach Gebühren), höchster Gewinn/Verlust zwischendurch (MFE/MAE), Trend (Markt-Filter), RSI, ATR, Uhrzeit, Wochentag, KI-Ampel, News zur Zeit.

### 9. Lernen (jeden Sonntag, wie im Video 1 + Hermes-Idee)
- **Ziel-Datei** `goal.yaml`: Wunsch +50 %/Monat, realistisch besser als Halten und besser als Zufall, max. 15 % Absturz.
- **Wochen-Analyse:** Was lief gut/schlecht – nach Wert, Strategie, Uhrzeit, Trend, Lern-Trade vs. normal. Jeder fertige Trade bekommt eine kurze Analyse (Können / Pech / Glück / Fehler).
- **Zufalls-Zwilling-Test:** Jede Strategie wird mit 10 Zufalls-Kopien verglichen (gleich viele Trades, gleiche Haltezeit, zufällige Zeitpunkte). Schlägt sie den Zufall nicht → Glück, nicht Können.
- **Vorher Vermutung aufschreiben:** „Wenn ich X ändere, wird Y besser.“ Nach 20 Trades prüfen, ob es gestimmt hat.
- **Max. 1 Änderung pro Woche**, nur mit genug Daten (≥ 20 Trades für Feinjustieren, ≥ 15 für Abschalten). Schlechte Werte/Strategien abschalten, gute bekommen mehr Gewicht.
- **Jede Version speichern** im Ordner `history/`. Wird es schlechter → zurückdrehen.
- Ergebnis kurz (max. 5 Zeilen) an Jonas.

### 10. Vor dem Start testen (Methode aus Video 1)
1. Regeln vorher festschreiben, danach nicht mehr am Ergebnis drehen.
2. Daten: 70 % üben, 30 % versteckt – bewertet wird nur der versteckte Teil.
3. Mehrere Zeiträume (auch 2022 = Crash-Jahr).
4. Prüfen: besser als Halten · besser als Zufalls-Zwillinge · max. 50 % Absturz · mind. 20 Trades · versteckt mind. halb so gut wie beim Üben · Nachbar-Einstellungen funktionieren auch · Gebühren eingerechnet · Code vorher mit Fake-Kursen prüfen, ob er richtig rechnet (keine Zukunfts-Daten).
5. Jonas ehrlich in 3 Zeilen sagen, welche Strategien den Zufall schlagen. Nur die laufen lassen (Lern-Trades dürfen trotzdem alles testen).

### 11. Meldungen an Jonas (ntfy, kurz)
- Jeder Kauf/Verkauf: „🟢 Kauf ETH 2.410 $ · Stop 2.360 · Ziel 2.490“ / „🔴 Verkauf ETH −4,10 $ (−0,8R)“.
- Jeden Abend 21:00: 1 Zeile (Trades heute, Konto, Woche).
- Fehler oder Notbremse sofort.

### 12. Geplante Aufgaben (Claude) anpassen
- **KI-Ampel täglich** behalten (für alle Werte, nicht nur BTC).
- **Sonntags-Lernen** auf Teil B Punkt 9 umstellen.
- Alte Aufgabe „Trading-Bot (Alpaca Paper)“ (Vault-Bot) ist aus → Jonas löscht sie.

### 13. Später (nicht jetzt)
- Echtes Geld erst nach **mind. 100 Trades**, die besser als Zufall **und** besser als Halten sind – und nur, wenn Jonas das ausdrücklich sagt.

---

## Teil C – Das Wichtigste aus den Videos (kurz)

**Video 1 – Miles Deutscher: „Claude Tested 10,000 Trading Strategies“**
- 50 bekannte Strategien × 10 Einstellungen × Long/Short × 2 Zeiteinheiten = 10.000 Tests, 5 Coins, 2019–2026.
- **Breakout-Strategien schlagen den Zufall am klarsten** (13 von 100 bestehen alle Tests, Zufall nur 6 von 100).
- Beste Einzel-Strategien waren meist Glück (zu großer Absturz, zu wenige Trades, nur eine Einstellung funktioniert).
- Endstrategie: 80 Breakout-Varianten stimmen ab, Bitcoin-200-Tage-Filter → 10.000 $ → 145.000 $ seit 2019, max. −41 %, 2022 +31 %, 2025 −15 %.

**Video 2 – Miles Deutscher: „Claude als 24/7-Aktien-Trader“ (Alpaca)**
- Regelbuch-Datei (Risiko + Strategie), Claude liest sie vor jedem Trade.
- **Bracket-Orders** (Stop + Ziel gleich bei Alpaca), 1 % Risiko, max. 5 Positionen, Tageslimit 3 %.
- Breakout 55-Tage-Hoch + über 200-Tage-Schnitt war von 3 Strategien die beste: 1 Jahr +16 % (75 Trades) vs. S&P +11 %. Über 5 Jahre war Halten aber besser.
- „Wenn etwas komisch aussieht, nichts kaufen“ + alles protokollieren.

**Hermes-Anleitung (Text von Jonas)**
- Gute Ideen: Ziel-Datei, jede Strategie-Version speichern, Vermutung vor jeder Änderung, nur 1 Wert pro Änderung, Lebenszeichen.
- Nicht übernommen: Lernen schon nach 5 Trades (= Zufall), Railway/Hermes (kostet, laut eigenem Hinweis gerade kaputt).

**Erfahrung aus dem Vault-Bot (26.11.2026)**
- Bei Alpaca offene Krypto-Orders mit `BTC/USD` suchen, **nicht** `BTCUSD` – sonst wird der Stop nicht gefunden und doppelt gesetzt.
- Krypto-Stop-Menge etwas kleiner als die Position (Gebühr wird in BTC abgezogen), z. B. × 0,997.
- Strenge Regeln allein = tagelang kein Trade, wenn der Markt fällt → darum mehr Werte + Lern-Trades.
