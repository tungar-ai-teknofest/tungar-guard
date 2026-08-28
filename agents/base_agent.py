import time
import random
from abc import ABC, abstractmethod
from typing import Dict, Any, Set

from models import AgentInput, AgentOutput


class BaseAgent(ABC):
    def __init__(self, name: str, error_rate: float = 0.0):
        self.name = name
        self.error_rate = error_rate

    @property
    @abstractmethod
    def expected_keys(self) -> Set[str]:
        raise NotImplementedError

    @abstractmethod
    def process(self, input_data: AgentInput) -> Dict[str, Any]:
        raise NotImplementedError

    def _validate_schema(self, result_data: Dict[str, Any]):
        actual_keys = set(result_data.keys())
        missing = sorted(self.expected_keys - actual_keys)
        return (len(missing) == 0), missing

    def execute(self, input_data: AgentInput) -> AgentOutput:
        time.sleep(random.uniform(0.05, 0.2))

        if random.random() < self.error_rate:
            return AgentOutput(
                agent_name=self.name, result_data={}, confidence_score=0.0, status="FAILED",
                error_message=f"{self.name} işlem sırasında bir hata ile karşılaştı (Simulated Error).",
                schema_valid=False, missing_keys=sorted(self.expected_keys),
            )

        try:
            result = self.process(input_data)
            schema_valid, missing_keys = self._validate_schema(result)
            confidence = result.get("confidence_score", round(random.uniform(0.75, 0.99), 2))
            return AgentOutput(
                agent_name=self.name, result_data=result, confidence_score=confidence, status="SUCCESS",
                schema_valid=schema_valid, missing_keys=missing_keys if missing_keys else None,
            )
        except Exception as e:
            return AgentOutput(
                agent_name=self.name, result_data={}, confidence_score=0.0, status="FAILED",
                error_message=str(e), schema_valid=False, missing_keys=sorted(self.expected_keys),
            )
