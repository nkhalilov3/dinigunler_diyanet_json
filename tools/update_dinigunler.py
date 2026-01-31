#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import re
import ssl
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin
from urllib.request import Request, urlopen


DIYANET_BASE = "https://vakithesaplama.diyanet.gov.tr"
DIYANET_INDEX_URL = f"{DIYANET_BASE}/"
DIYANET_DINIGUNLER_URL = f"{DIYANET_BASE}/dinigunler.php?yil={{year}}"

MIN_YEAR = 2026
PREFETCH_UNTIL = 2035

OUT_DIR = "dinigunler"
INDEX_PATH = os.path.join(OUT_DIR, "index.json")

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) dinigunler_diyanet_json/2.0"
HTTP_TIMEOUT = 30


MONTHS_TR = {
    "OCAK": 1,
    "ŞUBAT": 2, "SUBAT": 2,
    "MART": 3,
    "NİSAN": 4, "NISAN": 4,
    "MAYIS": 5,
    "HAZİRAN": 6, "HAZIRAN": 6,
    "TEMMUZ": 7,
    "AĞUSTOS": 8, "AGUSTOS": 8,
    "EYLÜL": 9, "EYLUL": 9,
    "EKİM": 10, "EKIM": 10,
    "KASIM": 11,
    "ARALIK": 12,
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def http_get_text(url: str, timeout: int = HTTP_TIMEOUT) -> str:
    req = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,*/*",
        },
        method="GET",
    )
    ctx = ssl.create_default_context()
    with urlopen(req, context=ctx, timeout=timeout) as resp:
        raw = resp.read()

    # Diyanet: meist UTF-8, manchmal TR Encodings
    for enc in ("utf-8", "iso-8859-9", "cp1254"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def save_json(path: str, obj: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def is_dashes_only(name: str) -> bool:
    s = (name or "").strip()
    if not s:
        return True
    # nur -, —, –, Punkte/Spaces
    return re.fullmatch(r"[-–—\.\s]+", s) is not None


class _DiyanetMenuYearLinkParser(HTMLParser):
    """
    Extrahiert Links aus dem HTML, die im Text ein Jahr tragen und in Richtung
    Dini Günler zeigen (dinigunler.php?yil=... oder icerik.php?icerik=...).

    Ergebnis: Dict[year] = absolute_url
    """
    def __init__(self) -> None:
        super().__init__()
        self._in_a = False
        self._a_href: Optional[str] = None
        self._buf: List[str] = []
        self.year_to_href: Dict[int, str] = {}

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "a":
            return
        href = None
        for k, v in attrs:
            if k.lower() == "href":
                href = v
                break
        self._in_a = True
        self._a_href = href
        self._buf = []

    def handle_endtag(self, tag):
        if tag.lower() != "a":
            return
        if self._in_a and self._a_href:
            text = re.sub(r"\s+", " ", "".join(self._buf)).strip()
            low = text.lower()

            # Nur wenn Text klar auf Dini Günler zeigt (verhindert False Positives)
            if "dini" in low and ("gün" in low or "gun" in low):
                m = re.search(r"\b(20\d{2})\b", text)
                if m:
                    y = int(m.group(1))
                    if MIN_YEAR <= y <= PREFETCH_UNTIL:
                        self.year_to_href[y] = self._a_href

        self._in_a = False
        self._a_href = None
        self._buf = []

    def handle_data(self, data):
        if self._in_a and data:
            self._buf.append(data)


class _TdTableParser(HTMLParser):
    """
    Parst alle <tr><td>... als rows.
    """
    def __init__(self) -> None:
        super().__init__()
        self.in_tr = False
        self.in_td = False
        self._cell_buf: List[str] = []
        self._row: List[str] = []
        self.rows: List[List[str]] = []

    def handle_starttag(self, tag, attrs):
        t = tag.lower()
        if t == "tr":
            self.in_tr = True
            self._row = []
        elif t == "td" and self.in_tr:
            self.in_td = True
            self._cell_buf = []

    def handle_endtag(self, tag):
        t = tag.lower()
        if t == "td" and self.in_td:
            self.in_td = False
            cell = "".join(self._cell_buf)
            cell = re.sub(r"\s+", " ", cell).strip()
            self._row.append(cell)
        elif t == "tr" and self.in_tr:
            self.in_tr = False
            if any(c.strip() for c in self._row):
                self.rows.append(self._row)

    def handle_data(self, data):
        if self.in_td and data:
            self._cell_buf.append(data)


def _parse_greg_iso(greg_day: str, greg_month_year: str) -> Optional[str]:
    # greg_day: "01" ; greg_month_year: "OCAK-2026" oder "OCAK - 2026"
    d = greg_day.strip()
    if not d:
        return None
    mday = re.match(r"(\d{1,2})", d)
    if not mday:
        return None
    day_num = int(mday.group(1))

    text = greg_month_year.upper()

    m = re.search(r"([A-ZÇĞİÖŞÜ]+)\s*-\s*(20\d{2})", text)
    if not m:
        m = re.search(r"([A-ZÇĞİÖŞÜ]+)\s*(20\d{2})", text)
    if not m:
        return None

    mon_txt = m.group(1).strip()
    year_num = int(m.group(2))

    mon_key = (
        mon_txt.replace("İ", "I")
        .replace("Ş", "S")
        .replace("Ğ", "G")
        .replace("Ü", "U")
        .replace("Ö", "O")
        .replace("Ç", "C")
    )
    mon = MONTHS_TR.get(mon_txt) or MONTHS_TR.get(mon_key)
    if not mon:
        return None

    try:
        return date(year_num, mon, day_num).isoformat()
    except Exception:
        return None


def parse_dinigunler_year_html(html_text: str) -> List[Dict[str, Any]]:
    """
    Liest die Diyanet-Tabelle wie in deiner funktionierenden Datei:
    rows mit len==7:
      hijri_day, hijri_month, hijri_year, greg_day, greg_month_year, weekday, name
    Filter:
      - name leer oder nur '-----' => überspringen
    Ausgabe:
      [{"date":"YYYY-MM-DD","name_tr":"..."}]
    """
    p = _TdTableParser()
    p.feed(html_text)

    rows = [r for r in p.rows if len(r) == 7]
    out: List[Dict[str, Any]] = []

    for r in rows:
        hijri_day, hijri_month, hijri_year, greg_day, greg_month_year, weekday, name = r
        name = re.sub(r"\s+", " ", (name or "")).strip()

        # Deine Anforderung: alles mit "-----" NICHT übernehmen
        if is_dashes_only(name):
            continue

        iso = _parse_greg_iso(greg_day, greg_month_year)
        if not iso:
            # Wenn das Datum nicht parsebar ist, skippen (lieber sauber als falsche Daten)
            continue

        out.append({
            "date": iso,
            "name_tr": name
        })

    # Duplikate entfernen
    uniq = {}
    for it in out:
        uniq[(it["date"], it["name_tr"])] = it
    out = list(uniq.values())
    out.sort(key=lambda x: (x["date"], x["name_tr"]))
    return out


def discover_year_urls() -> Dict[int, str]:
    """
    1) Menü von Startseite parsen (kann Links für mehrere Jahre enthalten).
    2) Fallback: für jedes Zieljahr den Standard-Link dinigunler.php?yil=YYYY probieren.
       (Falls Menü komisch ist, haben wir trotzdem eine Chance.)
    """
    html = http_get_text(DIYANET_INDEX_URL)
    parser = _DiyanetMenuYearLinkParser()
    parser.feed(html)

    year_to_url: Dict[int, str] = {}
    for y, href in parser.year_to_href.items():
        year_to_url[y] = urljoin(DIYANET_BASE + "/", href)

    # Fallback: Standard-URL anbieten (wird später nur benutzt, wenn sie wirklich Events liefert)
    for y in range(MIN_YEAR, PREFETCH_UNTIL + 1):
        year_to_url.setdefault(y, DIYANET_DINIGUNLER_URL.format(year=y))

    return year_to_url


def delete_past_year_files(current_year: int) -> None:
    if not os.path.isdir(OUT_DIR):
        return
    for fn in os.listdir(OUT_DIR):
        m = re.fullmatch(r"(\d{4})\.json", fn)
        if not m:
            continue
        y = int(m.group(1))
        if y < current_year:
            try:
                os.remove(os.path.join(OUT_DIR, fn))
            except Exception:
                pass


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)

    now_year = datetime.now(timezone.utc).year
    current_year = max(now_year, MIN_YEAR)

    delete_past_year_files(current_year)

    year_to_url = discover_year_urls()

    years_written: List[int] = []
    for y in range(current_year, PREFETCH_UNTIL + 1):
        url = year_to_url.get(y) or DIYANET_DINIGUNLER_URL.format(year=y)
        try:
            html = http_get_text(url)
            items = parse_dinigunler_year_html(html)
            print(f"year={y} url={url} rows={len(items)}")

            # Wenn Diyanet für das Jahr noch nichts liefert: nichts schreiben
            if not items:
                continue

            save_json(os.path.join(OUT_DIR, f"{y}.json"), items)
            years_written.append(y)

            # kleine Pause (freundlich gegenüber Server)
            time.sleep(0.15)
        except Exception as e:
            print(f"year={y} FAILED: {e}")

    # years_available aus Dateien aufbauen
    years_available: List[int] = []
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
        "last_updated_utc": utc_now_iso(),
    }
    save_json(INDEX_PATH, index)

    print("years_written:", years_written)
    print("years_available:", years_available)
    print("done:", utc_now_iso())


if __name__ == "__main__":
    main()
