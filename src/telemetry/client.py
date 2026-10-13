from __future__ import annotations

import logging
import threading
from typing import Any

from src.telemetry.models import TelemetryEvent
from src.telemetry.transport import NetworkException, TelemetryTransport, TelemetryTransportError

logger = logging.getLogger("telemetry.client")


class TelemetryClient:
    """Cliente de telemetria com bufferização thread-safe e isolamento fail-safe."""

    def __init__(
        self,
        transport: TelemetryTransport,
        buffer_size: int = 10,
        default_context: dict[str, Any] | None = None,
        custom_logger: logging.Logger | None = None,
    ) -> None:
        if buffer_size <= 0:
            raise ValueError("buffer_size deve ser maior que zero")

        self._transport = transport
        self._buffer_size = buffer_size
        self._default_context = dict(default_context) if default_context else {}
        self._logger = custom_logger or logger

        self._lock = threading.RLock()
        self._buffer: list[TelemetryEvent] = []
        self._total_events_tracked: int = 0
        self._total_events_sent: int = 0
        self._total_failed_dispatches: int = 0

    @property
    def buffer_size(self) -> int:
        return self._buffer_size

    @property
    def buffered_count(self) -> int:
        with self._lock:
            return len(self._buffer)

    @property
    def total_events_tracked(self) -> int:
        with self._lock:
            return self._total_events_tracked

    @property
    def total_events_sent(self) -> int:
        with self._lock:
            return self._total_events_sent

    @property
    def total_failed_dispatches(self) -> int:
        with self._lock:
            return self._total_failed_dispatches

    def track_event(
        self,
        name: str | None,
        properties: dict[str, Any] | None = None,
        metrics: dict[str, float | int] | None = None,
        context: dict[str, Any] | None = None,
    ) -> bool:
        """Registra e enfileira um evento na telemetria de forma fail-safe."""
        try:
            if not name or not isinstance(name, str) or not name.strip():
                self._logger.warning("Evento ignorado: nome do evento inválido ou vazio.")
                return False

            # Sanitização e normalização de métricas
            normalized_metrics: dict[str, float] = {}
            if metrics:
                for k, v in metrics.items():
                    if isinstance(v, (int, float)) and not isinstance(v, bool):
                        normalized_metrics[k] = float(v)
                    else:
                        self._logger.warning(
                            "Métrica '%s' descartada: valor '%r' não é numérico.", k, v
                        )

            # Concatenação de contextos
            merged_context = dict(self._default_context)
            if context:
                merged_context.update(context)

            event = TelemetryEvent(
                name=name.strip(),
                properties=dict(properties) if properties else {},
                metrics=normalized_metrics,
                context=merged_context,
            )

            should_flush = False
            with self._lock:
                self._buffer.append(event)
                self._total_events_tracked += 1
                if len(self._buffer) >= self._buffer_size:
                    should_flush = True

            if should_flush:
                self.flush()

            return True
        except Exception as exc:
            # Garantia absoluta fail-safe: erros de telemetria nunca afetam fluxo de negócio
            self._logger.error(
                "Falha inesperada ao registrar evento de telemetria: %s",
                exc,
                exc_info=True,
            )
            return False

    def flush(self) -> bool:
        """Esvazia o buffer determinístico e despacha eventos ao transporte subjacente."""
        events_to_dispatch: list[TelemetryEvent] = []
        with self._lock:
            if not self._buffer:
                return True
            events_to_dispatch = list(self._buffer)
            self._buffer.clear()

        try:
            self._transport.send_batch(events_to_dispatch)
            with self._lock:
                self._total_events_sent += len(events_to_dispatch)
            return True
        except (TimeoutError, NetworkException, TelemetryTransportError) as net_err:
            with self._lock:
                self._total_failed_dispatches += 1
            self._logger.warning(
                "Falha recuperável ao despachar lote de telemetria (%d eventos): %s",
                len(events_to_dispatch),
                net_err,
            )
            return False
        except Exception as unhandled_err:
            with self._lock:
                self._total_failed_dispatches += 1
            self._logger.error(
                "Exceção crítica isolada no despacho do lote de telemetria (%d eventos): %s",
                len(events_to_dispatch),
                unhandled_err,
                exc_info=True,
            )
            return False

    def close(self) -> None:
        """Encerra o cliente garantindo o flush final de eventos remanescentes."""
        try:
            self.flush()
        except Exception as exc:
            self._logger.error("Falha ao fechar cliente de telemetria: %s", exc)
