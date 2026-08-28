import base64
import random
import time
from typing import List, Optional

import config
from vision.schema import VisionAnalysisResult, SCHEMA_JSON_EXAMPLE, try_parse

SYSTEM_PROMPT = f"""Sen TUNGAR-Guard sistemi icin calisan bir saha guvenlik operasyon asistanisin.
Sana verilen, zaman damgali kareler halindeki video parcasini analiz et.
Gorevin: olaylari zaman bilgisiyle tespit etmek, kisa Turkce ozet uretmek,
risk seviyesi belirlemek ve uygulanabilir aksiyon onerileri sunmak.

KURALLAR:
- SADECE gecerli JSON dondur, baska hicbir metin ekleme.
- JSON asagidaki semaya birebir uymali:
{SCHEMA_JSON_EXAMPLE}
- faz alani sadece "baslangic", "gelisim" veya "sonuc" olabilir.
- severity_level ve risk alanlari sadece "Dusuk", "Orta", "Yuksek" veya "Kritik" olabilir.
- "{config.COLLISION_LABEL}" etiketi verilmisse bu bir kisi-arac carpismasi/ezilme riski
  demektir, severity_level'i MUTLAKA "Kritik" yap ve call_emergency_team ile
  trigger_local_alarm'i tetiklenen_araclar'a ekle.
- Emin olmadigin durumlarda guven skorunu dusuk tut (0.3-0.5) ve otomatik aksiyon onerme.
- tetiklenen_araclar alaninda SADECE su isimlerden secebilirsin:
  trigger_local_alarm, send_internal_log, call_emergency_team, query_event_history, get_event_detail
"""


def _encode_image(image_bytes: bytes) -> str:
    return base64.b64encode(image_bytes).decode("utf-8")


def _mock_response(frame_labels: Optional[List[str]] = None,
                    frame_timestamps: Optional[List[str]] = None) -> VisionAnalysisResult:
    labels = frame_labels or []
    ts = frame_timestamps or ["00:00", "00:01", "00:02"]
    t_start, t_peak, t_end = ts[0], ts[len(ts) // 2], ts[-1]

    if config.COLLISION_LABEL in labels:
        return VisionAnalysisResult(
            genel_ozet="[MOCK] Kişi ile araç arasında çarpışma/ezilme riski tespit edildi.",
            olaylar=[{
                "olay_id": "E01", "event_start": t_start, "event_peak": t_peak, "event_end": t_end,
                "faz": "gelisim", "incident_type": "Kişi-araç çarpışması", "severity_level": "Kritik",
                "guven": round(random.uniform(0.75, 0.92), 2),
                "kanit": {"kareler": [], "yolo_tespitleri": labels, "tetikleyen_kanal": "K2"},
                "gerekce": "Mock modu: kişi ve araç bbox'ları anlamlı ölçüde üst üste biniyor.",
            }],
            nedensel_zincir=["Araç ve kişi aynı alanda", "Bbox çakışması tespit edildi"],
            risk="Kritik",
            onerilen_aksiyonlar=["Sağlık ekibini derhal yönlendirin", "Alanı güvenlik şeridiyle kapatın"],
            tetiklenen_araclar=["call_emergency_team", "trigger_local_alarm"],
        )

    if any(l.startswith("no_") or l == "smoke" for l in labels):
        risk, sev, incident = "Yuksek", "Yuksek", "PPE ihlali / risk tespiti (mock)"
        guven = round(random.uniform(0.7, 0.9), 2)
        aksiyonlar = ["Sorumlu personeli bilgilendirin", "Kaydı ISG loguna düşürün"]
        araclar = ["send_internal_log"]
    elif "forklift" in labels or "wheel loader" in labels or "excavators" in labels:
        risk, sev, incident = "Orta", "Orta", "Ağır ekipman hareketi (mock)"
        guven = round(random.uniform(0.6, 0.85), 2)
        aksiyonlar = ["Alanı gözlemleyin", "Personel yakınlığını kontrol edin"]
        araclar = ["send_internal_log"]
    else:
        risk, sev, incident = "Dusuk", "Dusuk", "Rutin gözlem (mock)"
        guven = round(random.uniform(0.7, 0.95), 2)
        aksiyonlar = ["Standart loglama"]
        araclar = ["send_internal_log"]

    return VisionAnalysisResult(
        genel_ozet=f"[MOCK] Karede tespit edilenler: {', '.join(labels) if labels else 'nesne yok'}.",
        olaylar=[{
            "olay_id": "E01", "event_start": t_start, "event_peak": t_peak, "event_end": t_end,
            "faz": "gelisim", "incident_type": incident, "severity_level": sev, "guven": guven,
            "kanit": {"kareler": [], "yolo_tespitleri": labels, "tetikleyen_kanal": "K1"},
            "gerekce": "Mock modu: gercek model calismiyor.",
        }],
        nedensel_zincir=[incident],
        risk=risk,
        onerilen_aksiyonlar=aksiyonlar,
        tetiklenen_araclar=araclar,
    )


def analyze_frames(frame_bytes_list: List[bytes], frame_timestamps: List[str],
                    yolo_labels: Optional[List[str]] = None,
                    max_retries: int = 2) -> VisionAnalysisResult:

    if config.USE_LOCAL_MODEL:
        from vision.local_qwen import analyze_frames_local
        return analyze_frames_local(frame_bytes_list, frame_timestamps, yolo_labels)

    if config.MOCK_MODE:
        time.sleep(0.3)
        return _mock_response(yolo_labels, frame_timestamps)

    try:
        from openai import OpenAI
    except ImportError:
        return _mock_response(yolo_labels, frame_timestamps)

    client = OpenAI(base_url=config.QWEN_BASE_URL, api_key=config.QWEN_API_KEY or "not-needed")

    context_note = ""
    if yolo_labels and config.COLLISION_LABEL in yolo_labels:
        context_note = f"\nUYARI: '{config.COLLISION_LABEL}' etiketi mevcut — kişi/araç bbox çakışması tespit edildi."

    content = [{"type": "text", "text": (
        "Asagidaki kareleri, zaman damgalariyla birlikte analiz et:\n"
        + "\n".join(f"Kare {i+1} = {ts}" for i, ts in enumerate(frame_timestamps))
        + context_note
    )}]
    for fb in frame_bytes_list:
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{_encode_image(fb)}"},
        })

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": content},
    ]

    last_error = ""
    for attempt in range(max_retries + 1):
        try:
            kwargs = dict(model=config.QWEN_MODEL_NAME, messages=messages, temperature=0.2, max_tokens=1200)
            try:
                response = client.chat.completions.create(response_format={"type": "json_object"}, **kwargs)
            except Exception:
                response = client.chat.completions.create(**kwargs)

            raw_text = response.choices[0].message.content
            parsed = try_parse(raw_text)
            if parsed:
                return parsed
            last_error = "JSON şemaya uymadı."
            messages.append({"role": "assistant", "content": raw_text})
            messages.append({"role": "user", "content": f"Hata: {last_error} Lütfen SADECE geçerli JSON döndür, şemaya birebir uy."})
        except Exception as e:
            last_error = str(e)
            break

    return VisionAnalysisResult(
        genel_ozet=f"Analiz tamamlanamadi (hata: {last_error}). Manuel dogrulama onerilir.",
        olaylar=[], nedensel_zincir=[], risk="Dusuk",
        onerilen_aksiyonlar=["Manuel doğrulama önerilir"], tetiklenen_araclar=[],
    )
