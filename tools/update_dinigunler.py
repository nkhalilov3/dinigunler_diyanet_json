# pip install -r tools/requirements.txt

import os
import re
import json
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://vakithesaplama.diyanet.gov.tr/"
DISCOVERY_URL = urljoin(BASE_URL, "dinigunler.php?yil=2026")

MIN_YEAR = 2026
PREFETCH_UNTIL = 2035

OUT_DIR = "dinigunler"
INDEX_PATH = os.path.join(OUT_DIR, "index.json")

UA = "Mozilla/5.0 (compatible; dinigunler_diyanet_json/1.0)"

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

def utc_now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def http_get(url: str) -> str:
    r = requests.get(url, headers={"User-Agent": UA}, timeout=30)
    r.raise_for_status()
    return r.text

def save_json(path: str, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def discover_year_links(html: str) -> dict[int, str]:
    """
    Liest aus dem Menü alle Links der Form:
      - dinigunler.php?yil=2026
      - icerik.php?icerik=154 (Text enthält z.B. '2027 Yılı Dini Günler')
    Map: Jahr -> absolute URL
    """
    soup = BeautifulSoup(html, "html.parser")
    year_to_url: dict[int, str] = {}

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        text = " ".join(a.get_text(" ", strip=True).split())

        year = None

        # Muster 1: ?yil=YYYY
        m1 = re.search(r"(?:^|[?&])yil=(\d{4})", href)
        if m1:
            year = int(m1.group(1))
        else:
            # Muster 2: Jahr im Linktext, wenn es um Dini Günler geht
            m2 = re.search(r"\b(20\d{2})\b", text)
            if m2 and ("dini" in text.lower() and ("günler" in text.lower() or "gunler" in text.lower())):
                year = int(m2.group(1))

        if year is None:
            continue
        if year < MIN_YEAR or year > PREFETCH_UNTIL:
            continue

        abs_url = urljoin(BASE_URL, href)
        year_to_url[year] = abs_url

    return year_to_url

def pick_best_table(soup: BeautifulSoup):
    """
    Diyanet-Seite hat i.d.R. eine Tabelle mit Spalten u.a. 'MİLADİ' und 'DİNİ GÜNLER'.
    Wir suchen die Tabelle, die diese Header enthält.
    """
    for table in soup.find_all("table"):
        headers = " ".join(table.get_text(" ", strip=True).split()).lower()
        if ("miladi" in headers or "m\u0131ladi" in headers) and ("dini" in headers) and ("gün" in headers or "gun" in headers):
            return table
    # fallback: erste Tabelle
    return soup.find("table")

def parse_year_page(year: int, html: str) -> list[dict]:
    """
    Parst die Jahres-Tabelle und erzeugt:
      [{"date":"YYYY-MM-DD","title_tr":"..."}]
    Leere/Platzhalter-Zeilen werden verworfen.
    """
    soup = BeautifulSoup(html, "html.parser")
    table = pick_best_table(soup)
    if not table:
        return []

    events = []
    for tr in table.find_all("tr"):
        cols = [" ".join(td.get_text(" ", strip=True).split()) for td in tr.find_all(["td", "th"])]
        if len(cols) < 2:
            continue

        joined = " | ".join(cols)

        # Titel: meist letzte Spalte (Dini Günler)
        title = cols[-1].strip()

        # Header/Platzhalter/Leer raus
        if not title:
            continue
        if title.lower() in {"dini günler", "dini gunler"}:
            continue
        if re.fullmatch(r"[\.\-–—\s]+", title):
            continue

        # Datum: "DD <MONAT> YYYY"
        dm = re.search(
            r"\b(\d{1,2})\s+([A-Za-zÇĞİÖŞÜçğıöşü]+)\s+(\d{4})\b",
            joined
        )
        if not dm:
            continue

        day = int(dm.group(1))
        mon_name_raw = dm.group(2).lower()
        year_found = int(dm.group(3))
        if year_found != year:
            continue

        mon_key = mon_name_raw.replace("ı", "i")
        mon = MONTHS_TR.get(mon_key) or MONTHS_TR.get(mon_name_raw)
        if not mon:
            continue

        iso = f"{year:04d}-{mon:02d}-{day:02d}"

        events.append({"date": iso, "title_tr": title})

    # Duplikate entfernen
    uniq = {}
    for e in events:
        uniq[(e["date"], e["title_tr"])] = e
    events = list(uniq.values())
    events.sort(key=lambda x: (x["date"], x["title_tr"]))
    return events

def delete_past_year_files(current_year: int):
    """
    Löscht alle Jahresdateien < current_year (abgelaufene Jahre).
    """
    if not os.path.isdir(OUT_DIR):
        return
    for fn in os.listdir(OUT_DIR):
        m = re.fullmatch(r"(\d{4})\.json", fn)
        if not m:
            continue
        y = int(m.group(1))
        if y < current_year:
            os.remove(os.path.join(OUT_DIR, fn))

def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    now_year = datetime.now(timezone.utc).year
    current_year = max(now_year, MIN_YEAR)

    discovery_html = http_get(DISCOVERY_URL)
    year_links = discover_year_links(discovery_html)

    # Zieljahre: von max(current_year, MIN_YEAR) bis PREFETCH_UNTIL
    target_years = [y for y in range(current_year, PREFETCH_UNTIL + 1) if y in year_links]

    # abgelaufene Jahre löschen
    delete_past_year_files(current_year)

    years_written = []
    for y in target_years:
        url = year_links[y]
        html = http_get(url)
        events = parse_year_page(y, html)
        if not events:
            continue
        save_json(os.path.join(OUT_DIR, f"{y}.json"), events)
        years_written.append(y)

    # years_available aus Dateien neu aufbauen
    years_available = []
    for fn in os.listdir(OUT_DIR):
        m = re.fullmatch(r"(\d{4})\.json", fn)
        if m:
            years_available.append(int(m.group(1)))
    years_available = sorted(set(years_available))

    index = {
        "schema": 1,
        "min_year": MIN_YEAR,
        "prefetch_until": PREFETCH_UNTIL,
        "years_available": years_available,
        "last_updated_utc": utc_now_iso()
    }
    save_json(INDEX_PATH, index)

    print("discovered_years:", sorted(year_links.keys()))
    print("target_years:", target_years)
    print("years_available:", years_available)
    print("done:", utc_now_iso())

if __name__ == "__main__":
    main()
