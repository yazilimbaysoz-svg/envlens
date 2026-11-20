# envlens — Instagram İçerik Paketi

## Karusel Sırası

| Slayt | Dosya | İçerik |
| --- | --- | --- |
| 01 | `01_envlens_kapak.png` | Kapak + problem: eksik key, sızdırılmış şifre, drift, stale |
| 02 | `02_envlens_mimari.png` | Gerçek terminal çıktısı + 4 aşamalı mimari şeması |
| 03 | `03_envlens_kurulum.png` | Kurulum komutları, GitHub linki ve çağrı |

Tüm görseller 1080x1350 px, koyu terminal estetiğinde ve `generate.py` ile üretilmiştir.

---

## Instagram Açıklama Metni

Sabah 03:12. Deploy patladı. Sebep: kimsenin tanımlamadığı tek bir environment variable. 🚨

Tam olarak bu yüzden **envlens**'i yazdık: kodunu, `.env` dosyalarını, Docker Compose'u ve GitHub Actions'ı tarayıp ortam değişkeni kazalarını deploy'dan **önce** yakalayan, sıfır bağımlılıklı küçük bir CLI.

🔍 5 kural:
• **MISSING** — kod okur, kimse tanımlamamış
• **UNDECLARED** — key var ama `.env.example` yok
• **STALE** — template'te durup kimsenin okumadığı key
• **LEAK** — commit'lenmiş gerçek şifre/token
• **DRIFT** — staging ve prod farklı değerler

⚡ Neden farklı?
– Python standart kütüphanesiyle yazıldı: runtime bağımlılığı **0**
– Ağ çağrısı yok, telemetri yok, gizli değerleri asla yazdırmaz
– JSON + Markdown raporlarıyla doğrudan CI'a girer
– 10+ dil ve GitHub Actions `${{ secrets.X }}` referanslarını anlar

Kurulumu 10 saniye:
```
uv tool install envlens
envlens scan . --fail-on high
```

MIT lisanslı, tamamen açık kaynak. Bir sonraki 03:12 incident'ini bir yıldızla birlikte engelleyelim ⭐

👇 Kaydır: problem, mimari, kurulum.
🔗 github.com/yazilimbaysoz-svg/envlens

---

## Etiketler

#envlens #baysozyazilim #acikkaynak #opensource #devsecops #security #siberguvenlik #python #cli #devtools #github #ci #cicd #yaml #docker #environmentvariables #secretsmanagement #configdrift #yazilim #softwareengineering #developertools #cybersecurity #zerodependencies #hacktoberfest

---

## Hikaye / Reels Metni (15 sn)

1. **0-3 sn:** Ekranda kırmızı hata: `STRIPE_KEY missing (app.py:42)` → "Bir eksik key, tüm deploy çöktü."
2. **3-7 sn:** Terminalde `envlens scan . --fail-on high` çalışıyor, bulgular akıyor.
3. **7-11 sn:** 4 aşamalı mimari: KAYNAK → SCANNER → ANALYSIS → CI EXIT.
4. **11-15 sn:** `PASS  No environment configuration issues found.` → "envlens ile rahat uyu. Star'ı unutma ⭐"

---

## Paylaşım Notu

İlk yorum olarak kurulum komutunu yapıştırın; profil linkini GitHub reposuna güncelleyin. Gönderiyi 24 saat sonra "Güncellemeler" formatında repoya eklenen yeni özelliklerle takip edin.
