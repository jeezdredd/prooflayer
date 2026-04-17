from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class AnalysisOutput:
    confidence: float
    verdict: str
    evidence: dict[str, Any]


class BaseAnalyzer(ABC):
    name: str
    version: str

    @abstractmethod
    def analyze(self, file_path: str, metadata: dict) -> AnalysisOutput:
        ...

    @abstractmethod
    def supported_mime_types(self) -> list[str]:
        ...
