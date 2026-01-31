# Dini Günler – Automatic JSON API (Diyanet)

Automatisch gepflegte JSON-Daten für islamische religiöse Tage (Dini Günler),
bereitgestellt über GitHub Pages.

**Autor:** Nijat Khalilov  
**Status:** Stabil / vollautomatisch

---

## 🌐 Sprachen / Languages
- [Deutsch](#deutsch)
- [Türkçe](#türkçe)

---

## Deutsch

### Überblick

Dieses Repository stellt **Dini Günler** als **statische JSON-API** bereit.
Die Daten werden regelmäßig aus den öffentlich zugänglichen Seiten der
**Diyanet İşleri Başkanlığı** extrahiert und automatisch aktualisiert.

Das Projekt ist besonders für **Embedded-Systeme (z. B. ESP32-Gebetsuhren)**,
Kalender-Anwendungen und Informationsdisplays geeignet.

---

### Datenzugriff

**Index (verfügbare Jahre):**  
https://nkhalilov3.github.io/dinigunler_diyanet_json/dinigunler/index.json

**Jahresdatei (Beispiel):**  
https://nkhalilov3.github.io/dinigunler_diyanet_json/dinigunler/2026.json

---

### Datenformat

```json
{
  "date": "21-02-2035",
  "name_tr": "KURBAN BAYRAMI 4. Gün",
  "name_de": "Opferfest 4. Tag"
}
