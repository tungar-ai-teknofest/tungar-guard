from dataclasses import dataclass, field
from typing import List, Tuple
import os
import tempfile

import cv2
import numpy as np

import config


@dataclass
class Detection:
    cls_name: str
    conf: float
    box: Tuple[float, float, float, float]


@dataclass
class Trigger:
    frame_idx: int
    timestamp_sec: float
    channel: str
    detections: List[Detection] = field(default_factory=list)
    collision: bool = False


def _iou(box_a, box_b) -> float:
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    if inter <= 0:
        return 0.0
    area_a = (ax2 - ax1) * (ay2 - ay1)
    area_b = (bx2 - bx1) * (by2 - by1)
    return inter / (area_a + area_b - inter)


def _boxes_close(box_a, box_b, margin_ratio: float = 0.5) -> bool:
    ax = (box_a[0] + box_a[2]) / 2
    ay = (box_a[1] + box_a[3]) / 2
    bx = (box_b[0] + box_b[2]) / 2
    by = (box_b[1] + box_b[3]) / 2
    dist = ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5
    avg_w = ((box_a[2] - box_a[0]) + (box_b[2] - box_b[0])) / 2
    return dist < avg_w * (1 + margin_ratio)


def detect_frame(model, frame_bgr: np.ndarray, conf: float = 0.25) -> List[Detection]:
    results = model.predict(source=frame_bgr, conf=conf, verbose=False)
    dets = []
    if not results:
        return dets
    r = results[0]
    for box in r.boxes:
        cls_id = int(box.cls[0])
        cls_name = config.YOLO_CLASS_NAMES[cls_id] if cls_id < len(config.YOLO_CLASS_NAMES) else str(cls_id)
        conf_val = float(box.conf[0])
        x1, y1, x2, y2 = box.xyxy[0].tolist()
        dets.append(Detection(cls_name, conf_val, (x1, y1, x2, y2)))
    return dets


def _check_person_vehicle(dets: List[Detection]) -> Tuple[bool, bool]:
    """Dönüş: (yakinlik_var, carpisma_var). Çarpışma = anlamlı bbox üst üste binmesi."""
    persons = [d for d in dets if d.cls_name == "person"]
    vehicles = [d for d in dets if d.cls_name in config.VEHICLE_CLASSES]
    close, collision = False, False
    for p in persons:
        for v in vehicles:
            if _iou(p.box, v.box) >= config.IOU_COLLISION_THRESHOLD:
                collision = True
                close = True
            elif _boxes_close(p.box, v.box):
                close = True
    return close, collision


def find_triggers(model, video_path: str, sample_fps: float = 5.0,
                   periodic_sweep_sec: float = 20.0, debounce_sec: float = 10.0,
                   max_triggers: int = 15, max_collision_triggers: int = 8,
                   collision_debounce_sec: float = 8.0, batch_size: int = 8) -> Tuple[List[Trigger], float, dict]:
    """Video baştan sona taranır (YOLO taraması ucuzdur, tamamı taranır). Ama her tetik
    gerçek bir Qwen çağrısı anlamına geldiği için (pahalı!) hem normal (K1/K3) hem
    çarpışma (K2 collision) tetikleri AYRI ayrı sınırlıdır — aksi halde uzun süre devam
    eden bir çarpışma/yakınlık, videoyu saatlerce analiz ettirebilir.

    Dönüş: (triggers, video_fps, scan_stats). scan_stats içinde YOLO tarama hızı (FPS)
    ve varsa GPU bellek tepe kullanımı raporlanır — KPI panelindeki "donanım tüketimi"
    metriği için."""
    import time as _time
    scan_start = _time.time()
    peak_vram_mb = None
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.reset_peak_memory_stats()
    except Exception:
        torch = None

    cap = cv2.VideoCapture(video_path)
    video_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    frame_interval = max(1, int(round(video_fps / sample_fps)))

    triggers: List[Trigger] = []
    last_trigger_time = -999.0
    last_collision_time = -999.0
    last_sweep_time = 0.0
    normal_trigger_count = 0
    collision_trigger_count = 0
    scanned_frame_count = 0

    def process_batch(batch):
        nonlocal last_trigger_time, last_collision_time, last_sweep_time
        nonlocal normal_trigger_count, collision_trigger_count, scanned_frame_count
        if not batch:
            return
        scanned_frame_count += len(batch)
        imgs = [b[2] for b in batch]
        results = model.predict(source=imgs, conf=0.25, verbose=False)
        for (f_idx, t_sec, _), r in zip(batch, results):
            dets = []
            for box in r.boxes:
                cls_id = int(box.cls[0])
                cls_name = config.YOLO_CLASS_NAMES[cls_id] if cls_id < len(config.YOLO_CLASS_NAMES) else str(cls_id)
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                dets.append(Detection(cls_name, float(box.conf[0]), (x1, y1, x2, y2)))

            names = {d.cls_name for d in dets}
            close, collision = _check_person_vehicle(dets)

            channel = None
            if collision:
                channel = "K2"
            elif names & config.DANGEROUS_CLASSES:
                channel = "K1"
            elif names & config.VEHICLE_CLASSES:
                channel = "K1"
            elif close:
                channel = "K2"
            if channel is None and (t_sec - last_sweep_time) >= periodic_sweep_sec:
                channel = "K3"
                last_sweep_time = t_sec

            if (collision and (t_sec - last_collision_time) >= collision_debounce_sec
                    and collision_trigger_count < max_collision_triggers):
                triggers.append(Trigger(f_idx, t_sec, channel, dets, collision=True))
                last_trigger_time = last_collision_time = t_sec
                collision_trigger_count += 1
            elif (not collision and channel and (t_sec - last_trigger_time) >= debounce_sec
                  and normal_trigger_count < max_triggers):
                triggers.append(Trigger(f_idx, t_sec, channel, dets, collision=False))
                last_trigger_time = t_sec
                normal_trigger_count += 1

    frame_idx = 0
    batch = []
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if frame_idx % frame_interval == 0:
            batch.append((frame_idx, frame_idx / video_fps, frame))
            if len(batch) >= batch_size:
                process_batch(batch)
                batch = []
        frame_idx += 1
    process_batch(batch)

    cap.release()

    scan_elapsed = _time.time() - scan_start
    if torch is not None and torch.cuda.is_available():
        peak_vram_mb = torch.cuda.max_memory_allocated() / (1024 * 1024)
    scan_stats = {
        "scan_elapsed_sec": scan_elapsed,
        "scanned_frames": scanned_frame_count,
        "scan_fps": (scanned_frame_count / scan_elapsed) if scan_elapsed > 0 else 0.0,
        "peak_vram_mb": peak_vram_mb,
    }
    return triggers, video_fps, scan_stats


def extract_temporal_window(video_path: str, center_sec: float, video_fps: float,
                             window_before: float = 3.0, window_after: float = 4.0,
                             n_frames: int = 8) -> Tuple[List[bytes], List[str]]:
    cap = cv2.VideoCapture(video_path)
    total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)

    start_sec = max(0.0, center_sec - window_before)
    end_sec = center_sec + window_after
    timestamps_sec = np.linspace(start_sec, end_sec, n_frames)

    frame_bytes_list, labels = [], []
    for t in timestamps_sec:
        frame_num = min(int(t * video_fps), int(total_frames) - 1) if total_frames > 0 else int(t * video_fps)
        cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, frame_num))
        ok, frame = cap.read()
        if not ok:
            continue
        ok2, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if ok2:
            frame_bytes_list.append(buf.tobytes())
            mm = int(t // 60)
            ss = int(t % 60)
            labels.append(f"{mm:02d}:{ss:02d}")
    cap.release()
    return frame_bytes_list, labels


def extract_video_clip(video_path: str, center_sec: float, video_fps: float,
                        window_before: float = None, window_after: float = None) -> Tuple[bytes, float]:
    """Tetik anının etrafından kısa bir video KLİBİ keser (EVREN API'ye kare değil
    klip gönderilir — API frame-based çalışmayı desteklemiyor, vlm hiç görüntü
    kabul etmiyor, llm-large/llm-fast istek başına en fazla 2 görüntüyle sınırlı).
    Dönüş: (mp4 bytes, klibin orijinal videodaki başlangıç saniyesi)."""
    window_before = config.EVREN_CLIP_BEFORE_SEC if window_before is None else window_before
    window_after = config.EVREN_CLIP_AFTER_SEC if window_after is None else window_after

    cap = cv2.VideoCapture(video_path)
    total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    start_sec = max(0.0, center_sec - window_before)
    end_sec = center_sec + window_after
    start_frame = int(start_sec * video_fps)
    end_frame = int(end_sec * video_fps)
    if total_frames > 0:
        end_frame = min(end_frame, int(total_frames) - 1)

    cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, start_frame))

    tmp_path = tempfile.mktemp(suffix=".mp4")
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(tmp_path, fourcc, video_fps, (w, h))

    frame_idx = start_frame
    while frame_idx <= end_frame:
        ok, frame = cap.read()
        if not ok:
            break
        out.write(frame)
        frame_idx += 1

    out.release()
    cap.release()

    with open(tmp_path, "rb") as f:
        clip_bytes = f.read()
    os.remove(tmp_path)
    return clip_bytes, start_sec


def compute_baseline_checkpoints(duration_sec: float, n: int = 3) -> List[float]:
    """Videoyu n eşit parçaya böler, her parçanın ortasını döner. YOLO hiçbir şey
    tetiklemese bile (YOLO'nun sınıf listesinde olmayan bir olay türü — örn. düşen
    koli/palet), Qwen'in videoyu en az bu kadar görmesini garanti eder. Karar
    tamamen YOLO'nun tespit ettiği sınıflara bağlı kalmasın diye eklendi."""
    if duration_sec <= 0:
        return []
    segment = duration_sec / n
    return [segment * (i + 0.5) for i in range(n)]


def merge_baseline_triggers(triggers: List[Trigger], video_path: str, video_fps: float,
                             n_baseline: int = 3, min_gap_sec: float = 5.0) -> List[Trigger]:
    """YOLO tetiklerine, videoyu eşit parçalara bölen n_baseline "temel kontrol"
    tetiği ekler — bir YOLO tetiğine çok yakınsa (min_gap_sec içinde) eklenmez,
    zaten o an inceleniyor demektir."""
    cap = cv2.VideoCapture(video_path)
    total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    cap.release()
    duration_sec = (total_frames / video_fps) if video_fps else 0.0

    existing_times = [t.timestamp_sec for t in triggers]
    merged = list(triggers)
    for bt in compute_baseline_checkpoints(duration_sec, n_baseline):
        if not any(abs(bt - et) < min_gap_sec for et in existing_times):
            merged.append(Trigger(frame_idx=int(bt * video_fps), timestamp_sec=bt,
                                   channel="baseline", detections=[], collision=False))
            existing_times.append(bt)

    merged.sort(key=lambda t: t.timestamp_sec)
    return merged
