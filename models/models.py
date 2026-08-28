from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List


@dataclass
class AgentInput:
    payload: Dict[str, Any]
    metadata: Dict[str, Any]


@dataclass
class AgentOutput:
    agent_name: str
    result_data: Dict[str, Any]
    confidence_score: float
    status: str
    error_message: Optional[str] = None
    schema_valid: bool = True
    missing_keys: Optional[list] = None


@dataclass
class PipelineRun:
    run_id: str
    status: str
    created_at: float
    video_name: str = ""
    completed_at: Optional[float] = None
    total_duration_sec: Optional[float] = None


@dataclass
class AgentExecution:
    execution_id: str
    run_id: str
    agent_name: str
    input_payload: str
    output_payload: str
    status: str
    execution_time_ms: float
    mock_confidence_score: float


@dataclass
class VideoEvent:
    event_id: str
    run_id: str
    source_name: str
    event_start: str
    event_peak: str
    event_end: str
    faz: str
    incident_type: str
    severity_level: str
    guven: float
    gerekce: str
    onerilen_aksiyonlar: List[str] = field(default_factory=list)
    tetiklenen_araclar: List[str] = field(default_factory=list)
    kanit_json: str = "{}"
    inference_ms: float = 0.0
    created_at: float = 0.0
