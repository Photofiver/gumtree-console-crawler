#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup
import time
import random
import re
from datetime import datetime
from urllib.parse import urljoin

# ==================== KONFIGURACJA ====================
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept-Language": "en-GB,en;q=0.9",
}

BASE_URLS = [
    "https://www.gumtree.com/for-sale/video-games-consoles/uk/northern-ireland",
]

MAX_PAGES = 2
DELAY_MIN = 5
DELAY_MAX = 12

KEYWORDS = ["console", "ps5", "ps4", "xbox", "controller", "pad", "nintendo", "switch"]
# ======================================================

def parse_price(text):
    match = re.search(r'£\s*([\d,]+(?:\.\d{2})?)', text)
    if not match:
        match = re.search(r'([\d,]+(?:\.\d{2})?)', text)
    if match:
        try:
            return float(match.group(1).replace(",", ""))
        except:
            return None
    return None

def is_relevant(title):
    t = title.lower()
    return any(kw in t for kw in KEYWORDS)

def scrape_page(url):
    print(f"→ Sprawdzam: {url}")
    offers = []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        listings = soup.find_all("a", href=lambda h: h and ("/p/" in str(h) or "/ad/" in str(h)))

        for item in listings:
            title_tag = item.find(["h2", "h3"])
            title = title_tag.get_text(strip=True) if title_tag else item.get_text(strip=True)
            title = " ".join(title.split())
            if not title or not is_relevant(title) or len(title) < 10:
                continue

            link = urljoin(url, item["href"])
            full_text = item.get_text()
            price = parse_price(full_text)
            
            if price is None or price <= 5:
                continue

            location = "Northern Ireland"
            for loc in ["Belfast", "Antrim", "Down", "Londonderry", "Tyrone", "Armagh"]:
                if loc.lower() in full_text.lower():
                    location = loc
                    break

            offers.append({
                "title": title,
                "price": price,
                "location": location,
                "link": link
            })

    except Exception as e:
        print(f"   Błąd: {e}")

    return offers

def main():
    all_offers = []
    seen = set()

    for base in BASE_URLS:
        for page in range(1, MAX_PAGES + 1):
            url = base if page == 1 else f"{base}?page={page}"
            offers = scrape_page(url)

            for o in offers:
                if o["link"] not in seen:
                    seen.add(o["link"])
                    all_offers.append(o)

            if page < MAX_PAGES:
                delay = random.uniform(DELAY_MIN, DELAY_MAX)
                print(f"   Przerwa {delay:.1f}s...")
                time.sleep(delay)

    all_offers.sort(key=lambda x: x["price"])

    # GENEROWANIE STRONY HTML
    html_filename = "wyniki_gumtree.html"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    html_content = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Okazje Gumtree ({{now_str}})</title>
    <style>
        body {{ font-family: system-ui, sans-serif; background: #121212; color: #fff; padding: 20px; max-width: 1000px; margin: 0 auto; }}
        h1 {{ color: #2ecc71; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        th, td {{ padding: 14px; text-align: left; border-bottom: 1px solid #333; }}
        th {{ background: #1e1e1e; color: #f1c40f; }}
        tr:hover {{ background: #1a1a1a; }}
        .price {{ font-weight: bold; color: #2ecc71; font-size: 18px; }}
        a {{ color: #3498db; text-decoration: none; }}
    </style>
</head>
<body>
    <h1>🔥 Znalezione Oferty Konsol i Padów ({{now_str}})</h1>
    <p>Znaleziono unikalnych ofert: {{len(all_offers)}}. Posortowane od najtańszych.</p>
    <table>
        <tr>
            <th>Cena</th>
            <th>Lokalizacja</th>
            <th>Tytuł</th>
        </tr>
'''
    
    for o in all_offers:
        html_content += f'''
        <tr>
            <td class="price">£{{o['price']:.0f}}</td>
            <td>📍 {{o['location']}}</td>
            <td><a href="{{o['link']}}" target="_blank">{{o['title']}}</a></td>
        </tr>
        '''
        
    html_content += """
    </table>
</body>
</html>
"""

    with open(html_filename, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"\n\u2705 Gotowe! Wygenerowano: {html_filename}")
    print("Otwórz ten plik w przeglądarce.")

if __name__ == "__main__":
    main()