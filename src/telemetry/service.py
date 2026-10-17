import logging
from typing import Any
import uuid
from src.telemetry.collector import TelemetryCollector
from src.telemetry.models import RecordType, TelemetryRecord
from src.telemetry.sanitizer import TelemetrySanitizer

logger = logging.getLogger("telemetry.service")


class TelemetryService:
    """Classe central de telemetria com isolamento estrito contra falhas e sanitização PII."""

    def __init__(
        self,
        collector: TelemetryCollector,
        sanitizer: TelemetrySanitizer | None = None,
        logger_instance: logging.Logger | None = None,
    ) -> None:
        self._collector: TelemetryCollector = collector
        self._sanitizer: TelemetrySanitizer = sanitizer or TelemetrySanitizer()
        self._logger: logging.Logger = logger_instance or logger

    def emit_metric(
        self,
        name: str,
        value: float | int,
        tags: dict[str, Any] | None = None,
    ) -> bool:
        payload: dict[str, Any] = {
            "value": value,
            "tags": tags or {},
        }
        return self._dispatch(name=name, record_type=RecordType.METRIC, payload=payload)

    def emit_event(
        self,
        name: str,
        payload: dict[str, Any] | None = None,
        level: str = "INFO",
    ) -> bool:
        data: dict[str, Any] = {
            "level": level.upper(),
            "details": payload or {},
        }
        return self._dispatch(name=name, record_type=RecordType.EVENT, payload=data)

    def emit_span(
        self,
        name: str,
        duration_ms: float,
        attributes: dict[str, Any] | None = None,
        trace_id: str | None = None,
        span_id: str | None = None,
    ) -> bool:
        payload: dict[str, Any] = {
            "duration_ms": max(0.0, float(duration_ms)),
            "trace_id": trace_id or str(uuid.uuid4()),
            "span_id": span_id or str(uuid.uuid4()),
            "attributes": attributes or {},
        }
        return self._dispatch(name=name, record_type=RecordType.SPAN, payload=payload)

    def _dispatch(
        self,
        name: str,
        record_type: RecordType,
        payload: dict[str, Any],
    ) -> bool:
        try:
            sanitized_payload = self._sanitizer.sanitize(payload)
            record = TelemetryRecord(
                name=name,
                record_type=record_type,
                payload=sanitized_payload,
            )
            success = self._collector.send(record)
            if not success:
                self._logger.warning(
                    "Falha ao despachar registro de telemetria [%s: %s]. Modo degradado.",
                    record_type.value,
                    name,
                )
            return bool(success)
        except Exception as exc:
            # FAIL-SAFE: Nenhuma exceção deve interromper o fluxo de negócio do chamador.
            self._logger.warning(
                "Coletor de telemetria indisponível ou em timeout. Operando em modo degradado. Erro: %s",
                exc,
                exc_info=False,
            )
            return False
