import os

# ---- Çalışma modu ----
# "evren" -> TEKNOFEST EVREN çıkarım servisi (yarışma altyapısı, varsayılan)
# "local" -> yerel Qwen3-VL-4B (transformers, offline demo için)
# "mock"  -> hiçbiri, test amaçlı
API_MODE = os.environ.get("TUNGAR_API_MODE", "evren")

# ---- EVREN (TEKNOFEST resmi çıkarım servisi) ----
# https://evren-teknofest.ssyz.org.tr/hizli-baslangic
EVREN_BASE_URL = "https://evren-llmapi.ssyz.org.tr/v1"
EVREN_API_KEY = os.environ.get("EVREN_API_KEY", "sk-evren-team43-27a7692d3fab685353112b155407d489")
EVREN_MODEL = os.environ.get("EVREN_MODEL", "llm-large")     # video+özet+JSON tek çağrıda (§6, Senaryo 3)
EVREN_TIMEOUT = 1800                                          # dokümantasyon zorunlu kılıyor (§7.1 uyarısı)

# Vektör veritabanı (şu an app'te kullanılmıyor, ileride lazım olursa hazır dursun)
EVREN_QDRANT_URL = "https://evren-vektor.ssyz.org.tr/team43/"
EVREN_QDRANT_KEY = os.environ.get("EVREN_QDRANT_KEY", "qdr-team43-02ecf9841e95472b6a0ef84836e9ae17")

# EVREN video klip ayarları (§3.4 çözünürlük zarfı — kısa klip önerilir)
EVREN_CLIP_BEFORE_SEC = 4.0
EVREN_CLIP_AFTER_SEC = 8.0   # toplam ~12sn klip, hızlı işlenme aralığında

# ---- Yerel model (opsiyonel, demo/offline kanıt için) ----
USE_LOCAL_MODEL = os.environ.get("TUNGAR_USE_LOCAL_MODEL", "0") == "1"
LOCAL_MODEL_NAME = os.environ.get("TUNGAR_LOCAL_MODEL", "Qwen/Qwen3-VL-4B-Instruct")

if USE_LOCAL_MODEL:
    API_MODE = "local"
if not EVREN_API_KEY and API_MODE == "evren":
    API_MODE = "mock"

MOCK_MODE = (API_MODE == "mock")

DB_PATH = os.environ.get("TUNGAR_DB_PATH", "tungar_guard.db")
YOLO_MODEL_PATH = os.environ.get("TUNGAR_YOLO_PATH", "tungar_guard_yolov8n.pt")

YOLO_CLASS_NAMES = [
    'person', 'hardhat', 'no_vest', 'no_gloves', 'boots', 'vest', 'no_hardhat',
    'no_boots', 'forklift', 'wheel loader', 'excavators', 'dump truck',
    'safety net', 'mini-van', 'truck', 'barricade', 'dumpster', 'mask', 'smoke',
]

DANGEROUS_CLASSES = {"no_hardhat", "no_vest", "no_gloves", "no_boots", "smoke"}
VEHICLE_CLASSES = {"forklift", "wheel loader", "excavators", "dump truck", "truck", "mini-van"}

COLLISION_LABEL = "person_vehicle_collision"
IOU_COLLISION_THRESHOLD = 0.05
