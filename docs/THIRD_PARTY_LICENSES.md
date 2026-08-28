# Üçüncü Taraf Bağımlılıklar ve Lisansları

TUNGAR-Guard'ın kendi kaynak kodu Apache License 2.0 ile lisanslıdır
(bkz. [LICENSE](../LICENSE)). Aşağıdaki tablo, projenin çalışması için
kullandığımız dış bağımlılıkları ve bunların lisanslarını listeler.

| Bileşen | Lisans | Kullanım şekli |
|---|---|---|
| [Ultralytics YOLOv8](https://github.com/ultralytics/ultralytics) | AGPL-3.0 | Dış bağımlılık olarak `pip` üzerinden kurulur; kaynak kodu bu depoya **kopyalanmamıştır**. Kendi eğittiğimiz ağırlık dosyası (`tungar_guard_yolov8n.pt`) bu kütüphane ile yüklenir. |
| [Streamlit](https://github.com/streamlit/streamlit) | Apache 2.0 | Arayüz katmanı |
| [Pydantic](https://github.com/pydantic/pydantic) | MIT | Şema doğrulama (yapılandırılmış JSON çıktı) |
| [OpenAI Python SDK](https://github.com/openai/openai-python) | Apache 2.0 | EVREN çıkarım servisiyle (OpenAI uyumlu API) iletişim için istemci kütüphanesi |
| [pandas](https://github.com/pandas-dev/pandas) | BSD-3-Clause | Veri işleme |
| [NumPy](https://github.com/numpy/numpy) | BSD-3-Clause | Sayısal işlemler |
| [OpenCV (opencv-python-headless)](https://github.com/opencv/opencv-python) | Apache 2.0 | Video kare işleme |
| [Transformers](https://github.com/huggingface/transformers) *(opsiyonel, yerel model modu)* | Apache 2.0 | Qwen3-VL-4B modelini yerelde çalıştırmak için, yalnızca `TUNGAR_USE_LOCAL_MODEL=1` ayarlandığında kurulur |

## Eğitim veri seti kaynakları

YOLOv8 dikkat katmanını eğitmek için kullandığımız görüntüler, aşağıdaki
herkese açık Hugging Face veri setlerinden derlenmiştir (bkz.
`YOLO_Egitim_Colab.ipynb`):

- [Chapian/PPE_detection](https://huggingface.co/datasets/Chapian/PPE_detection)
- [keremberke/forklift-object-detection](https://huggingface.co/datasets/keremberke/forklift-object-detection)
- [keremberke/construction-safety-object-detection](https://huggingface.co/datasets/keremberke/construction-safety-object-detection)
- [keremberke/smoke-object-detection](https://huggingface.co/datasets/keremberke/smoke-object-detection)

Birleştirilmiş ve etiketlenmiş nihai veri seti: **[BURAYA GITHUB
RELEASES / HUGGING FACE DATASETS LİNKİNİ EKLEYİN]**

## Neden YOLOv8'in kodu kopyalanmadı?

Ultralytics YOLOv8, AGPL-3.0 lisansı altındadır. AGPL, kodunu kullanan
bir servisin de AGPL ile lisanslanmasını zorunlu kılabilir ("copyleft").
Kendi kodumuzu Apache 2.0 ile paylaşabilmek için YOLOv8'i bir kaynak kodu
kopyası olarak değil, standart bir Python bağımlılığı (`pip install
ultralytics`) olarak kullanıyoruz — bu, AGPL'in kapsamı dışında kalan
yaygın ve kabul edilmiş bir kullanım şeklidir.
