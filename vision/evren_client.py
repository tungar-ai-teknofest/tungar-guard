import base64
import json
from typing import Optional, List

import config
from vision.schema import VisionAnalysisResult

EVREN_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "genel_ozet": {"type": "string"},
        "olaylar": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "olay_id": {"type": "string"},
                    "event_start": {"type": "string"},
                    "event_peak": {"type": "string"},
                    "event_end": {"type": "string"},
                    "faz": {"type": "string", "enum": ["baslangic", "gelisim", "sonuc"]},
                    "incident_type": {"type": "string"},
                    "severity_level": {"type": "string", "enum": ["Dusuk", "Orta", "Yuksek", "Kritik"]},
                    "guven": {"type": "number"},
                    "gerekce": {"type": "string"},
                },
                "required": ["olay_id", "event_start", "event_peak", "event_end", "faz",
                             "incident_type", "severity_level", "guven", "gerekce"],
                "additionalProperties": False,
            },
        },
        "risk": {"type": "string", "enum": ["Dusuk", "Orta", "Yuksek", "Kritik"]},
        "onerilen_aksiyonlar": {"type": "array", "items": {"type": "string"}},
        "tetiklenen_araclar": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["genel_ozet", "olaylar", "risk", "onerilen_aksiyonlar", "tetiklenen_araclar"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = f"""Sen TUNGAR-Guard sistemi için çalışan bir saha güvenlik operasyon asistanısın.
Sana verilen video klibini analiz et. Olayları zaman damgasıyla (klip içindeki değil,
sana söylenen ORİJİNAL video zamanına göre, mm:ss formatında) tespit et, kısa Türkçe
özet üret, risk seviyesi belirle, uygulanabilir aksiyon önerileri sun.

incident_type alanını düzgün, doğru yazımlı Türkçe kelimelerle yaz (örn. "kaçak",
"forklift devrilmesi", "yangın") — kısaltma, slug ya da alt çizgili teknik kod
kullanma, birbirine benzeyen kelimeleri (örn. "kaçak" / "kazak") karıştırma.

GÖRSEL AYRIM (önemli, yanlış sınıflandırma yapma):
- "Patlama" SADECE görünür alev, parlama/flaş veya ani bir enerji pürlemesi
  varsa kullan. Bir raf/palet çöküşünden kalkan TOZ BULUTU patlama DEĞİLDİR —
  bunu "raf çökmesi" / "malzeme dökülmesi" gibi doğru adlandır, toz bulutunu
  patlamayla karıştırma.
- "Yangın"/"duman" için de gerçek alev veya duman rengi/dokusu görmelisin,
  sadece toz/pislik bulutunu duman sanma.

BOŞ OLAYLAR LİSTESİ (çok önemli): Gördüğün görüntü tamamen rutin/uyumlu ise
(PPE eksiksiz takılmış, tehlike yok, anormal bir şey olmuyor) "olaylar" alanını
BOŞ LİSTE ([]) olarak döndür ve risk'i "Dusuk" yap. Sırf "kontrol ettim" demek
için uydurma bir olay UYDURMA — bir işçi baretini/yeleğini düzgün takmış,
normal çalışıyorsa bu bir "olay" DEĞİLDİR, raporlanacak bir şey yoktur.
Sadece gerçekten dikkat çekici (ihlal, tehlike, anomali) bir şey gördüğünde
olaylar listesine ekle. Olaylar boş olsa bile genel_ozet alanında GERÇEKTEN
GÖRDÜĞÜNÜ tarif et (örn. "İşçi PPE'sini eksiksiz takmış, normal çalışıyor,
dikkat çekici bir durum yok.") — asla jenerik "kontrol edildi" gibi boş bir
cümleyle geçiştirme, ne gördüğünü somut olarak anlat.

KİŞİ ETKİLENİYORSA ETİKETTE BELİRT: Düşen/devrilen bir nesne (panel, palet,
raf, yük vb.) bir KİŞİYE çarpıyor veya altında bırakıyorsa, incident_type
SADECE nesneyi değil, kişinin durumunu da yansıtmalı — örn. "malzeme düşmesi"
yerine "kişinin malzeme altında kalması", "ezilme riski" veya "kişi yaralanma
riski" gibi net bir ifade kullan. "sıkışma"/"sıkışması" kelimesini KULLANMA
(gündelik Türkçede farklı/uygunsuz bir çağrışımı var) — bunun yerine "altında
kalma", "ezilme" veya "çarpma" gibi net ve profesyonel kelimeler tercih et.
Sadece nesne odaklı, kişiyi görmezden gelen bir etiket de YAZMA.

TEK OLAYI BÖLME: Aynı süregelen olay (örn. bir patlama, bir devrilme) klip
içinde birden fazla anda görünse bile TEK bir "olaylar" girdisi olarak
raporla — event_start/event_peak/event_end alanlarını olayın başlangıç,
en yoğun anı ve bitişini göstermek için kullan. Aynı olay için "olaylar"
listesine ikinci bir girdi EKLEME (örn. "patlama" önce 00:02'de sonra
00:04'te ayrı ayrı raporlanmaz — tek girdi: event_start=00:02,
event_peak=00:03, event_end=00:04). Sadece GERÇEKTEN farklı/bağımsız
olaylar varsa birden fazla girdi kullan.

GÜVEN ALANI KALİBRASYONU (önemli — sabit bir sayı yazma, her olay için gerçekten
değerlendir):
- Görüntü net, olay tipi belirgin, şüphe yok: 0.85-0.98 arası kullan.
- Görüntü kısmen belirsiz (uzak, karanlık, kısmen kapalı, yorumlanabilir): 0.5-0.75.
- Çok belirsiz, tahmin niteliğinde: 0.3-0.5.
Aynı klip içinde bile farklı olayların güven değeri farklı olabilir. Her olay için
ayrı ayrı düşün — hepsine aynı sayıyı yazma.

SEVERITY_LEVEL KALİBRASYONU (önemli, aşırı değerlendirme yapma):
- Düşük: rutin, ihlal yok, sadece gözlem.
- Orta: tek/kısa süreli, tehlike anında gerçekleşmeyen küçük bir PPE ihlali (örn.
  bir kişinin bir an için baretini çıkarması, kimse yakınında araç/tehlike yokken).
- Yüksek: sürekli/tekrarlayan PPE ihlali, YA DA ihlal aktif bir tehlike kaynağının
  (araç, yükseklik, ağır ekipman) yakınında gerçekleşiyor.
- Kritik: SADECE gerçek çarpışma, düşme, yaralanma, basınçlı kaçak/patlama veya
  can güvenliğini anında tehdit eden bir durum için kullan.
Bir kişinin kısa süreli, tehlikeden uzakta PPE eksikliği tek başına Kritik ya da
Yüksek değildir — bunu Orta olarak değerlendir.

"{config.COLLISION_LABEL}" etiketi verilmişse bu bir kişi-araç çarpışması/ezilme riski
demektir, severity_level'i MUTLAKA "Kritik" yap ve call_emergency_team ile
trigger_local_alarm'i tetiklenen_araclar'a ekle.

tetiklenen_araclar alanında SADECE şu isimlerden seçebilirsin:
trigger_local_alarm, send_internal_log, call_emergency_team, query_event_history, get_event_detail"""


def _client():
    from openai import OpenAI
    return OpenAI(base_url=config.EVREN_BASE_URL, api_key=config.EVREN_API_KEY, timeout=config.EVREN_TIMEOUT)


def analyze_clip(clip_bytes: bytes, yolo_labels: Optional[List[str]] = None,
                  clip_start_offset_sec: float = 0.0) -> VisionAnalysisResult:
    """Video klibini EVREN API'sine (varsayılan: llm-large) gönderir, şema kısıtlı
    (strict) JSON döner — ayrıştırma hatası riski yoktur."""
    video_b64 = base64.b64encode(clip_bytes).decode()

    context_note = ""
    if yolo_labels:
        context_note = f"\nYerel tespit sistemi bu klipte şunları işaretledi: {', '.join(yolo_labels)}."

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": [
            {"type": "text", "text": (
                f"Bu video klibi, orijinal videonun {clip_start_offset_sec:.0f}. saniyesinden "
                "itibaren başlıyor. Zaman damgalarını buna göre (orijinal video zamanına göre, "
                "mm:ss formatında) ver." + context_note
            )},
            {"type": "video_url", "video_url": {"url": f"data:video/mp4;base64,{video_b64}"}},
        ]},
    ]

    try:
        client = _client()
        response = client.chat.completions.create(
            model=config.EVREN_MODEL,
            messages=messages,
            max_tokens=4096,
            temperature=0.0,
            response_format={"type": "json_schema", "json_schema": {
                "name": "video_analiz_raporu", "schema": EVREN_JSON_SCHEMA, "strict": True,
            }},
        )
        content = response.choices[0].message.content
        if not content:
            finish_reason = response.choices[0].finish_reason
            raise ValueError(f"Model boş yanıt döndürdü (finish_reason={finish_reason}). "
                              f"Muhtemelen token bütçesi yetersiz kaldı.")
        data = json.loads(content)
        return VisionAnalysisResult(**data)
    except Exception as e:
        return VisionAnalysisResult(
            genel_ozet=f"EVREN API çağrısı başarısız oldu: {type(e).__name__}: {e}",
            olaylar=[], nedensel_zincir=[], risk="Dusuk",
            onerilen_aksiyonlar=["Manuel doğrulama önerilir"], tetiklenen_araclar=[],
        )


def chat_evren(system_prompt: str, history: list, user_message: str) -> str:
    """Metin tabanlı sohbet — video göndermez, sadece llm-fast ile hızlı yanıt."""
    messages = [{"role": "system", "content": system_prompt}]
    for turn in history:
        messages.append({"role": turn["role"], "content": turn["content"]})
    messages.append({"role": "user", "content": user_message})

    try:
        client = _client()
        response = client.chat.completions.create(
            model="llm-fast", messages=messages, max_tokens=500, temperature=0.0,
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"EVREN API çağrısı başarısız oldu: {e}"
