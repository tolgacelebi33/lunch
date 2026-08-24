# Lunch nära Svedbergs

Ren repository-struktur.

## Filer
- `index.html` – webbplatsen
- `CNAME` – `lunch.celebi.io`
- `data/lunch.json` – lunchdata som webbsidan läser
- `data/news.json` – nyhetspool
- `data/commodities.json` – råvarupriser (Inköpsradar), konverterat till SEK
- `scripts/update_lunch.py` – uppdaterar aktuell lunchvecka för Kabyssen, Limmareds Wärdshus,
  Centralen / Sångbergs och Glasets Hus
- `scripts/update_news.py` – uppdaterar nyhetspool
- `scripts/update_commodities.py` – hämtar råvarupriser och konverterar till SEK via Frankfurter (ECB)
- `.github/workflows/update-lunch.yml` – kör uppdateringen automatiskt

Det ska INTE finnas `lunch.json`, `news.json` eller `commodities.json` direkt i repository-roten.

## Restauranger och automatik
- **Centralen / Sångbergs** – textbaserad meny, skrapas direkt.
- **Limmareds Wärdshus** – textbaserad meny ("Vecka N"-block), skrapas direkt.
- **Glasets Hus** – menyn publiceras enbart som bild. Läses av med OCR
  (tesseract-ocr + tesseract-ocr-swe, installeras i workflowen).
- **Kabyssen** – kabyssen-dalstorp.se blockerar automatiserad hämtning via
  `robots.txt`. Skrapning sker med restaurangens uttryckliga (muntliga och
  skriftliga) tillstånd. Samma text/OCR-fallback som Glasets Hus används,
  men strukturen har inte kunnat förhandsgranskas i förväg – kontrollera
  `kabyssen: ...`-raden i Actions-loggen efter första körningen.

Kör gärna workflowen manuellt en gång ("Run workflow" i Actions-fliken) och
läs igenom hela loggen innan ni litar på att allt är korrekt inläst.
