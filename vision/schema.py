from typing import List
from pydantic import BaseModel, Field, ValidationError


class Kanit(BaseModel):
    kareler: List[str] = Field(default_factory=list)
    yolo_tespitleri: List[str] = Field(default_factory=list)
    tetikleyen_kanal: str = ""


class Olay(BaseModel):
    olay_id: str
    event_start: str
    event_peak: str
    event_end: str
    faz: str
    incident_type: str
    severity_level: str
    guven: float
    kanit: Kanit = Field(default_factory=Kanit)
    gerekce: str = ""


class VisionAnalysisResult(BaseModel):
    genel_ozet: str
    olaylar: List[Olay] = Field(default_factory=list)
    nedensel_zincir: List[str] = Field(default_factory=list)
    risk: str
    onerilen_aksiyonlar: List[str] = Field(default_factory=list)
    tetiklenen_araclar: List[str] = Field(default_factory=list)


SCHEMA_JSON_EXAMPLE = """{
  "genel_ozet": string (kisa Turkce ozet, 1-2 cumle),
  "olaylar": [
    {
      "olay_id": string (benzersiz kisa kod, orn E01),
      "event_start": string (mm:ss, verilen kare zaman damgalarindan biri),
      "event_peak": string (mm:ss),
      "event_end": string (mm:ss),
      "faz": "baslangic" | "gelisim" | "sonuc",
      "incident_type": string (gozlemledigin olayin turu, kendi kelimelerinle),
      "severity_level": "Dusuk" | "Orta" | "Yuksek" | "Kritik",
      "guven": number (0.0-1.0 arasi, gercek degerlendirmen),
      "kanit": {"kareler": [], "yolo_tespitleri": [string, ...], "tetikleyen_kanal": string},
      "gerekce": string (gordugun gorsel kanita dayanarak neden bu sonuca vardigin)
    }
  ],
  "nedensel_zincir": [string, ...],
  "risk": "Dusuk" | "Orta" | "Yuksek" | "Kritik",
  "onerilen_aksiyonlar": [string, ...],
  "tetiklenen_araclar": [string, ...]
}
ONEMLI: Yukaridaki degerler alan aciklamalaridir, ornek deger DEGILDIR. Kopyalama —
sadece SANA VERILEN gercek karelerde gordugun icerige gore kendi degerlerini uret."""


def try_parse(raw_text: str) -> VisionAnalysisResult | None:
    import json
    import re

    text = raw_text.strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        text = match.group(0)
    try:
        data = json.loads(text)
        return VisionAnalysisResult(**data)
    except (json.JSONDecodeError, ValidationError):
        return None


def build_full_report(video_name: str, events: List[dict], observed_summaries: List[str] = None) -> dict:
    """Şartname madde 3/5'teki tek video raporu formatı: zaman damgalı olay
    listesi + genel özet + risk değerlendirmesi + aksiyon önerileri, JSON."""
    if not events:
        real_summary = None
        for s in (observed_summaries or []):
            if s and "başarısız oldu" not in s:
                real_summary = s
                break
        return {
            "video": video_name, "olaylar": [],
            "genel_ozet": real_summary or "Dikkate değer bir olay tespit edilmedi.",
            "risk_degerlendirmesi": "Düşük", "aksiyon_onerileri": [],
        }

    severity_rank = {"Dusuk": 0, "Düşük": 0, "Orta": 1, "Yuksek": 2, "Yüksek": 2, "Kritik": 3}
    worst = max(events, key=lambda e: severity_rank.get(e["severity_level"], 0))

    olaylar = [{"zaman": e["event_start"], "olay": e["incident_type"], "seviye": e["severity_level"],
                "guven": e["guven"]} for e in events]
    aksiyonlar = []
    for e in events:
        for a in e.get("onerilen_aksiyonlar", []):
            if a not in aksiyonlar:
                aksiyonlar.append(a)

    incident_types = ", ".join(sorted({e["incident_type"] for e in events}))
    ozet = (f"{video_name} videosunda {len(events)} olay tespit edildi: {incident_types}. "
            f"En yüksek risk seviyesi: {worst['severity_level']}.")

    return {
        "video": video_name, "olaylar": olaylar, "genel_ozet": ozet,
        "risk_degerlendirmesi": worst["severity_level"], "aksiyon_onerileri": aksiyonlar,
    }
