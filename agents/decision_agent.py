from typing import Dict, Any, Set

from models import AgentInput
from .base_agent import BaseAgent


class DecisionAgent(BaseAgent):

    EXPECTED_KEYS = {"decision", "reasoning"}

    def __init__(self, error_rate: float = 0.0):
        super().__init__("DecisionAgent", error_rate)

    @property
    def expected_keys(self) -> Set[str]:
        return self.EXPECTED_KEYS

    def process(self, input_data: AgentInput) -> Dict[str, Any]:
        analysis = input_data.payload if isinstance(input_data.payload, dict) else {}
        scenario = analysis.get("detected_scenario", "Bilinmiyor")
        confidence = analysis.get("confidence_score", 0.5)

        if scenario in ("Normal Rutin", "Düşük"):
            decision, severity = "Onay", "Düşük"
        elif confidence < 0.75:
            decision, severity = "Manuel_İnceleme", "Orta"
        else:
            decision, severity = "Red", "Yüksek"

        return {
            "decision": decision,
            "reasoning": f"'{scenario}' tespiti (güven: {confidence:.2f}) değerlendirilerek {decision} kararı verilmiştir.",
            "severity": severity,
            "based_on_scenario": scenario,
            "based_on_confidence": confidence,
        }
