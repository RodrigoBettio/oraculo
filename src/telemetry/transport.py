from __future__ import annotations

from typing import Protocol
from src.telemetry.models import TelemetryEvent


class TelemetryTransportError(Exception):
    """Exceção base para erros de transporte de telemetria."""
    pass


class NetworkException(TelemetryTransportError):
    """Representa falhas de conectividade ou rede durante transmissão."""
    pass


class TelemetryTransport(Protocol):
    """Protocolo abstrato para despacho de lotes de eventos de telemetria."""

    def send_batch(self, events: list[TelemetryEvent]) -> None:
        """Envia uma lista de eventos de telemetria ao backend remoto."""
        ...
