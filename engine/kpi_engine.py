from typing import Dict, List, Optional
import json

from database import DatabaseManager


AGENT_CONFIDENCE_WEIGHTS = {
    "AnalysisAgent": 0.25,
    "DecisionAgent": 0.45,
    "ValidationAgent": 0.30,
}


class KPIEngine:
    def __init__(self, db: DatabaseManager):
        self.db = db

    def calculate_and_save_kpis(self, run_id: str) -> Optional[Dict]:
        executions = self.db.get_executions_by_run(run_id)
        if not executions:
            return None

        total_steps = len(executions)
        successful_steps = sum(1 for e in executions if e["status"] == "SUCCESS")
        success_rate = (successful_steps / total_steps) * 100

        avg_step_latency = sum(e["execution_time_ms"] for e in executions) / total_steps

        run_row = self.db.get_run(run_id)
        total_pipeline_latency_ms = None
        if run_row and run_row.get("total_duration_sec") is not None:
            total_pipeline_latency_ms = run_row["total_duration_sec"] * 1000

        weighted_sum, weight_total = 0.0, 0.0
        for e in executions:
            weight = AGENT_CONFIDENCE_WEIGHTS.get(e["agent_name"], 0.0)
            weighted_sum += e["mock_confidence_score"] * weight
            weight_total += weight
        weighted_confidence = (weighted_sum / weight_total) if weight_total > 0 else 0.0

        schema_penalties = 0
        for e in executions:
            try:
                out_data = json.loads(e["output_payload"])
                if not out_data.get("schema_valid", True):
                    schema_penalties += 10
            except (json.JSONDecodeError, TypeError):
                schema_penalties += 20

        self.db.save_kpi(run_id, "success_rate", success_rate)
        self.db.save_kpi(run_id, "avg_step_latency_ms", avg_step_latency)
        if total_pipeline_latency_ms is not None:
            self.db.save_kpi(run_id, "total_pipeline_latency_ms", total_pipeline_latency_ms)
        self.db.save_kpi(run_id, "confidence_index_weighted", weighted_confidence)
        self.db.save_kpi(run_id, "schema_penalty", schema_penalties)

        return {
            "run_id": run_id, "success_rate": success_rate, "avg_step_latency": avg_step_latency,
            "total_pipeline_latency_ms": total_pipeline_latency_ms,
            "confidence": weighted_confidence, "penalty": schema_penalties,
        }

    def calculate_agent_level_kpis(self) -> Dict[str, float]:
        all_executions = self.db.get_all_executions()
        by_agent: Dict[str, List[float]] = {}
        for e in all_executions:
            by_agent.setdefault(e["agent_name"], []).append(e["execution_time_ms"])

        agent_averages = {}
        for agent_name, durations in by_agent.items():
            avg = sum(durations) / len(durations)
            agent_averages[agent_name] = avg
            self.db.save_kpi(run_id=None, metric_name="agent_avg_latency_ms", metric_value=avg,
                              metadata={"agent": agent_name, "sample_size": len(durations)})
        return agent_averages

    def get_measured_kpi_summary(self) -> Dict:
        """Şartname KPI tablosundaki, canlı veriden gerçekten ölçülebilen metrikler:
        şema geçerliliği, uçtan uca gecikme (p50/p90), YOLO tarama hızı, donanım,
        insan kalite değerlendirmesi. Recall/yanlış-alarm/zaman-sapması burada YOK —
        onlar etiketli bir hold-out test seti gerektiriyor, canlı panelden ölçülemez."""
        all_kpis = self.db.get_all_kpis()

        def values_for(name):
            return sorted(r["metric_value"] for r in all_kpis if r["metric_name"] == name)

        def percentile(sorted_vals, p):
            if not sorted_vals:
                return None
            k = (len(sorted_vals) - 1) * (p / 100)
            f, c = int(k), min(int(k) + 1, len(sorted_vals) - 1)
            if f == c:
                return sorted_vals[f]
            return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)

        latencies = values_for("inference_time_ms")
        schema_flags = values_for("schema_valid")
        ratings = values_for("human_quality_rating")
        fps_vals = values_for("yolo_scan_fps")
        vram_vals = values_for("yolo_peak_vram_mb")

        return {
            "schema_valid_pct": (sum(schema_flags) / len(schema_flags) * 100) if schema_flags else None,
            "schema_valid_n": len(schema_flags),
            "latency_p50_sec": (percentile(latencies, 50) / 1000) if latencies else None,
            "latency_p90_sec": (percentile(latencies, 90) / 1000) if latencies else None,
            "latency_n": len(latencies),
            "human_quality_avg": (sum(ratings) / len(ratings)) if ratings else None,
            "human_quality_n": len(ratings),
            "yolo_fps_avg": (sum(fps_vals) / len(fps_vals)) if fps_vals else None,
            "peak_vram_mb": max(vram_vals) if vram_vals else None,
        }

    def print_terminal_dashboard(self, results: List[Dict], agent_averages: Optional[Dict[str, float]] = None) -> str:
        lines = []
        lines.append("=" * 100)
        lines.append(" " * 30 + "TUNGAR-Guard - KPI METRİK TABLOSU")
        lines.append("=" * 100)
        lines.append(f"{'Run ID (Short)':<15} | {'Başarı (%)':<10} | {'Adım Ort. (ms)':<15} | "
                      f"{'Uçtan Uca (ms)':<15} | {'Güven (ağırlıklı)':<18} | {'Şema Cezası'}")
        lines.append("-" * 100)
        for res in results:
            short_id = res['run_id'][:8] + "..."
            success = f"{res['success_rate']:.1f}%"
            step_latency = f"{res['avg_step_latency']:.2f}"
            total_latency = f"{res['total_pipeline_latency_ms']:.2f}" if res.get('total_pipeline_latency_ms') is not None else "N/A"
            conf = f"{res['confidence']:.3f}"
            penalty = f"{res['penalty']}"
            lines.append(f"{short_id:<15} | {success:<10} | {step_latency:<15} | {total_latency:<15} | {conf:<18} | {penalty}")
        lines.append("=" * 100)
        if agent_averages:
            lines.append("\nAjan Bazlı Ortalama İşlem Süresi (Tüm Çalıştırmalar Genelinde):")
            lines.append("-" * 50)
            for agent_name, avg in agent_averages.items():
                lines.append(f"  {agent_name:<20} : {avg:.2f} ms")
            lines.append("-" * 50)
        text = "\n".join(lines)
        print(text)
        return text
