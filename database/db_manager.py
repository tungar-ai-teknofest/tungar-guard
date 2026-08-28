import sqlite3
import uuid
import time
import json
from typing import Dict, Any, List, Optional

from models import AgentExecution, VideoEvent


class DatabaseManager:
    def __init__(self, db_path: str = "tungar_guard.db"):
        self.db_path = db_path
        self.init_db()

    class _ConnectionContext:
        def __init__(self, db_path: str):
            self.db_path = db_path
            self.conn: Optional[sqlite3.Connection] = None

        def __enter__(self) -> sqlite3.Connection:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.execute("PRAGMA foreign_keys = ON")
            return self.conn

        def __exit__(self, exc_type, exc_val, exc_tb):
            try:
                if exc_type is None:
                    self.conn.commit()
                else:
                    self.conn.rollback()
            finally:
                self.conn.close()
            return False

    def _get_connection(self):
        return self._ConnectionContext(self.db_path)

    def init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    title TEXT,
                    created_at REAL,
                    updated_at REAL
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS chat_messages (
                    message_id TEXT PRIMARY KEY,
                    session_id TEXT,
                    role TEXT,
                    content TEXT,
                    message_type TEXT,
                    payload_json TEXT,
                    resolved INTEGER DEFAULT 0,
                    created_at REAL,
                    FOREIGN KEY(session_id) REFERENCES sessions(session_id)
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS pipeline_runs (
                    run_id TEXT PRIMARY KEY,
                    status TEXT,
                    video_name TEXT,
                    session_id TEXT,
                    created_at REAL,
                    completed_at REAL,
                    total_duration_sec REAL
                )
            ''')
            try:
                cursor.execute("ALTER TABLE pipeline_runs ADD COLUMN session_id TEXT")
            except sqlite3.OperationalError:
                pass

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS agent_executions (
                    execution_id TEXT PRIMARY KEY,
                    run_id TEXT,
                    agent_name TEXT,
                    input_payload TEXT,
                    output_payload TEXT,
                    status TEXT,
                    execution_time_ms REAL,
                    mock_confidence_score REAL,
                    FOREIGN KEY(run_id) REFERENCES pipeline_runs(run_id)
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS kpi_metrics (
                    metric_id TEXT PRIMARY KEY,
                    run_id TEXT,
                    metric_name TEXT,
                    metric_value REAL,
                    metadata TEXT,
                    FOREIGN KEY(run_id) REFERENCES pipeline_runs(run_id)
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS video_events (
                    event_id TEXT PRIMARY KEY,
                    run_id TEXT,
                    session_id TEXT,
                    source_name TEXT,
                    event_start TEXT,
                    event_peak TEXT,
                    event_end TEXT,
                    faz TEXT,
                    incident_type TEXT,
                    severity_level TEXT,
                    guven REAL,
                    gerekce TEXT,
                    onerilen_aksiyonlar TEXT,
                    tetiklenen_araclar TEXT,
                    kanit_json TEXT,
                    inference_ms REAL,
                    created_at REAL,
                    FOREIGN KEY(run_id) REFERENCES pipeline_runs(run_id)
                )
            ''')
            try:
                cursor.execute("ALTER TABLE video_events ADD COLUMN session_id TEXT")
            except sqlite3.OperationalError:
                pass
            try:
                cursor.execute("ALTER TABLE video_events ADD COLUMN inference_ms REAL")
            except sqlite3.OperationalError:
                pass

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tool_calls (
                    call_id TEXT PRIMARY KEY,
                    run_id TEXT,
                    event_id TEXT,
                    tool_name TEXT,
                    arguments TEXT,
                    result TEXT,
                    created_at REAL
                )
            ''')
            conn.commit()

    # sessions ------------------------------------------------------

    def create_session(self, session_id: str, title: str = "Yeni sohbet"):
        with self._get_connection() as conn:
            now = time.time()
            conn.execute(
                "INSERT INTO sessions (session_id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (session_id, title, now, now)
            )

    def touch_session(self, session_id: str, title: Optional[str] = None):
        with self._get_connection() as conn:
            if title:
                conn.execute("UPDATE sessions SET updated_at = ?, title = ? WHERE session_id = ?",
                             (time.time(), title, session_id))
            else:
                conn.execute("UPDATE sessions SET updated_at = ? WHERE session_id = ?",
                             (time.time(), session_id))

    def get_sessions(self, limit: int = 50) -> List[Dict]:
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            return [dict(r) for r in conn.execute(
                "SELECT * FROM sessions ORDER BY updated_at DESC LIMIT ?", (limit,)
            ).fetchall()]

    def delete_session(self, session_id: str):
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            run_ids = [r["run_id"] for r in conn.execute(
                "SELECT run_id FROM pipeline_runs WHERE session_id = ?", (session_id,)
            ).fetchall()]
            for rid in run_ids:
                conn.execute("DELETE FROM kpi_metrics WHERE run_id = ?", (rid,))
                conn.execute("DELETE FROM agent_executions WHERE run_id = ?", (rid,))
                conn.execute("DELETE FROM tool_calls WHERE run_id = ?", (rid,))
            conn.execute("DELETE FROM video_events WHERE session_id = ?", (session_id,))
            conn.execute("DELETE FROM pipeline_runs WHERE session_id = ?", (session_id,))
            conn.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
            conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))

    # chat_messages ---------------------------------------------------

    def add_message(self, session_id: str, role: str, content: str,
                     message_type: str = "text", payload: Dict = None) -> str:
        message_id = str(uuid.uuid4())
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO chat_messages (message_id, session_id, role, content, message_type, payload_json, resolved, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, 0, ?)",
                (message_id, session_id, role, content, message_type,
                 json.dumps(payload or {}, ensure_ascii=False), time.time())
            )
        return message_id

    def resolve_message(self, message_id: str):
        with self._get_connection() as conn:
            conn.execute("UPDATE chat_messages SET resolved = 1 WHERE message_id = ?", (message_id,))

    def get_session_messages(self, session_id: str) -> List[Dict]:
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            return [dict(r) for r in conn.execute(
                "SELECT * FROM chat_messages WHERE session_id = ? ORDER BY created_at ASC", (session_id,)
            ).fetchall()]

    # pipeline_runs ---------------------------------------------------

    def create_run(self, run_id: str, status: str = "INIT", video_name: str = "", session_id: Optional[str] = None):
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO pipeline_runs (run_id, status, video_name, session_id, created_at) VALUES (?, ?, ?, ?, ?)",
                (run_id, status, video_name, session_id, time.time())
            )

    def set_run_status(self, run_id: str, status: str):
        with self._get_connection() as conn:
            conn.execute("UPDATE pipeline_runs SET status = ? WHERE run_id = ?", (status, run_id))

    def update_run(self, run_id: str, status: str, total_duration: float):
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE pipeline_runs SET status = ?, completed_at = ?, total_duration_sec = ? WHERE run_id = ?",
                (status, time.time(), total_duration, run_id)
            )

    def get_run(self, run_id: str) -> Optional[Dict]:
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM pipeline_runs WHERE run_id = ?", (run_id,)).fetchone()
            return dict(row) if row else None

    # agent_executions --------------------------------------------------

    def log_execution(self, exec_data: AgentExecution):
        with self._get_connection() as conn:
            conn.execute(
                """INSERT INTO agent_executions
                   (execution_id, run_id, agent_name, input_payload, output_payload, status, execution_time_ms, mock_confidence_score)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (exec_data.execution_id, exec_data.run_id, exec_data.agent_name,
                 exec_data.input_payload, exec_data.output_payload, exec_data.status,
                 exec_data.execution_time_ms, exec_data.mock_confidence_score)
            )

    def get_executions_by_run(self, run_id: str) -> List[Dict]:
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            return [dict(r) for r in conn.execute(
                "SELECT * FROM agent_executions WHERE run_id = ?", (run_id,)
            ).fetchall()]

    def get_all_executions(self) -> List[Dict]:
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            return [dict(r) for r in conn.execute("SELECT * FROM agent_executions").fetchall()]

    # kpi_metrics -----------------------------------------------------

    def save_kpi(self, run_id: Optional[str], metric_name: str, metric_value: float, metadata: Dict = None):
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO kpi_metrics (metric_id, run_id, metric_name, metric_value, metadata) VALUES (?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), run_id, metric_name, metric_value, json.dumps(metadata or {}, ensure_ascii=False))
            )

    def get_all_kpis(self) -> List[Dict]:
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            return [dict(r) for r in conn.execute("SELECT * FROM kpi_metrics").fetchall()]

    # video_events ------------------------------------------------------

    def insert_video_event(self, event: VideoEvent, session_id: Optional[str] = None):
        with self._get_connection() as conn:
            conn.execute(
                """INSERT INTO video_events
                   (event_id, run_id, session_id, source_name, event_start, event_peak, event_end, faz,
                    incident_type, severity_level, guven, gerekce, onerilen_aksiyonlar,
                    tetiklenen_araclar, kanit_json, inference_ms, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (event.event_id, event.run_id, session_id, event.source_name, event.event_start,
                 event.event_peak, event.event_end, event.faz, event.incident_type,
                 event.severity_level, event.guven, event.gerekce,
                 json.dumps(event.onerilen_aksiyonlar, ensure_ascii=False),
                 json.dumps(event.tetiklenen_araclar, ensure_ascii=False),
                 event.kanit_json, event.inference_ms, event.created_at or time.time())
            )

    def get_events(self, run_id: Optional[str] = None, min_severity: Optional[str] = None,
                   session_id: Optional[str] = None, limit: int = 100) -> List[Dict]:
        query = "SELECT * FROM video_events WHERE 1=1"
        params: List[Any] = []
        if run_id:
            query += " AND run_id = ?"
            params.append(run_id)
        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)
        if min_severity:
            query += " AND severity_level = ?"
            params.append(min_severity)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            return [dict(r) for r in conn.execute(query, params).fetchall()]

    def get_event_detail(self, event_id: str) -> Optional[Dict]:
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM video_events WHERE event_id = ?", (event_id,)).fetchone()
            return dict(row) if row else None

    # tool_calls ----------------------------------------------------

    def log_tool_call(self, run_id: str, event_id: Optional[str], tool_name: str, arguments: Dict, result: Dict):
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO tool_calls (call_id, run_id, event_id, tool_name, arguments, result, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), run_id, event_id, tool_name,
                 json.dumps(arguments, ensure_ascii=False), json.dumps(result, ensure_ascii=False), time.time())
            )

    # istatistik / doğrulama ------------------------------------------

    def get_stats(self) -> Dict:
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            total_runs = conn.execute("SELECT COUNT(*) c FROM pipeline_runs").fetchone()["c"]
            success = conn.execute("SELECT COUNT(*) c FROM pipeline_runs WHERE status='COMPLETED'").fetchone()["c"]
            failed = conn.execute("SELECT COUNT(*) c FROM pipeline_runs WHERE status='FAILED'").fetchone()["c"]
            total_exec = conn.execute("SELECT COUNT(*) c FROM agent_executions").fetchone()["c"]
            total_kpi = conn.execute("SELECT COUNT(*) c FROM kpi_metrics").fetchone()["c"]
            orphan = conn.execute(
                "SELECT COUNT(*) c FROM agent_executions e "
                "LEFT JOIN pipeline_runs r ON e.run_id = r.run_id WHERE r.run_id IS NULL"
            ).fetchone()["c"]
            return {
                "total_runs": total_runs, "successful_runs": success, "failed_runs": failed,
                "total_executions": total_exec, "total_kpis": total_kpi,
                "orphan_executions": orphan,
            }

    def get_dashboard_summary(self) -> Dict:
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            total_events = conn.execute("SELECT COUNT(*) c FROM video_events").fetchone()["c"]
            critical = conn.execute(
                "SELECT COUNT(*) c FROM video_events WHERE severity_level = 'Kritik'"
            ).fetchone()["c"]
            avg_conf_row = conn.execute("SELECT AVG(guven) a FROM video_events").fetchone()
            avg_conf = avg_conf_row["a"] or 0.0
            avg_inf_row = conn.execute("SELECT AVG(inference_ms) a FROM video_events WHERE inference_ms > 0").fetchone()
            avg_inf = avg_inf_row["a"] or 0.0
            success_rows = conn.execute(
                "SELECT metric_value FROM kpi_metrics WHERE metric_name = 'success_rate'"
            ).fetchall()
            avg_success = (sum(r["metric_value"] for r in success_rows) / len(success_rows)) if success_rows else 0.0
            return {
                "total_events": total_events, "critical_events": critical,
                "avg_confidence": avg_conf, "avg_agent_success_rate": avg_success,
                "avg_inference_ms": avg_inf,
            }

    def execute_readonly_query(self, query: str) -> Dict:
        q = query.strip().lower()
        if not q.startswith("select"):
            return {"columns": ["hata"], "rows": [], "error": "Yalnızca SELECT sorguları desteklenir (salt-okunur)."}
        try:
            uri = f"file:{self.db_path}?mode=ro"
            conn = sqlite3.connect(uri, uri=True)
            conn.execute("PRAGMA query_only = ON")
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query)
            rows = [dict(r) for r in cursor.fetchall()]
            columns = [d[0] for d in cursor.description] if cursor.description else []
            conn.close()
            return {"columns": columns, "rows": rows, "error": None}
        except Exception as e:
            return {"columns": ["hata"], "rows": [], "error": str(e)}
