from typing import List, Optional

import config
from vision.schema import VisionAnalysisResult, SCHEMA_JSON_EXAMPLE, try_parse

SYSTEM_PROMPT = f"""Sen TUNGAR-Guard sistemi icin calisan bir saha guvenlik operasyon asistanisin.
Sana verilen, zaman damgali kareler halindeki video parcasini analiz et.
SADECE gecerli JSON dondur, baska metin ekleme. Sema:
{SCHEMA_JSON_EXAMPLE}
faz: baslangic/gelisim/sonuc. severity_level ve risk: Dusuk/Orta/Yuksek/Kritik.
tetiklenen_araclar sadece su isimlerden secilebilir: trigger_local_alarm, send_internal_log, call_emergency_team, query_event_history, get_event_detail."""

_model = None
_processor = None


def ensure_loaded():
    """Modeli önceden yükler (indirme dahil). app.py başlangıçta bunu çağırıp
    kullanıcıya net bir bekleme mesajı gösterir — 'Analiz Et' anında sürpriz
    uzun bekleme yaşanmaz."""
    _load()


def chat_local(system_prompt: str, history: list, user_message: str) -> str:
    """Metin tabanlı sohbet — aynı yüklü modeli (görsel olmadan) kullanır.
    Qwen3-VL'in chat template'i her mesajın content'inin liste-parça formatında
    olmasını bekliyor (düz string değil), aksi halde template içinde None hatası verir."""
    _load()

    def _msg(role, text):
        return {"role": role, "content": [{"type": "text", "text": text}]}

    messages = [_msg("system", system_prompt)]
    for turn in history:
        messages.append(_msg(turn["role"], turn["content"]))
    messages.append(_msg("user", user_message))

    text = _processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    try:
        inputs = _processor.tokenizer(text, return_tensors="pt").to(_model.device)
    except AttributeError:
        inputs = _processor(text=[text], images=[], return_tensors="pt").to(_model.device)
    output_ids = _model.generate(**inputs, max_new_tokens=400, do_sample=False)
    generated = output_ids[:, inputs["input_ids"].shape[1]:]
    return _processor.batch_decode(generated, skip_special_tokens=True)[0]


def _load():
    global _model, _processor
    if _model is not None:
        return
    import torch
    from transformers import Qwen3VLForConditionalGeneration, AutoProcessor

    device_map = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[TUNGAR-Guard] Qwen3-VL yükleniyor, cihaz: {device_map} "
          f"({'GPU bulundu' if device_map == 'cuda' else 'UYARI: GPU bulunamadı, CPU çok yavaş olacak!'})")

    _model = Qwen3VLForConditionalGeneration.from_pretrained(
        config.LOCAL_MODEL_NAME, dtype="auto", device_map=device_map
    )
    _processor = AutoProcessor.from_pretrained(config.LOCAL_MODEL_NAME)
    print(f"[TUNGAR-Guard] Model gerçek cihazı: {_model.device}")


def analyze_frames_local(frame_bytes_list: List[bytes], frame_timestamps: List[str],
                          yolo_labels: Optional[List[str]] = None,
                          max_retries: int = 1) -> VisionAnalysisResult:
    import io
    from PIL import Image

    _load()

    MAX_DIM = 448  # görselleri küçültmek, işlem token sayısını ve süreyi ciddi düşürür

    def _prep_image(fb: bytes) -> "Image.Image":
        img = Image.open(io.BytesIO(fb)).convert("RGB")
        img.thumbnail((MAX_DIM, MAX_DIM))
        return img

    content = [{"type": "text", "text": (
        "Asagidaki kareleri, zaman damgalariyla birlikte analiz et:\n"
        + "\n".join(f"Kare {i+1} = {ts}" for i, ts in enumerate(frame_timestamps))
    )}]
    for fb in frame_bytes_list:
        content.append({"type": "image", "image": _prep_image(fb)})

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": content},
    ]

    images = [c["image"] for c in content if c["type"] == "image"]
    last_raw = ""

    for attempt in range(max_retries + 1):
        text = _processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = _processor(text=[text], images=images, return_tensors="pt").to(_model.device)

        output_ids = _model.generate(**inputs, max_new_tokens=600, do_sample=False)
        generated = output_ids[:, inputs["input_ids"].shape[1]:]
        raw_text = _processor.batch_decode(generated, skip_special_tokens=True)[0]
        last_raw = raw_text

        parsed = try_parse(raw_text)
        if parsed:
            return parsed

        messages.append({"role": "assistant", "content": raw_text})
        messages.append({"role": "user", "content": "Hata: JSON şemaya uymadı. SADECE geçerli JSON döndür, başka metin ekleme."})

    print("UYARI: yerel model çıktısı şemaya uymadı. Ham çıktı:\n", last_raw[:500])
    return VisionAnalysisResult(
        genel_ozet=f"Model çıktısı ayrıştırılamadı (ham çıktı loglandı, {max_retries + 1} denemede). Manuel doğrulama önerilir.",
        olaylar=[], nedensel_zincir=[], risk="Dusuk",
        onerilen_aksiyonlar=["Manuel doğrulama önerilir"], tetiklenen_araclar=[],
    )
