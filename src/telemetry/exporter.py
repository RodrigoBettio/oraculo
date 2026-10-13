from abc import ABC, abstractmethod
from typing import Sequence

from src.telemetry.models import MetricRecord


class TelemetryExporter(ABC):
    @abstractmethod
    def export(self, batch: Sequence[MetricRecord]) -> bool:
        """Exporta um lote de métricas."""
        pass

    @abstractmethod
    def shutdown(self) -> None:
        """Encerra e limpa recursos utilizados pelo exportador."""
        pass
