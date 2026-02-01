# Dini Günler – JSON API (Diyanet)

Statische, automatisch gepflegte JSON-Daten für islamische religiöse Tage  
İslami dini günler için otomatik olarak güncellenen statik JSON verileri


---

## Zweck / Amaç

Dieses Repository stellt **Dini Günler** als **JSON-Dateien** bereit.  
Bu repository **Dini Günler** verilerini **JSON dosyaları** olarak sunar.

Die Daten werden automatisch aus öffentlich zugänglichen Seiten der  
**Diyanet İşleri Başkanlığı** extrahiert und regelmäßig aktualisiert.  
Veriler, **Diyanet İşleri Başkanlığı**’nın herkese açık sayfalarından otomatik olarak alınır ve düzenli olarak güncellenir.

Gedacht für Clients ohne eigenes Backend  
(z. B. ESP32-Gebetsuhren, Kalender, Displays).  
Backend gerektirmeyen istemciler için tasarlanmıştır  
(ör. ESP32 ezan saatleri, takvimler, ekranlar).

---

## Zugriff / Erişim

Index (verfügbare Jahre / mevcut yıllar):  
https://nkhalilov3.github.io/dinigunler_diyanet_json/dinigunler/index.json

Jahresdatei – Beispiel / Yıllık dosya – örnek:  
https://nkhalilov3.github.io/dinigunler_diyanet_json/dinigunler/2026.json

---

## Datenformat / Veri Formatı

```json
{
  "date": "21-02-2035",
  "name_tr": "KURBAN BAYRAMI 4. Gün",
  "name_de": "Opferfest 4. Tag"
}
