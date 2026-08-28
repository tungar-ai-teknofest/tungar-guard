import uuid
import time
import json
from dataclasses import asdict
from typing import Optional

from models import AgentInput, AgentOutput, AgentExecution
from database import DatabaseManager
from agents import AnalysisAgent, DecisionAgent, ValidationAgent


class PipelineEngine:
    def __init__(self, db: DatabaseManager):
        self.db = db

    def run_pipeline(self, initial_payload: dict, video_name: str = "",
                      force_error_on: Optional[str] = None,
                      error_rate: float = 0.0, session_id: Optional[str] = None) -> str:
        run_id = str(uuid.uuid4())
        pipeline_start_time = time.time()

        self.db.create_run(run_id, "INIT", video_name=video_name, session_id=session_id)
        self.db.set_run_status(run_id, "IN_PROGRESS")

        pipeline_status = "COMPLETED"

        try:
            agents = [
                AnalysisAgent(error_rate=1.0 if force_error_on == "AnalysisAgent" else error_rate),
                DecisionAgent(error_rate=1.0 if force_error_on == "DecisionAgent" else error_rate),
                ValidationAgent(error_rate=1.0 if force_error_on == "ValidationAgent" else error_rate),
            ]

            current_input = AgentInput(payload=initial_payload, metadata={"video_name": video_name})

            for agent in agents:
                step_start_time = time.time()
                output: AgentOutput = agent.execute(current_input)
                step_duration_ms = (time.time() - step_start_time) * 1000

                execution = AgentExecution(
                    execution_id=str(uuid.uuid4()), run_id=run_id, agent_name=agent.name,
                    input_payload=json.dumps(asdict(current_input), ensure_ascii=False, default=str),
                    output_payload=json.dumps(asdict(output), ensure_ascii=False, default=str),
                    status=output.status, execution_time_ms=step_duration_ms,
                    mock_confidence_score=output.confidence_score,
                )
                self.db.log_execution(execution)

                if output.status == "FAILED":
                    pipeline_status = "FAILED"
                    break

                current_input = AgentInput(payload=output.result_data, metadata=current_input.metadata)

        except Exception as e:
            pipeline_status = "FAILED"
            try:
                error_execution = AgentExecution(
                    execution_id=str(uuid.uuid4()), run_id=run_id, agent_name="PipelineEngine",
                    input_payload=json.dumps({"initial_payload": initial_payload}, ensure_ascii=False, default=str),
                    output_payload=json.dumps({"error": str(e)}, ensure_ascii=False),
                    status="FAILED", execution_time_ms=0.0, mock_confidence_score=0.0,
                )
                self.db.log_execution(error_execution)
            except Exception:
                pass

        total_duration = time.time() - pipeline_start_time
        self.db.update_run(run_id, pipeline_status, total_duration)
        return run_id
