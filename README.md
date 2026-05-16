# Gumtree Console Crawler

Prosty crawler w Pythonie do codziennego sprawdzania ofert **używanych konsol do gier i kontrolerów** na Gumtree w rejonie **Belfast / Irlandia Północna**.

## Co zbiera
- Tytuł oferty
- Cenę
- Lokalizację
- Link do ogłoszenia

Wyniki są sortowane od najtańszych i zapisywane do pliku CSV.

## Instalacja

```bash
pip install -r requirements.txt
```

## Uruchomienie

```bash
python gumtree_crawler.py
```

Po uruchomieniu powstanie plik `gumtree_offers_YYYY-MM-DD.csv` z aktualnymi ofertami.

## Codzienne uruchamianie (zalecane)

### Linux / macOS (cron)

```bash
crontab -e
```

Dodaj:
```cron
0 9 * * * cd /twoja/sciezka && /usr/bin/python3 gumtree_crawler.py >> gumtree.log 2>&1
```

### Windows
Użyj **Task Scheduler** i ustaw uruchamianie codziennie o wybranej godzinie.

## WAŻNE

- Crawler ma wbudowane **długie opóźnienia** (8-18 sekund) – szanuje serwer Gumtree.
- Nie uruchamiaj częściej niż raz dziennie.
- Scrapowanie może naruszać regulamin Gumtree. Używasz na własne ryzyko.
- Jeśli strona się zmieni i crawler przestanie działać – daj znać, zaktualizuję selektory.

## Pliki
- `gumtree_crawler.py` – główny skrypt
- `requirements.txt` – wymagane biblioteki

Stworzone dla użytkownika z Belfastu 🏴‍☠️
