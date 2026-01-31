"""
Dieses Script:
- liest die Diyanet-Webseite
- findet automatisch alle verfügbaren Jahre (über das Menü)
- erstellt für jedes Jahr eine JSON-Datei
- speichert die Dateien im Ordner /dinigunler

Noch KEIN Automatismus – das kommt später.
"""

import requests
import json
import re
from bs4 import BeautifulSoup
from datetime import datetime

# ===============================
# Grundeinstellungen
# ===============================

BASE_URL = "https://vakithesaplama.diyanet.gov.tr/"
START_URL = BASE_URL + "dinigunler.php?yil=2026"

MIN_YEAR = 2026
MAX_YEAR = 2035

OUTPUT_DIR = "dinigunler"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (AzanUhrDiniGunlerBot)"
}

MONTHS_TR = {
    "ocak": 1,
    "şubat": 2, "subat": 2,
    "mart": 3,
    "nisan": 4,
    "mayıs": 5, "mayis": 5,
    "haziran": 6,
    "temmuz": 7,
    "ağustos": 8, "agustos": 8,
    "eylül": 9, "eylul": 9,
    "ekim": 10,
    "kasım": 11, "kasim": 11,
    "aralık": 12, "aralik": 12,
}

# ===============================
# Hilfsfunktionen
# ===============================

def fetch(url):
    print("Lade:", url)
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.text

def discover_year_links(html):
    """
    Sucht im Menü nach:
    - 2026 Yılı Dini Günler
    - icerik.php?icerik=XXX
    """
    soup = BeautifulSoup(html, "html.parser")
    year_links = {}

    for a in soup.find_all("a", href=True):
        text = a.get_text(strip=True)
        href = a["href"]

        m = re.search(r"(20\d{2})", text)
        if not m:
            continue

        year = int(m.group(1))
        if year < MIN_YEAR or year > MAX_YEAR:
            continue

        full_url = BASE_URL + href.lstrip("/")
        year_links[year] = full_url

    return year_links

def parse_year_page(year, html):
    """
    Liest die Tabelle eines Jahres aus
    und erzeugt:
    { "date": "YYYY-MM-DD", "title_tr": "..." }
    """
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if not table:
        return []

    events = []

    for row in table.find_all("tr"):
        text = row.get_text(" ", strip=True)

        m = re.search(
            r"(\d{1,2})\s+([A-Za-zÇĞİÖŞÜçğıöşü]+)\s+(\d{4})",
            text
        )
        if not m:
            continue

        day = int(m.group(1))
        month_name = m.group(2).lower().replace("ı", "i")
        year_found = int(m.group(3))

        if year_found != year:
            continue

        month = MONTHS_TR.get(month_name)
        if not month:
            continue

        date_iso = f"{year}-{month:02d}-{day:02d}"

        parts = text.split()
        title = " ".join(parts[-4:])  # grobe Näherung, reicht für Diyanet

        events.append({
            "date": date_iso,
            "title_tr": title
        })

    return events

# ===============================
# Hauptprogramm
# ===============================

def main():
    start_html = fetch(START_URL)
    year_links = discover_year_links(start_html)

    all_years = {}

    for year, url in year_links.items():
        html = fetch(url)
        events = parse_year_page(year, html)
        if events:
            all_years[year] = events

    # Dateien schreiben
    for year, events in all_years.items():
        path = f"{OUTPUT_DIR}/{year}.json"
        print("Schreibe:", path)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(events, f, ensure_ascii=False, indent=2)

    # index.json aktualisieren
    index = {
        "schema": 1,
        "min_year": MIN_YEAR,
        "prefetch_until": MAX_YEAR,
        "years_available": sorted(all_years.keys()),
        "last_updated_utc": datetime.utcnow().isoformat() + "Z"
    }

    with open(f"{OUTPUT_DIR}/index.json", "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    print("Fertig.")

if __name__ == "__main__":
    main()
