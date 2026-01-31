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

UA = "Mozilla/5.0 (compatible; dinigunler_diyanet_json/1.1)"

MONTHS_TR = {
    "ocak": 1,
    "subat": 2, "şubat": 2,
    "mart": 3,
    "nisan": 4,
    "mayis": 5, "mayıs": 5,
    "haziran": 6,
    "temmuz": 7,
    "agustos": 8, "ağustos": 8,
    "eylul": 9, "eylül": 9,
    "ekim": 10,
    "kasim": 11, "kasım": 11,
    "aralik": 12, "aralık": 12,
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

def norm_tr(s: str) -> str:
    # robustes Normalisieren für türkische I/İ/ı und Sonderzeichen
    s = s.strip()
    s = s.replace("İ", "I").replace("ı", "i")
    s = s.lower()
    return s

def discover_year_links(html: str) -> dict[int, str]:
    """
    Liest aus dem Menü alle Links, die auf '... Yılı Dini Günler' zeigen
    und mappt: Jahr -> absolute URL.
    """
    soup = BeautifulSoup(html, "html.parser")
    year_to_url: dict[int, str] = {}

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        text = " ".join(a.get_text(" ", strip=True).split())
        t = norm_tr(text)

        # nur Links, die wirklich Dini Günler meinen
        if not ("dini" in t and ("gun" in t or "gün" in t)):
            continue

        m = re.search(r"\b(20\d{2})\b", text)
        if not m:
            continue

        year = int(m.group(1))
        if year < MIN_YEAR or year > PREFETCH_UNTIL:
            continue

        year_to_url[year] = urljoin(BASE_URL, href)

    return year_to_url

def pick_best_table(soup: BeautifulSoup):
    """
    Nimmt die Tabelle, deren Header 'MILADI' und 'DINI GUNLER' enthält.
    Fallback: erste Tabelle.
    """
    tables = soup.find_all("table")
    if not tables:
        return None

    for table in tables:
        header_text = norm_tr(" ".join(table.get_text(" ", strip=True).split()))
        if ("miladi" in header_text or "miladi" in header_text) and ("dini" in header_text) and ("gun" in header_text or "gün" in header_text):
            return table

    return tables[0]

def extract_iso_date_from_row(year: int, row_text: str) -> str | None:
    """
    Diyanet kann Datum so liefern:
      02-OCAK-2026
    oder so:
      02 OCAK 2026
    Wir akzeptieren beides.
    """
    # Format: DD-AY-YYYY (mit - oder / oder .)
    m = re.search(r"\b(\d{1,2})\s*[-/\.]\s*([A-Za-zÇĞİÖŞÜçğıöşü]+)\s*[-/\.]\s*(\d{4})\b", row_text)
    if not m:
        # Format: DD AY YYYY (mit spaces)
        m = re.search(r"\b(\d{1,2})\s+([A-Za-zÇĞİÖŞÜçğıöşü]+)\s+(\d{4})\b", row_text)
    if not m:
        return None

    day = int(m.group(1))
    mon_raw = m.group(2)
    year_found = int(m.group(3))
    if year_found != year:
        return None

    mon_key = norm_tr(mon_raw).replace("ı", "i")
    mon = MONTHS_TR.get(mon_key)
    if not mon:
        return None

    return f"{year:04d}-{mon:02d}-{day:02d}"

def parse_year_page(year: int, html: str) -> list[dict]:
    """
    Parst die Diyanet-Tabelle und erzeugt:
      [{"date":"YYYY-MM-DD","title_tr":"..."}]
    Entfernt Leerzeilen/Platzhalter.
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

        title = (cols[-1] or "").strip()
        if not title:
            continue
        tl = norm_tr(title)
        if tl in {"dini gunler", "dini günler"}:
            continue
        if re.fullmatch(r"[\.\-–—\s]+", title):
            continue

        joined = " | ".join(cols)
        iso = extract_iso_date_from_row(year, joined)
        if not iso:
            continue

        events.append({"date": iso, "title_tr": title})

    # Duplikate entfernen
    uniq = {}
    for e in events:
        uniq[(e["date"], e["title_tr"])] = e
    out = list(uniq.values())
    out.sort(key=lambda x: (x["date"], x["title_tr"]))
    return out

def delete_past_year_files(current_year: int):
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

    # Zieljahre: aktuelles Jahr bis PREFETCH_UNTIL, aber nur wenn Diyanet-Link existiert
    target_years = [y for y in range(current_year, PREFETCH_UNTIL + 1) if y in year_links]

    delete_past_year_files(current_year)

    years_written = []
    for y in target_years:
        url = year_links[y]
        html = http_get(url)
        events = parse_year_page(y, html)

        print(f"year={y} url={url} events={len(events)}")

        if not events:
            continue

        save_json(os.path.join(OUT_DIR, f"{y}.json"), events)
        years_written.append(y)

    # years_available aus Dateien aufbauen
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
    print("years_written:", years_written)
    print("years_available:", years_available)
    print("done:", utc_now_iso())

if __name__ == "__main__":
    main()
