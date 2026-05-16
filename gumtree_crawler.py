#!/usr/bin/env python3
"""
Prosty crawler ofert używanych konsol i kontrolerów na Gumtree
(Belfast + Irlandia Północna)

 Zbiera: tytuł, cenę, lokalizację, link
 Sortuje od najtańszych

UWAGA: Używaj z umiarem. Dodano długie opóźnienia.
"""

import requests
from bs4 import BeautifulSoup
import time
import random
import csv
import re
from datetime import datetime
from urllib.parse import urljoin

# ==================== KONFIGURACJA ====================

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept-Language": "en-GB,en;q=0.9",
}

BASE_URLS = [
    "https://www.gumtree.com/for-sale/video-games-consoles/uk/northern-ireland",
]

MAX_PAGES = 2
DELAY_MIN = 8
DELAY_MAX = 18

KEYWORDS = ["console", "ps5", "ps4", "xbox", "controller", "pad", "nintendo", "switch"]

# ======================================================


def parse_price(text):
    match = re.search(r'£\s*([\d,]+(?:\.\d{2})?)', text)
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
    print(f"→ Scrapuję: {url}")
    offers = []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Próbujemy różnych selektorów (Gumtree często zmienia klasy)
        listings = soup.find_all("div", class_=lambda c: c and any(x in str(c).lower() for x in ["listing", "card", "result", "ad"]) if c else False)

        if not listings:
            listings = soup.find_all("a", href=lambda h: h and ("/p/" in str(h) or "/ad/" in str(h)))

        for item in listings:
            title_tag = item.find(["h2", "h3", "a"])
            title = title_tag.get_text(strip=True) if title_tag else ""
            if not title or not is_relevant(title):
                continue

            link_tag = item.find("a", href=True)
            if not link_tag:
                continue
            link = urljoin(url, link_tag["href"])

            price = parse_price(item.get_text())
            if price is None or price <= 0:
                continue

            # Lokalizacja
            text = item.get_text()
            location = "NI / Belfast area"
            for loc in ["Belfast", "Antrim", "Down", "Londonderry", "Tyrone", "Armagh"]:
                if loc.lower() in text.lower():
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
                print(f"   Czekam {delay:.1f}s (grzeczność dla serwera)...")
                time.sleep(delay)

    all_offers.sort(key=lambda x: x["price"])

    today = datetime.now().strftime("%Y-%m-%d")
    filename = f"gumtree_offers_{today}.csv"

    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["title", "price", "location", "link"])
        writer.writeheader()
        writer.writerows(all_offers)

    print(f"\n\u2705 Zakończono. Znaleziono {len(all_offers)} ofert.")
    print(f"📁 Zapisano: {filename}\n")

    print("Najtańsze oferty:")
    for o in all_offers[:8]:
        print(f"£{o['price']:<6.0f} | {o['title'][:50]:<50} | {o['location']}")


if __name__ == "__main__":
    main()
