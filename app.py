import os
import json
import tempfile
import time
import uuid

import streamlit as st
import pandas as pd

import config
from database import DatabaseManager
from engine import PipelineEngine, KPIEngine
from models import VideoEvent
from vision import find_triggers, analyze_trigger, merge_baseline_triggers, dispatch_tools
from vision.schema import build_full_report
from chat import send_chat_message

st.set_page_config(page_title="TUNGAR-Guard", layout="wide", page_icon="🛡️")

CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap');

html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; }
code, .stCodeBlock, [data-testid="stMarkdownContainer"] code { font-family: 'IBM Plex Mono', monospace !important; }

/* Sayfa zemini — çok hafif bir vinyet, düzlüğü kırar */
[data-testid="stAppViewContainer"] {
    background:
        radial-gradient(1200px 500px at 15% -10%, rgba(245,165,36,0.05), transparent 60%),
        #0B0F14;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background: #0E141B;
    border-right: 1px solid #1E2731;
}
[data-testid="stSidebar"] [data-testid="stButton"] > button {
    background: transparent;
    border: 1px solid transparent;
    text-align: left;
    color: #B4BFC9;
}
[data-testid="stSidebar"] [data-testid="stButton"] > button:hover {
    border-color: #2A3542;
    color: #E6EDF3;
    background: #161F2B;
}

/* ---- Üst kontrol paneli: başlık + KPI şeridi + aksiyonlar tek panelde ---- */
.tg-panel {
    background: linear-gradient(180deg, #131B24 0%, #10161F 100%);
    border: 1px solid #1E2731;
    border-radius: 12px;
    box-shadow: 0 4px 24px rgba(0,0,0,0.35), inset 0 1px 0 rgba(255,255,255,0.03);
    padding: 18px 22px 16px 22px;
    margin-bottom: 22px;
    position: relative;
    overflow: hidden;
}
.tg-panel::before {
    content: "";
    position: absolute; top: 0; left: 0; right: 0; height: 2px;
    background: linear-gradient(90deg, transparent, #F5A524 25%, #F5A524 75%, transparent);
    opacity: 0.7;
}
.tg-panel-top {
    display: flex; align-items: center; justify-content: space-between;
    margin-bottom: 16px;
}
.tg-title-row { display: flex; align-items: center; gap: 10px; }
.tg-title-row .tg-title { font-size: 1.15rem; font-weight: 700; letter-spacing: 0.01em; }
.tg-badge {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.7rem;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: #F5A524;
    background: rgba(245, 165, 36, 0.12);
    border: 1px solid rgba(245, 165, 36, 0.35);
    border-radius: 4px;
    padding: 3px 8px;
}

/* KPI şeridi — kutu-içinde-kutu değil, ince ayraçlı tek satır */
.tg-stat-strip { display: flex; }
.tg-stat {
    flex: 1;
    padding: 0 20px;
    border-left: 1px solid #212B36;
}
.tg-stat:first-child { border-left: none; padding-left: 0; }
.tg-stat .tg-stat-label {
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    color: #7C8A99;
    margin-bottom: 4px;
}
.tg-stat .tg-stat-value {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 1.7rem;
    font-weight: 600;
    color: #E6EDF3;
    line-height: 1.1;
}

/* Bölüm başlıkları — sol vurgu çizgisiyle */
.tg-section-title {
    display: flex; align-items: center; gap: 9px;
    font-size: 1.02rem; font-weight: 700; color: #E6EDF3;
    margin: 4px 0 12px 0;
}
.tg-section-title::before {
    content: ""; width: 3px; height: 16px; background: #F5A524; border-radius: 2px; display: inline-block;
}

/* KPI kartları (KPI Paneli alt sayfasında) */
.tg-kpi-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 18px; }
.tg-kpi {
    background: #121821;
    border: 1px solid #1E2731;
    border-left: 3px solid var(--accent, #3D4552);
    border-radius: 8px;
    padding: 14px 16px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.25);
}
.tg-kpi .tg-kpi-label {
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #8B98A5;
    margin-bottom: 6px;
}
.tg-kpi .tg-kpi-value {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 1.9rem;
    font-weight: 600;
    color: #E6EDF3;
}

/* Tespit edilen durum kartları */
.tg-event-card {
    background: #121821;
    border: 1px solid #1E2731;
    border-left: 4px solid var(--sev, #3D4552);
    border-radius: 8px;
    padding: 10px 14px;
    margin-bottom: 10px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.25);
}
.tg-event-card .tg-event-title { font-weight: 600; font-size: 0.95rem; }
.tg-event-card .tg-event-meta {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.75rem;
    color: #8B98A5;
    margin-top: 3px;
}
.tg-event-card .tg-event-extra {
    font-size: 0.8rem;
    color: #B4BFC9;
    margin-top: 6px;
    padding-top: 6px;
    border-top: 1px solid #1E2731;
    line-height: 1.4;
}
.tg-event-card .tg-event-extra b { color: #E6EDF3; font-weight: 600; }
.tg-sev-pill {
    display: inline-block;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    padding: 1px 7px;
    border-radius: 3px;
    color: #0B0F14;
    font-weight: 600;
    margin-left: 6px;
}

/* Video yükleme kutusu */
[data-testid="stForm"] {
    background: #121821;
    border: 1px solid #1E2731;
    border-radius: 10px;
    padding: 16px 18px 6px 18px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.25);
}

/* Butonlar */
.stButton > button, .stFormSubmitButton > button {
    border-radius: 6px;
    font-weight: 500;
}
.stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] {
    background: #F5A524;
    color: #0B0F14;
    border: none;
    font-weight: 600;
}
.stButton > button[kind="primary"]:hover, .stFormSubmitButton > button[kind="primary"]:hover {
    background: #FFB84D;
}

/* Sohbet baloncukları */
[data-testid="stChatMessage"] {
    background: #121821;
    border: 1px solid #1E2731;
    border-radius: 10px;
}

hr { border-color: #1E2731 !important; }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

def section_title(text: str):
    st.markdown(f'<div class="tg-section-title">{text}</div>', unsafe_allow_html=True)


def _message_to_text(m: dict) -> str:
    """Her mesaj tipini (video raporu, olay bildirimi, onay durumu dahil) sohbet
    modeline gönderilecek düz metne çevirir — model geçmiş video analizlerine ve
    olaylara referans verebilsin diye."""
    if m["message_type"] == "text":
        return m["content"]
    try:
        payload = json.loads(m["payload_json"])
    except (json.JSONDecodeError, TypeError):
        return m["content"]

    if m["message_type"] == "video_report":
        lines = [m["content"]]
        for o in payload.get("olaylar", []):
            lines.append(f"- {o['zaman']} {o['olay']} ({o['seviye']}, güven: {o['guven']:.2f})")
        if payload.get("aksiyon_onerileri"):
            lines.append("Önerilen aksiyonlar: " + ", ".join(payload["aksiyon_onerileri"]))
        return "\n".join(lines)

    if m["message_type"] == "video_event":
        return f"{m['content']} ({payload.get('channel','')} kanalı, risk: {payload.get('risk','')})"

    if m["message_type"] == "confirm_action":
        durum = "yanıtlandı" if m.get("resolved") else "yanıt bekleniyor"
        return f"{m['content']} [{durum}]"

    return m["content"]

SEVERITY_COLOR = {
    "Kritik": "#E5484D", "Yuksek": "#F5A524", "Yüksek": "#F5A524",
    "Orta": "#F2C94C", "Dusuk": "#3DD68C", "Düşük": "#3DD68C",
}


@st.cache_resource
def get_db():
    return DatabaseManager(config.DB_PATH)


@st.cache_resource
def get_yolo_model():
    if not os.path.exists(config.YOLO_MODEL_PATH):
        return None
    from ultralytics import YOLO
    return YOLO(config.YOLO_MODEL_PATH)


db = get_db()
model = get_yolo_model()

if config.USE_LOCAL_MODEL:
    @st.cache_resource
    def _load_local_qwen():
        from vision.local_qwen import ensure_loaded
        ensure_loaded()
        return True

    with st.spinner(f"Yerel model yükleniyor ({config.LOCAL_MODEL_NAME}) — ilk seferde ağırlıklar "
                     f"(~8GB) inecek, birkaç dakika sürebilir. Sonraki kullanımlarda anında hazır olacak."):
        _load_local_qwen()

if "active_session" not in st.session_state:
    sessions = db.get_sessions(limit=1)
    if sessions:
        st.session_state.active_session = sessions[0]["session_id"]
    else:
        sid = str(uuid.uuid4())
        db.create_session(sid, "Yeni sohbet")
        st.session_state.active_session = sid


def new_session():
    sid = str(uuid.uuid4())
    db.create_session(sid, "Yeni sohbet")
    st.session_state.active_session = sid


def handle_events_batch(session_id: str, run_id: str, collected: list):
    """collected: [(event_id, olay, result), ...] — VİDEODAKİ TÜM tetiklerden toplanan
    olaylar. Aynı şiddet katmanındaki olaylar TEK bir mesajda toplu bildirilir, her
    tetik için ayrı ayrı uyarı gönderilmez."""
    kritik = [t for t in collected if t[1].severity_level == "Kritik"]
    orta_yuksek = [t for t in collected if t[1].severity_level in ("Orta", "Yuksek", "Yüksek")]
    dusuk = [t for t in collected if t not in kritik and t not in orta_yuksek]

    def _line(item):
        _, olay, _ = item
        return f"• {olay.incident_type} ({olay.event_start})"

    if kritik:
        lines = "\n".join(_line(t) for t in kritik)
        db.add_message(session_id, "assistant",
                        f"🚨 **{len(kritik)} KRİTİK OLAY tespit edildi:**\n{lines}\n\n"
                        f"Şu an alarmı çalıştırıp acil sağlık ekibini arayabilirim. Onaylıyor musunuz?",
                        "confirm_action", payload={
                            "event_ids": [eid for eid, _, _ in kritik], "run_id": run_id,
                            "tools": ["call_emergency_team", "trigger_local_alarm"],
                            "context": lines,
                            "confirm_label": "✅ Onayla, ara ve alarmı çalıştır",
                        })

    if orta_yuksek:
        lines = "\n".join(_line(t) for t in orta_yuksek)
        tools = sorted({tool for _, _, r in orta_yuksek for tool in (r.tetiklenen_araclar or ["send_internal_log"])})
        db.add_message(session_id, "assistant",
                        f"⚠️ **{len(orta_yuksek)} orta/yüksek seviye risk tespit edildi:**\n{lines}\n\n"
                        f"İlgili sorumluları bilgilendirmemi ister misiniz?",
                        "confirm_action", payload={
                            "event_ids": [eid for eid, _, _ in orta_yuksek], "run_id": run_id,
                            "tools": tools, "context": lines,
                            "confirm_label": "✅ Evet, sorumluları bilgilendir",
                        })

    if dusuk:
        lines = "\n".join(_line(t) for t in dusuk)
        db.add_message(session_id, "assistant",
                        f"ℹ️ **{len(dusuk)} küçük anomali tespit edildi:**\n{lines}\n\n"
                        f"Kontrol etmenizi öneririm; emin değilsem otomatik aksiyon almıyorum.",
                        "text")




def process_video(uploaded_file, session_id: str):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
        tmp.write(uploaded_file.read())
        video_path = tmp.name

    db.add_message(session_id, "user", f"🎥 Video yüklendi: {uploaded_file.name}", "text")
    db.touch_session(session_id, title=uploaded_file.name)

    run_id = str(uuid.uuid4())
    db.create_run(run_id, "IN_PROGRESS", video_name=uploaded_file.name, session_id=session_id)
    pipeline_start = time.time()

    with st.spinner("Video taranıyor..."):
        triggers, video_fps, scan_stats = find_triggers(model, video_path, sample_fps=5.0, max_triggers=15)
        triggers = merge_baseline_triggers(triggers, video_path, video_fps, n_baseline=3)

    if not triggers:
        db.add_message(session_id, "assistant", "Video işlenemedi (çok kısa ya da bozuk olabilir).", "text")
        db.update_run(run_id, "COMPLETED", time.time() - pipeline_start)
        os.unlink(video_path)
        return

    engine = PipelineEngine(db)
    kpi_engine = KPIEngine(db)
    all_events_for_report = []
    inference_times = []
    collected_for_batch = []

    for trig in triggers:
        t0 = time.time()
        with st.spinner("Analiz ediliyor..."):
            result = analyze_trigger(video_path, trig, video_fps)
        elapsed_ms = (time.time() - t0) * 1000
        inference_times.append(elapsed_ms / 1000)

        schema_ok = "başarısız oldu" not in result.genel_ozet
        db.save_kpi(None, "inference_time_ms", elapsed_ms, metadata={"run_id": run_id})
        db.save_kpi(None, "schema_valid", 1.0 if schema_ok else 0.0, metadata={"run_id": run_id})

        if not schema_ok:
            continue

        for olay in result.olaylar:
            event_id = str(uuid.uuid4())
            db.insert_video_event(VideoEvent(
                event_id=event_id, run_id=run_id, source_name=uploaded_file.name,
                event_start=olay.event_start, event_peak=olay.event_peak, event_end=olay.event_end,
                faz=olay.faz, incident_type=olay.incident_type, severity_level=olay.severity_level,
                guven=olay.guven, gerekce=olay.gerekce,
                onerilen_aksiyonlar=result.onerilen_aksiyonlar,
                tetiklenen_araclar=result.tetiklenen_araclar,
                kanit_json=olay.kanit.model_dump_json(), created_at=time.time(),
            ), session_id=session_id)

            all_events_for_report.append(olay.model_dump())
            collected_for_batch.append((event_id, olay, result))

        analysis_run_id = engine.run_pipeline(
            initial_payload={"real_vision": result.model_dump()}, video_name=uploaded_file.name,
            session_id=session_id,
        )
        kpi_engine.calculate_and_save_kpis(analysis_run_id)

    if collected_for_batch:
        handle_events_batch(session_id, run_id, collected_for_batch)

    avg_inference_ms = (sum(inference_times) / len(inference_times)) * 1000 if inference_times else 0
    kpi_engine.db.save_kpi(run_id, "avg_inference_time_ms", avg_inference_ms)
    if scan_stats.get("scan_fps"):
        db.save_kpi(None, "yolo_scan_fps", scan_stats["scan_fps"])
    if scan_stats.get("peak_vram_mb"):
        db.save_kpi(None, "yolo_peak_vram_mb", scan_stats["peak_vram_mb"])

    report = build_full_report(uploaded_file.name, all_events_for_report)
    report["_run_id"] = run_id
    db.add_message(session_id, "assistant",
                    f"📋 **Video Raporu** — {report['genel_ozet']}",
                    "video_report", payload=report)

    db.update_run(run_id, "COMPLETED", time.time() - pipeline_start)
    os.unlink(video_path)


def handle_confirm(message_id: str, session_id: str, payload: dict, approved: bool):
    event_ids = payload.get("event_ids") or ([payload["event_id"]] if "event_id" in payload else [])
    first_event_id = event_ids[0] if event_ids else None

    if approved:
        tool_results = dispatch_tools(db, payload["run_id"], first_event_id, payload["tools"],
                                       context_message=payload.get("context", ""))
        tool_names = ", ".join(payload["tools"])
        n = len(event_ids) if len(event_ids) > 1 else None
        suffix = f" ({n} olay için)" if n else ""
        db.add_message(session_id, "assistant", f"✅ Onaylandı — {tool_names} tetiklendi{suffix}.", "text")
    else:
        db.add_message(session_id, "assistant",
                        "Anlaşıldı, otomatik aksiyon almıyorum. Durumu kendiniz değerlendirin; "
                        "gerekirse tekrar bildirin.", "text")
    db.resolve_message(message_id)


# ------------------------------------------------------------------
# Kenar çubuğu — geçmiş sohbetler
# ------------------------------------------------------------------
with st.sidebar:
    st.markdown('<div style="display:flex;align-items:center;gap:8px;padding:4px 0 14px 0;">'
                '<span style="font-size:1.6rem;">🛡️</span>'
                '<span style="font-size:1.15rem;font-weight:700;letter-spacing:0.01em;">TUNGAR-Guard</span>'
                '</div>', unsafe_allow_html=True)
    if st.button("➕ Yeni Sohbet", use_container_width=True):
        new_session()
        st.rerun()

    st.markdown("#### Geçmiş")
    if "session_to_delete" not in st.session_state:
        st.session_state.session_to_delete = None

    for s in db.get_sessions():
        label = s["title"] or "Yeni sohbet"
        active = s["session_id"] == st.session_state.active_session
        row_col1, row_col2 = st.columns([5, 1])
        if row_col1.button(("• " if active else "") + label, key=f"sess_{s['session_id']}", use_container_width=True):
            st.session_state.active_session = s["session_id"]
            st.rerun()
        if row_col2.button("🗑️", key=f"del_{s['session_id']}"):
            st.session_state.session_to_delete = s["session_id"]
            st.rerun()

    if st.session_state.session_to_delete:
        sid_to_delete = st.session_state.session_to_delete
        st.session_state.session_to_delete = None
        db.delete_session(sid_to_delete)
        if sid_to_delete == st.session_state.active_session:
            remaining = db.get_sessions(limit=1)
            if remaining:
                st.session_state.active_session = remaining[0]["session_id"]
            else:
                new_session()
        st.rerun()

    st.divider()


# ------------------------------------------------------------------
# Ana ekran — kontrol paneli
# ------------------------------------------------------------------
mode_label, mode_color = "MOCK", "#8B98A5"
if config.API_MODE == "evren":
    mode_label, mode_color = f"EVREN · {config.EVREN_MODEL}", "#3DD68C"
elif config.USE_LOCAL_MODEL:
    mode_label, mode_color = f"YEREL · {config.LOCAL_MODEL_NAME}", "#F5A524"
elif config.MOCK_MODE:
    mode_label, mode_color = "MOCK MOD", "#E5484D"

if model is None:
    st.error(f"YOLO model dosyası bulunamadı: `{config.YOLO_MODEL_PATH}`")

summary = db.get_dashboard_summary()
st.markdown(
    '<div class="tg-panel">'
    '<div class="tg-panel-top">'
    '<div class="tg-title-row">'
    '<span style="font-size:1.4rem;">🛡️</span>'
    '<span class="tg-title">Kontrol Merkezi</span>'
    f'<span class="tg-badge" style="color:{mode_color};border-color:{mode_color}55;'
    f'background:{mode_color}22;">{mode_label}</span>'
    '</div>'
    '</div>'
    '<div class="tg-stat-strip">'
    f'<div class="tg-stat"><div class="tg-stat-label">Toplam Olay</div>'
    f'<div class="tg-stat-value">{summary["total_events"]}</div></div>'
    f'<div class="tg-stat"><div class="tg-stat-label">Kritik Olay</div>'
    f'<div class="tg-stat-value" style="color:#E5484D;">{summary["critical_events"]}</div></div>'
    f'<div class="tg-stat"><div class="tg-stat-label">Ort. Güven</div>'
    f'<div class="tg-stat-value">{summary["avg_confidence"]:.2f}</div></div>'
    f'<div class="tg-stat"><div class="tg-stat-label">Ajan Başarı</div>'
    f'<div class="tg-stat-value">%{summary["avg_agent_success_rate"]:.1f}</div></div>'
    '</div>'
    '</div>', unsafe_allow_html=True)

c5a, c5b = st.columns([4, 2])[1].columns(2)

EXAMPLE_QUERIES = {
    "Son 10 olay": "SELECT * FROM video_events ORDER BY created_at DESC LIMIT 10",
    "Kritik olaylar": "SELECT * FROM video_events WHERE severity_level = 'Kritik' ORDER BY created_at DESC LIMIT 20",
    "Ajan performansı": "SELECT agent_name, COUNT(*) AS adet, AVG(execution_time_ms) AS ort_sure_ms FROM agent_executions GROUP BY agent_name",
    "Tetiklenen araçlar": "SELECT tool_name, COUNT(*) AS adet FROM tool_calls GROUP BY tool_name",
    "Tüm pipeline çalıştırmaları": "SELECT * FROM pipeline_runs ORDER BY created_at DESC LIMIT 20",
}

if "show_sql_view" not in st.session_state:
    st.session_state.show_sql_view = False
if "show_kpi_view" not in st.session_state:
    st.session_state.show_kpi_view = False

if c5a.button("📊 KPI Paneli", use_container_width=True):
    st.session_state.show_kpi_view = not st.session_state.show_kpi_view
    st.session_state.show_sql_view = False
    st.rerun()

if c5b.button("🗄️ SQL Sorgu", use_container_width=True):
    st.session_state.show_sql_view = not st.session_state.show_sql_view
    st.session_state.show_kpi_view = False
    st.rerun()

st.divider()

if st.session_state.show_kpi_view:
    if st.button("← Sohbete dön", key="kpi_back"):
        st.session_state.show_kpi_view = False
        st.rerun()

    st.markdown("## 📊 KPI Ölçüm Paneli")
    st.caption("Ölçüm protokolü: canlı sistemden gerçek zamanlı toplanan veriler. "
               "Recall / yanlış-alarm / zaman-damgası-sapması burada yok — bunlar "
               "etiketli bir hold-out test seti gerektirir, ayrı bir değerlendirme "
               "scripti ile ölçülmelidir.")

    kpi_engine = KPIEngine(db)
    m = kpi_engine.get_measured_kpi_summary()

    k1, k2, k3 = st.columns(3)
    with k1:
        st.markdown("#### JSON Şema Geçerliliği")
        if m["schema_valid_n"]:
            st.markdown(f"<div class='tg-kpi-value' style='font-size:2rem;'>%{m['schema_valid_pct']:.1f}</div>",
                        unsafe_allow_html=True)
            st.caption(f"{m['schema_valid_n']} çağrı üzerinden ölçüldü")
        else:
            st.caption("Henüz veri yok")
    with k2:
        st.markdown("#### Uçtan Uca Gecikme (Türkçe rapor)")
        if m["latency_n"]:
            st.markdown(f"<div class='tg-kpi-value' style='font-size:2rem;'>p50: {m['latency_p50_sec']:.1f}sn</div>",
                        unsafe_allow_html=True)
            st.caption(f"p90: {m['latency_p90_sec']:.1f}sn · {m['latency_n']} tetikleme üzerinden")
        else:
            st.caption("Henüz veri yok")
    with k3:
        st.markdown("#### Türkçe Özet/Aksiyon Kalitesi")
        if m["human_quality_n"]:
            st.markdown(f"<div class='tg-kpi-value' style='font-size:2rem;'>{m['human_quality_avg']:.1f}/5</div>",
                        unsafe_allow_html=True)
            st.caption(f"{m['human_quality_n']} operatör değerlendirmesi (rapor altındaki yıldızlarla toplanıyor)")
        else:
            st.caption("Henüz değerlendirme yok — rapor mesajlarının altındaki yıldızları kullanın")

    st.divider()
    k4, k5 = st.columns(2)
    with k4:
        st.markdown("#### YOLO Tarama Hızı (donanım)")
        if m["yolo_fps_avg"]:
            st.markdown(f"<div class='tg-kpi-value' style='font-size:2rem;'>{m['yolo_fps_avg']:.1f} FPS</div>",
                        unsafe_allow_html=True)
        else:
            st.caption("Henüz veri yok")
    with k5:
        st.markdown("#### Tepe VRAM Kullanımı")
        if m["peak_vram_mb"]:
            st.markdown(f"<div class='tg-kpi-value' style='font-size:2rem;'>{m['peak_vram_mb']:.0f} MB</div>",
                        unsafe_allow_html=True)
        else:
            st.caption("GPU tespit edilmedi ya da EVREN modunda (uzak GPU, ölçülemez)")

elif st.session_state.show_sql_view:
    if st.button("← Sohbete dön"):
        st.session_state.show_sql_view = False
        st.rerun()

    st.markdown("## 🗄️ Veritabanı Sorgu Aracı")
    st.caption("Örnek bir soruya tıklayın ya da kendi sorgunuzu yazın (salt-okunur).")

    qcols = st.columns(len(EXAMPLE_QUERIES))
    for col, (label, q) in zip(qcols, EXAMPLE_QUERIES.items()):
        if col.button(label, key=f"ex_{label}", use_container_width=True):
            st.session_state.sql_query = q
            st.session_state.sql_result = db.execute_readonly_query(q)

    custom_q = st.text_area("Kendi sorgunuz", st.session_state.get("sql_query", "SELECT * FROM video_events LIMIT 10"), height=100)
    if st.button("Çalıştır", key="run_custom_sql", type="primary"):
        st.session_state.sql_query = custom_q
        st.session_state.sql_result = db.execute_readonly_query(custom_q)

    if st.session_state.get("sql_result"):
        res = st.session_state.sql_result
        if res["error"]:
            st.error(res["error"])
        else:
            st.dataframe(pd.DataFrame(res["rows"], columns=res["columns"]), use_container_width=True)

else:
    session_id = st.session_state.active_session
    messages = db.get_session_messages(session_id)

    with st.container(border=True):
        section_title("🎥 Video Yükle ve Analiz Et")
        with st.form(key=f"upload_form_{session_id}", clear_on_submit=True):
            uploaded = st.file_uploader("Video dosyası seçin", type=["mp4", "avi", "mov", "mkv"])
            submitted = st.form_submit_button("▶️ Analiz Et", type="primary")
        if submitted and uploaded:
            try:
                process_video(uploaded, session_id)
            except Exception as e:
                import traceback
                st.error(f"Video işlenirken hata oluştu:\n```\n{traceback.format_exc()}\n```")
            st.rerun()
        elif submitted and not uploaded:
            st.warning("Önce bir video dosyası seçin.")

    section_title("💬 Sohbet")

    col_chat, col_status = st.columns([2, 1])

    with col_status:
        video_title = None
        session_row = next((s for s in db.get_sessions(limit=50) if s["session_id"] == session_id), None)
        session_events_for_name = db.get_events(session_id=session_id, limit=1)
        if session_events_for_name:
            video_title = session_events_for_name[0]["source_name"]
        elif session_row and session_row["title"] and session_row["title"] != "Yeni sohbet":
            video_title = session_row["title"]

        section_title(f"Tespit Edilen Durumlar — {video_title}" if video_title else "Tespit Edilen Durumlar")
        events = db.get_events(session_id=session_id, limit=15)
        if not events:
            st.caption("Henüz olay yok.")
        for e in events:
            color = SEVERITY_COLOR.get(e["severity_level"], "#3D4552")
            try:
                aksiyonlar = json.loads(e.get("onerilen_aksiyonlar") or "[]")
            except (json.JSONDecodeError, TypeError):
                aksiyonlar = []
            try:
                araclar = json.loads(e.get("tetiklenen_araclar") or "[]")
            except (json.JSONDecodeError, TypeError):
                araclar = []
            gerekce = e.get("gerekce") or ""

            extra = ""
            if gerekce:
                extra += f'<div class="tg-event-extra"><b>Gerekçe:</b> {gerekce}</div>'
            if aksiyonlar:
                extra += f'<div class="tg-event-extra"><b>Öneriler:</b> {", ".join(aksiyonlar)}</div>'
            if araclar:
                extra += f'<div class="tg-event-extra"><b>Tetiklenen araçlar:</b> {", ".join(araclar)}</div>'

            st.markdown(
                f'<div class="tg-event-card" style="--sev:{color};">'
                f'<div class="tg-event-title">{e["incident_type"]}'
                f'<span class="tg-sev-pill" style="background:{color};">{e["severity_level"]}</span></div>'
                f'<div class="tg-event-meta">{e["event_start"]} · güven {e["guven"]:.2f}</div>'
                f'{extra}'
                f'</div>', unsafe_allow_html=True)

    with col_chat:
        for m in messages:
            with st.chat_message(m["role"]):
                if m["message_type"] == "video_event":
                    payload = json.loads(m["payload_json"])
                    st.markdown(f"**{m['content']}**")
                    st.caption(f"{payload['channel']} kanalı, ~{payload['timestamp']}sn — risk: {payload['risk']}")
                elif m["message_type"] == "video_report":
                    payload = json.loads(m["payload_json"])
                    st.markdown(m["content"])
                    for o in payload["olaylar"]:
                        st.markdown(f"- `{o['zaman']}` **{o['olay']}** ({o['seviye']}, güven: {o['guven']:.2f})")
                    if payload["aksiyon_onerileri"]:
                        st.caption("Önerilen aksiyonlar: " + ", ".join(payload["aksiyon_onerileri"]))
                    with st.expander("JSON"):
                        st.json(payload)

                    rating_key = f"rating_{m['message_id']}"
                    prev = st.session_state.get(rating_key)
                    stars = st.feedback("stars", key=f"widget_{m['message_id']}")
                    if stars is not None and stars != prev:
                        st.session_state[rating_key] = stars
                        db.save_kpi(payload.get("_run_id"), "human_quality_rating", float(stars + 1),
                                    metadata={"message_id": m["message_id"], "video": payload.get("video")})
                    st.caption("Bu analiz kalitesini değerlendirin (Türkçe özet/aksiyon kalitesi ölçümü için)")
                elif m["message_type"] == "confirm_action" and not m["resolved"]:
                    st.markdown(m["content"])
                    payload = json.loads(m["payload_json"])
                    label = payload.get("confirm_label", "✅ Onayla ve uygula")
                    bcol1, bcol2 = st.columns(2)
                    if bcol1.button(label, key=f"yes_{m['message_id']}"):
                        handle_confirm(m["message_id"], session_id, payload, True)
                        st.rerun()
                    if bcol2.button("❌ Hayır, gerek yok", key=f"no_{m['message_id']}"):
                        handle_confirm(m["message_id"], session_id, payload, False)
                        st.rerun()
                elif m["message_type"] == "confirm_action" and m["resolved"]:
                    st.markdown(m["content"])
                    st.caption("(yanıtlandı)")
                else:
                    st.markdown(m["content"])

        user_msg = st.chat_input("Bir mesaj yazın...")
        if user_msg:
            db.add_message(session_id, "user", user_msg, "text")
            db.touch_session(session_id)
            with st.spinner("Düşünüyor..."):
                history = [{"role": m["role"], "content": _message_to_text(m)} for m in messages]
                reply = send_chat_message(db, user_msg, history, session_id=session_id)
            db.add_message(session_id, "assistant", reply, "text")
            st.rerun()
