from typing import Dict, Any, Optional

from database import DatabaseManager


def trigger_local_alarm(db: DatabaseManager, run_id: str, event_id: Optional[str], siren_level: str = "orta") -> Dict[str, Any]:
    result = {"status": "ok", "message": f"Lokal alarm tetiklendi (seviye: {siren_level})."}
    db.log_tool_call(run_id, event_id, "trigger_local_alarm", {"siren_level": siren_level}, result)
    return result


def send_internal_log(db: DatabaseManager, run_id: str, event_id: Optional[str], message: str, priority: str = "normal") -> Dict[str, Any]:
    result = {"status": "ok", "message": "SİSTEM MESAJI kaydedildi.", "logged_message": message, "priority": priority}
    db.log_tool_call(run_id, event_id, "send_internal_log", {"message": message, "priority": priority}, result)
    return result


def call_emergency_team(db: DatabaseManager, run_id: str, event_id: Optional[str], unit: str = "saglik") -> Dict[str, Any]:
    result = {"status": "ok", "message": f"{unit} ekibi çağrısı simüle edildi ve loglandı."}
    db.log_tool_call(run_id, event_id, "call_emergency_team", {"unit": unit}, result)
    return result


def query_event_history(db: DatabaseManager, run_id: str, event_id: Optional[str],
                         min_severity: Optional[str] = None) -> Dict[str, Any]:
    events = db.get_events(min_severity=min_severity, limit=20)
    result = {"status": "ok", "count": len(events), "events": events}
    db.log_tool_call(run_id, event_id, "query_event_history", {"min_severity": min_severity}, {"count": len(events)})
    return result


def get_event_detail(db: DatabaseManager, run_id: str, event_id: str) -> Dict[str, Any]:
    detail = db.get_event_detail(event_id)
    result = {"status": "ok" if detail else "not_found", "detail": detail}
    db.log_tool_call(run_id, event_id, "get_event_detail", {"olay_id": event_id}, {"found": bool(detail)})
    return result


TOOL_REGISTRY = {
    "trigger_local_alarm": trigger_local_alarm,
    "send_internal_log": send_internal_log,
    "call_emergency_team": call_emergency_team,
    "query_event_history": query_event_history,
    "get_event_detail": get_event_detail,
}


def dispatch_tools(db: DatabaseManager, run_id: str, event_id: Optional[str],
                    tool_names: list, context_message: str = "") -> Dict[str, Any]:
    results = {}
    for name in tool_names:
        fn = TOOL_REGISTRY.get(name)
        if not fn:
            continue
        if name == "send_internal_log":
            results[name] = fn(db, run_id, event_id, message=context_message or "Olay kaydı.")
        elif name == "call_emergency_team":
            results[name] = fn(db, run_id, event_id, unit="saglik")
        elif name == "trigger_local_alarm":
            results[name] = fn(db, run_id, event_id, siren_level="yuksek")
        elif name == "query_event_history":
            results[name] = fn(db, run_id, event_id)
        elif name == "get_event_detail" and event_id:
            results[name] = fn(db, run_id, event_id)
    return results
