import random
from typing import Dict, Any, Set

from models import AgentInput
from .base_agent import BaseAgent


class AnalysisAgent(BaseAgent):

    EXPECTED_KEYS = {"detected_intent", "extracted_entities", "analysis_summary"}

    def __init__(self, error_rate: float = 0.0):
        super().__init__("AnalysisAgent", error_rate)

    @property
    def expected_keys(self) -> Set[str]:
        return self.EXPECTED_KEYS

    def process(self, input_data: AgentInput) -> Dict[str, Any]:
        payload = input_data.payload if isinstance(input_data.payload, dict) else {}
        real_vision = payload.get("real_vision")

        if real_vision:
            hazards = real_vision.get("hazards", [])
            return {
                "detected_intent": "risk_analysis",
                "extracted_entities": hazards if hazards else ["genel_gözlem"],
                "analysis_summary": real_vision.get("genel_ozet", ""),
                "detected_scenario": real_vision.get("risk", "Düşük"),
                "confidence_score": real_vision.get("guven", 0.85),
                "is_real_ai": True,
                "raw_vision": real_vision,
            }

        scenarios = ["Normal Rutin", "Forklift Devrilmesi", "Baretsiz Personel", "Yerde Hareketsiz Kişi"]
        detected = payload.get("forced_scenario") or random.choice(scenarios)
        return {
            "detected_intent": "risk_analysis",
            "extracted_entities": ["forklift", "personnel", "red_zone"],
            "analysis_summary": f"Mock analiz: {detected} senaryosu tespit edildi.",
            "detected_scenario": detected,
            "confidence_score": round(random.uniform(0.65, 0.95), 2),
            "is_real_ai": False,
        }
