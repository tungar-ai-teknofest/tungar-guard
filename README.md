# TUNGAR-Guard

Streamlit tabanlı tek sayfalık bir uygulama. Sohbet ve
video analiz aynı akışta; sol tarafta chatbot tarzı geçmiş sohbet listesi,
üstte KPI özeti. Video analiz **TEKNOFEST EVREN çıkarım servisi**
(`evren-llmapi.ssyz.org.tr`) ile çalışır, otomasyon/KPI tarafı gerçek
SQLite ile.

## Kurulum

```bash
pip install -r requirements.txt
```

`yolov8n.pt` proje kökünde olmalı (paketle birlikte geliyor).

## EVREN API anahtarınızı girin

```bash
export EVREN_API_KEY="sk-evren-teamNN-XXXXXXXX"   # size e-posta ile iletilen anahtar
```

Bu kadar — `config.py` içindeki `EVREN_BASE_URL` ve `EVREN_MODEL`
(`llm-large`, video+Türkçe özet+JSON'u tek çağrıda üretir) zaten
dokümantasyona göre ayarlı. Anahtarı girmezseniz sistem otomatik mock
moda düşer (DB/ajan/KPI gerçek çalışır, sadece AI çağrıları sahte).

## Çalıştırma

```bash
streamlit run app.py
```

Tarayıcıda `http://localhost:8501` açılır — Colab/tünel gerekmiyor,
tamamen kendi bilgisayarınızda çalışır.

## Nasıl çalışıyor

1. YOLO (yerel, sizin eğittiğiniz model) videoyu tarar, tetik anlarını bulur
   (K1: tehlike/araç sınıfı, K2: kişi-araç yakınlığı/çarpışma, K3: periyodik tarama)
2. Her tetik için ~12 saniyelik bir **video klibi** kesilir (EVREN API kare
   değil klip kabul ediyor — dokümantasyonun §7.5'inde açıklandığı gibi
   istek başına en fazla 2 görüntüyle sınırlı olduğu için klip yaklaşımı
   kullanılıyor)
3. Klip, `llm-large` modeline şema kısıtlı (`strict: True`) istekle
   gönderilir — ayrıştırma hatası riski yok
4. Şiddet seviyesine göre: Kritik/Yüksek/Orta → onay ister, Düşük → sadece tavsiye

## Bilinen sınırlar / EVREN dokümantasyonundan notlar

- İstemci zaman aşımı 1800sn olarak ayarlı (`config.EVREN_TIMEOUT`) — API bu kadar sürebiliyor
- Kısa klip kullanımı önerilir (biz ~12sn kullanıyoruz, önerilen aralıktayız)
- Aynı videoya art arda soru sormak (§7.2 prefix cache) çok daha hızlı —
  şu an her tetik ayrı klip gönderiyor, sohbet üzerinden takip sorularında
  bu avantaj kullanılmıyor (ileride geliştirilebilir)
- Sonsuz döngü / otomatik tekrar deneme yapılmıyor (dokümantasyon §12 bunu
  açıkça istiyor)

## Klasörler

```
app.py            # arayüz + video/sohbet akışı
config.py         # API_MODE (evren/local/mock) + EVREN ayarları
models/           # veri tipleri
database/         # SQLite katmanı
agents/           # Analysis / Decision / Validation ajanları
engine/           # pipeline + KPI motoru
vision/           # YOLO dikkat katmanı, EVREN istemcisi, yerel model (opsiyonel), mock araçlar
chat/             # sohbet asistanı
```

Kabul testi ve ham SQL sorgu arayüzü kenar çubuğundaki
"Geliştirici Araçları" altında.
