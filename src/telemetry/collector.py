from abc import ABC, abstractmethod
from typing import Protocol
from src.telemetry.models import TelemetryRecord


class TelemetryCollector(Protocol):
    def send(self, record: TelemetryRecord) -> bool:
        """Despacha um registro para o coletor externo."""
        ...


class BaseCollector(ABC):
    @abstractmethod
    def send(self, record: TelemetryRecord) -> bool:
        raise NotImplementedError
