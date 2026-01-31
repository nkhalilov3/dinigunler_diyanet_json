#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import re
import ssl
import time
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin
from urllib.request import Request, urlopen


DIYANET_BASE = "https://vakithesaplama.diyanet.gov.tr"
DIYANET_INDEX_URL = f"{DIYANET_BASE}/"
DIYANET_DINIGUNLER_URL = f"{DIYANET_BASE}/dinigunler.php?yil={{year}}"

MIN_YEAR = 2026
PREFETCH_UNTIL = 2035

OUT_DIR = "dinigunler"
INDEX_PATH = os.path.join(OUT_DIR, "index.json")

USER_AGENT = "Mozilla/5.0 dinigunler_diyanet_json/2.2"
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

# --- Übersetzungen / Regeln ---
# Hinweis: Diyanet schreibt oft in Großbuchstaben. Wir normalisieren robust.
def _norm_tr(s: str) -> str:
    s = (s or "").strip()
    # Großschreibung vereinheitlichen
    s = s.upper()
    # Türkische Sonderzeichen -> ASCII (nur fürs Matching)
    s = (
        s.replace("İ", "I")
         .replace("İ", "I")
         .replace("Ş", "S")
         .replace("Ğ", "G")
         .replace("Ü", "U")
         .replace("Ö", "O")
         .replace("Ç", "C")
         .replace("Â", "A")
         .replace("Ê", "E")
         .replace("Ô", "O")
    )
    # Apostrophe/seltsame Leerzeichen vereinheitlichen
    s = s.replace("’", "'")
    s = re.sub(r"\s+", " ", s)
    return s

def _extract_gun_no(s: str) -> Optional[int]:
    # "4. Gün" / "4. GUN" / "4.GUN"
    m = re.search(r"\b(\d+)\s*\.\s*GUN\b", s)
    if not m:
        m = re.search(r"\b(\d+)\s*\.\s*GÜN\b", s)  # falls doch
    return int(m.group(1)) if m else None

def tr_to_de(name_tr: str) -> str:
    """
    Wandelt Diyanet-Bezeichnungen (TR) in DE um.
    Erhält ggf. "X. Gün" als "X. Tag".
    """
    raw = (name_tr or "").strip()
    n = _norm_tr(raw)

    # Tag-Nummer merken (z.B. Bayram 1/2/3/4)
    gun_no = _extract_gun_no(n)

    # Grund-Mappings (ohne Tageszahl)
    # Reihenfolge: spezifisch -> allgemein
    if "KURBAN BAYRAMI" in n:
        base = "Opferfest"
    elif "RAMAZAN BAYRAMI" in n:
        base = "Zuckerfest"
    elif "AREFE" in n:
        # Arefe = Vorabend/Tag davor (wird bei Diyanet meist fürs Opferfest angegeben)
        base = "Arefe (Vorabend des Festes)"
    elif "KADIR GECESI" in n:
        base = "Nacht der Bestimmung (Lailat al-Qadr)"
    elif "MIRAC KANDILI" in n:
        base = "Miraj-Nacht"
    elif "REGAIB KANDILI" in n:
        base = "Regaib-Nacht"
    elif "BERAT KANDILI" in n:
        base = "Nacht der Vergebung (Berat-Nacht)"
    elif "MEVLID KANDILI" in n:
        base = "Mawlid (Geburt des Propheten)"
    elif "HICRI YILBASI" in n:
        base = "Islamisches Neujahr (Hidschri-Neujahr)"
    elif "ASURE GUNU" in n:
        base = "Aschura-Tag"
    elif "UC AYLARIN BASLANGICI" in n or "3 AYLARIN BASLANGICI" in n:
        base = "Beginn der drei heiligen Monate"
    elif "RAMAZAN BASLANGICI" in n or "RAMAZANIN ILK GUNU" in n or "RAMAZAN'IN ILK GUNU" in n:
        base = "Beginn des Ramadan"
    elif "RAMAZAN'IN SON 10 GECESI" in n or "RAMAZANIN SON 10 GECESI" in n:
        base = "Letzte 10 Nächte des Ramadan"
    elif "TESRIK GUNLERI" in n:
        base = "Taschrik-Tage"
    elif "ZILHICCE" in n and "ILK 10" in n:
        base = "Erste 10 Tage des Dhul-Hiddscha"
    else:
        # Fallback: nicht erkannt -> TR-Text übernehmen (besser als falsche Übersetzung)
        base = raw

    # Tageszahl ergänzen, wenn vorhanden und es ein mehrtägiges Fest ist
    if gun_no is not None and ("BAYRAMI" in n):
        return f"{base} {gun_no}. Tag"

    # Wenn TR schon sowas wie "4. Gün" enthält, aber nicht BAYRAMI:
    if gun_no is not None and "GUN" in n:
        return re.sub(r"\b(\d+)\s*\.\s*GUN\b", r"\1. Tag", base)

    return base


def utc_now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def http_get_text(url: str) -> str:
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, context=ssl.create_default_context(), timeout=HTTP_TIMEOUT) as r:
        raw = r.read()

    for enc in ("utf-8", "iso-8859-9", "cp1254"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            pass
    return raw.decode("utf-8", errors="replace")


def save_json(path: str, obj: Any):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def is_dashes_only(s: str) -> bool:
    return not s or re.fullmatch(r"[-–—.\s]+", s.strip())


def iso_to_ddmmyyyy(iso: str) -> str:
    # "2035-02-21" -> "21-02-2035"
    y, m, d = iso.split("-")
    return f"{d}-{m}-{y}"


class _DiyanetMenuYearLinkParser(HTMLParser):
    """
    Extrahiert Links aus dem HTML, die im Text ein Jahr tragen und in Richtung
    Dini Günler zeigen (dinigunler.php?yil=... oder icerik.php?icerik=...).

    Ergebnis: Dict[year] = href
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
            cell = re.sub(r"\s+", " ", "".join(self._cell_buf)).strip()
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

    # Monatsname normalisieren (für Lookup)
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
    rows mit len==7:
      hijri_day, hijri_month, hijri_year, greg_day, greg_month_year, weekday, name_tr
    Filter:
      - name_tr leer oder nur '-----' => überspringen
    Ausgabe:
      [{"date":"DD-MM-YYYY","name_tr":"...","name_de":"..."}]
    """
    p = _TdTableParser()
    p.feed(html_text)

    rows = [r for r in p.rows if len(r) == 7]
    out: List[Dict[str, Any]] = []

    for r in rows:
        _, _, _, greg_day, greg_month_year, _, name_tr = r
        name_tr = re.sub(r"\s+", " ", (name_tr or "")).strip()

        # alles mit "-----" NICHT übernehmen
        if is_dashes_only(name_tr):
            continue

        iso = _parse_greg_iso(greg_day, greg_month_year)
        if not iso:
            continue

        out.append({
            "date": iso_to_ddmmyyyy(iso),
            "name_tr": name_tr,
            "name_de": tr_to_de(name_tr),
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
    2) Fallback: für jedes Zieljahr den Standard-Link dinigunler.php?yil=YYYY anbieten.
    """
    html = http_get_text(DIYANET_INDEX_URL)
    parser = _DiyanetMenuYearLinkParser()
    parser.feed(html)

    year_to_url: Dict[int, str] = {}
    for y, href in parser.year_to_href.items():
        year_to_url[y] = urljoin(DIYANET_BASE + "/", href)

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
            print(f"year={y} url={url} items={len(items)}")

            if not items:
                continue

            save_json(os.path.join(OUT_DIR, f"{y}.json"), items)
            years_written.append(y)
            time.sleep(0.15)
        except Exception as e:
            print(f"year={y} FAILED: {e}")

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
