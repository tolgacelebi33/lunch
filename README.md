# Lunch nära Svedbergs

Ren repository-struktur.

## Filer
- `index.html` – webbplatsen
- `CNAME` – `lunch.celebi.io`
- `data/lunch.json` – lunchdata som webbsidan läser
- `data/news.json` – nyhetspool
- `scripts/update_lunch.py` – uppdaterar aktuell lunchvecka
- `scripts/update_news.py` – uppdaterar nyhetspool
- `.github/workflows/update-lunch.yml` – kör uppdateringen automatiskt

Det ska INTE finnas `lunch.json` eller `news.json` direkt i repository-roten.
