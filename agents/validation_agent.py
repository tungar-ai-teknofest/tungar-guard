import random
from typing import Dict, Any, Set

from models import AgentInput
from .base_agent import BaseAgent


class ValidationAgent(BaseAgent):

    EXPECTED_KEYS = {"is_valid", "validation_notes"}

    def __init__(self, error_rate: float = 0.0):
        super().__init__("ValidationAgent", error_rate)

    @property
    def expected_keys(self) -> Set[str]:
        return self.EXPECTED_KEYS

    def process(self, input_data: AgentInput) -> Dict[str, Any]:
        decision_payload = input_data.payload if isinstance(input_data.payload, dict) else {}
        decision = decision_payload.get("decision", "")
        severity = decision_payload.get("severity", "Düşük")

        if severity == "Yüksek" and decision == "Onay":
            return {
                "is_valid": False,
                "validation_notes": "Tutarsızlık: Yüksek riskli senaryo 'Onay' ile kapatılamaz.",
                "audit_rule_id": "TR-ISG-2026-V8",
            }

        is_valid = random.random() > 0.05
        return {
            "is_valid": is_valid,
            "validation_notes": "Karar kurallara uygun bulunmuştur." if is_valid else "Rastgele denetimde küçük bir tutarsızlık işaretlendi.",
            "audit_rule_id": "TR-ISG-2026-V8",
        }
