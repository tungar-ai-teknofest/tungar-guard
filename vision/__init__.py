from .schema import VisionAnalysisResult, try_parse, build_full_report
from .qwen_client import analyze_frames
from .attention import (find_triggers, extract_temporal_window, extract_video_clip,
                         detect_frame, merge_baseline_triggers)
from .tools import dispatch_tools, TOOL_REGISTRY

import config


def analyze_trigger(video_path: str, trig, video_fps: float) -> VisionAnalysisResult:
    """Tek giriş noktası — config.API_MODE'a göre doğru yola yönlendirir:
    evren -> video klibi (EVREN API klip bekler, kare değil)
    local/mock -> 8 karelik zamansal pencere (yerel Qwen / sahte cevap)."""
    yolo_labels = sorted({d.cls_name for d in trig.detections})
    if trig.collision:
        yolo_labels.append(config.COLLISION_LABEL)

    if config.API_MODE == "evren":
        from vision.evren_client import analyze_clip
        clip_bytes, start_offset = extract_video_clip(video_path, trig.timestamp_sec, video_fps)
        return analyze_clip(clip_bytes, yolo_labels=yolo_labels, clip_start_offset_sec=start_offset)

    frames, labels = extract_temporal_window(video_path, trig.timestamp_sec, video_fps)
    return analyze_frames(frames, labels, yolo_labels=yolo_labels)


__all__ = [
    "VisionAnalysisResult", "try_parse", "build_full_report", "analyze_frames",
    "find_triggers", "extract_temporal_window", "extract_video_clip", "detect_frame",
    "merge_baseline_triggers", "dispatch_tools", "TOOL_REGISTRY", "analyze_trigger",
]
