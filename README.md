# Dini Günler – JSON API (Diyanet)

Statische, automatisch gepflegte JSON-Daten für islamische religiöse Tage  
bereitgestellt über GitHub Pages.

Autor: Nijat Khalilov

---

## Deutsch

### Zweck

Dieses Repository stellt **Dini Günler** als **JSON-Dateien** bereit.
Die Daten werden automatisch aus öffentlich zugänglichen Seiten der
**Diyanet İşleri Başkanlığı** extrahiert und regelmäßig aktualisiert.

Gedacht für Clients, die **ohne eigenes Backend** arbeiten
(z. B. ESP32-Gebetsuhren, Kalender, Displays).

---

### Zugriff

Index (verfügbare Jahre):  
https://nkhalilov3.github.io/dinigunler_diyanet_json/dinigunler/index.json

Jahresdatei (Beispiel):  
https://nkhalilov3.github.io/dinigunler_diyanet_json/dinigunler/2026.json

---

### Datenformat

```json
{
  "date": "21-02-2035",
  "name_tr": "KURBAN BAYRAMI 4. Gün",
  "name_de": "Opferfest 4. Tag"
}
