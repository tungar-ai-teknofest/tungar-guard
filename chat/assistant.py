import time
from typing import List, Dict

import config
from database import DatabaseManager

AGENT_SYSTEM_PROMPT = """Sen bir saha guvenlik operasyon asistanisin. Kisa, net ve Turkce konusursun.
Emin olmadiginda tahmin etmez, sorarsin. Kritik konularda temkinli ol.
Sana verilen 'Veritabani baglami' disinda bilgi uydurma."""


def _build_context(db: DatabaseManager, session_id: str = None) -> str:
    stats = db.get_stats()
    recent_events = db.get_events(session_id=session_id, limit=20) if session_id else db.get_events(limit=10)
    scope = "bu sohbetteki/videodaki" if session_id else "genel"
    lines = [
        f"Toplam çalıştırma: {stats['total_runs']} (başarılı: {stats['successful_runs']}, başarısız: {stats['failed_runs']})",
        f"{scope} {len(recent_events)} olay (gerekçeleriyle):",
    ]
    for e in recent_events:
        lines.append(f"  - [{e['severity_level']}] {e['incident_type']} @ {e['event_start']} "
                      f"(güven: {e['guven']:.2f}) — gerekçe: {e.get('gerekce') or 'yok'}")
    return "\n".join(lines)


def send_chat_message(db: DatabaseManager, message: str, chat_history: List[Dict[str, str]] = None,
                       session_id: str = None) -> str:
    chat_history = chat_history or []
    db_context = _build_context(db, session_id=session_id)
    system_prompt = AGENT_SYSTEM_PROMPT + "\n\nVeritabanı bağlamı:\n" + db_context

    if config.API_MODE == "evren":
        from vision.evren_client import chat_evren
        return chat_evren(system_prompt, chat_history[-10:], message)

    if config.USE_LOCAL_MODEL:
        from vision.local_qwen import chat_local
        import traceback
        try:
            return chat_local(system_prompt, chat_history[-10:], message)
        except Exception:
            return f"Yerel model çağrısı başarısız oldu:\n```\n{traceback.format_exc()}\n```"

    if config.MOCK_MODE:
        time.sleep(0.3)
        return (f"[MOCK yanıt — henüz gerçek bir backend ayarlanmadı]\n\n"
                f"Sorduğunuz: \"{message}\"\n\nVeritabanı bağlamı:\n{db_context}")

    return "Bilinmeyen API modu."
