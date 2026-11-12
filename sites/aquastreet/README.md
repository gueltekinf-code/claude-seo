# Aquastreet – neue Website (www.aquastreet.de)

Schnelle, statische Website für den Waschpark Aquastreet in Alzenau. Sie läuft ohne Baukasten,
ohne Cookies und ohne externe Dienste. Ein Python-Skript erzeugt alle Seiten als fertiges HTML.

## Was drin ist

| Seite | Adresse | Ziel bei Google |
|---|---|---|
| Startseite | `/` | „Waschstraße Alzenau“, „Waschanlage Alzenau“ |
| Waschstraße & Preise | `/waschstrasse/` | Programme, Preise, Vergleich, Fahrzeugmaße |
| SB-Waschen | `/sb-waschen/` | „SB Waschbox Alzenau“, „Staubsauger 24/7“ |
| Innenreinigung | `/innenreinigung/` | Innenreinigung, Aufbereitung, Versiegelung |
| Firmenkunden | `/firmenkunden/` | Flottenwäsche, Firmenkarte, DKV/UTA |
| Kundenkarte | `/kundenkarte/` | Vorteile + Online-Antrag |
| Aktionen | `/aktionen/` | Seniorentag |
| Über uns | `/ueber-uns/` | Werte, FAQ |
| Kontakt | `/kontakt/` | Anfahrt, Öffnungszeiten, Formular |
| Impressum, Datenschutz | `/impressum/`, `/datenschutz/` | – |

Außerdem:

- **Strukturierte Daten (JSON-LD):** AutoWash mit Öffnungszeiten und Preisen, Services, FAQ und Brotkrumen.
- **SEO-Dateien:** `sitemap.xml`, `robots.txt` und `llms.txt` (für KI-Suchen wie ChatGPT und Perplexity).
- **`.htaccess`** mit vier Aufgaben:
  - leitet alles auf `https://www.aquastreet.de` weiter
  - leitet die alten Adressen per 301 um (`/angebote`, `/uber-uns`, `/kontakt-neu`)
  - setzt Sicherheits-Header
  - regelt Caching und Komprimierung
- **`formular.php`** verschickt Kontakt- und Kundenkartenanträge per E-Mail an `info@aquastreet.de`. Das Formular hat einen Spam-Schutz.
- **Live-Status** „Waschstraße geöffnet / öffnet um …“ nach deutscher Zeit.
- **Lighthouse (Google-Qualitätsmessung):** 99–100 Punkte in Performance, Barrierefreiheit, Best Practices und SEO.

## Hochladen bei STRATO

1. **Paket prüfen.** Für eigene Dateien brauchst du ein STRATO-*Hosting*-Paket mit Webspace und PHP. Mit dem reinen „Homepage-Baukasten“ geht das nicht.
2. Alle Dateien aus dem Ordner `dist/` per SFTP (z. B. mit FileZilla) in das Webspace-Verzeichnis hochladen. Dazu gehört auch die versteckte Datei `.htaccess`.
3. Im STRATO-Kundenbereich unter **Domains** **beide** Adressen auf dieses Verzeichnis zeigen lassen: `aquastreet.de` und `www.aquastreet.de`. Für beide **SSL aktivieren**.
   *Heute zeigt `aquastreet.de` ohne www nur eine STRATO-Platzhalterseite.*
4. In `formular.php` steht als Absender `website@aquastreet.de`. Diese Adresse (oder eine andere `@aquastreet.de`-Adresse) muss bei STRATO existieren, sonst landen Mails im Spam.
5. **Testen:**
   - `http://aquastreet.de` → muss auf `https://www.aquastreet.de/` springen
   - `/angebote` → muss auf `/waschstrasse/` springen
   - Kontaktformular einmal absenden
6. **Google Search Console:**
   - `https://www.aquastreet.de/sitemap.xml` einreichen
   - Startseite und `/waschstrasse/` per URL-Prüfung zur Indexierung anmelden
7. **Google-Unternehmensprofil:** Website-Link, Öffnungszeiten und Telefonnummer exakt wie auf der Website eintragen.

## Preise oder Texte ändern

Alle Fakten stehen oben in `build.py` im Abschnitt `DATA`: Preise, Programme, Öffnungszeiten, Produkte und FAQ.
Ändern, dann neu bauen:

```bash
pip install pillow
python3 build.py          # erzeugt dist/
```

Neue Fotos: Originale in einen Ordner legen, `tools/prepare_images.py` anpassen und ausführen.

## Bitte vor dem Livegang prüfen

- [ ] **Telefonnummer:** Im alten Impressum steht 0151 72297295, in der alten Datenschutzerklärung 0162 4615953. Verwendet wird 0151 72297295.
- [ ] **SB-Boxen:** Die alte Startseite nannte einmal „4“ und einmal „14“. Verwendet wird **4** (so steht es auch auf der Angebotsseite).
- [ ] **Wasserersparnis:** Die alte Seite nannte 70 % und 80 %. Die neue Seite nennt keine Prozentzahl. Bei einer belegbaren Zahl ergänzen.
- [ ] **Bildrechte:** Alle Fotos stammen von der alten Website. Bei Stockfotos prüfen, ob die Lizenz die Nutzung erlaubt.
- [ ] **Grafik „DKV/UTA“:** Sie enthält einen Tippfehler: „WIR AZEPTIEREN“ statt „AKZEPTIEREN“.
- [ ] **Impressum und Datenschutz:**
  - Aktualisiert: DDG statt TMG, der Link zur eingestellten EU-Streitschlichtungsplattform ist entfernt.
  - Die Datenschutzerklärung ist auf die neue Seite ohne Cookies und Tracking zugeschnitten.
  - Bitte rechtlich prüfen lassen, z. B. mit dem eRecht24-Generator.
- [ ] **Fehlende Angaben:**
  - Preise der SB-Programme und Feiertags-Öffnungszeiten stehen nicht auf der Seite, weil sie nicht bekannt waren.
  - Es gibt keine Kundenbewertungen auf der Seite. Echte Google-Bewertungen könnte man später einbinden.
