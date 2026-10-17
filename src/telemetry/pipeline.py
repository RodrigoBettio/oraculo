from __future__ import annotations

import logging
import re
import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Mapping, Protocol, Sequence

logger = logging.getLogger("telemetry.pipeline")


class DropPolicy(StrEnum):
    DROP_OLDEST = "drop_oldest"
    DROP_CURRENT = "drop_current"


class EventType(StrEnum):
    METRIC = "metric"
    SPAN = "span"
    EVENT = "event"


_SANITIZE_NAME_REGEX = re.compile(r"[^a-zA-Z0-9_.:/-]")
_SANITIZE_LABEL_REGEX = re.compile(r"[^a-zA-Z0-9_.-]")


def sanitize_name(name: str) -> str:
    stripped = name.strip()
    if not stripped:
        return "unnamed_metric"
    return _SANITIZE_NAME_REGEX.sub("_", stripped)


def sanitize_label_key(key: str) -> str:
    stripped = key.strip()
    if not stripped:
        return "invalid_key"
    return _SANITIZE_LABEL_REGEX.sub("_", stripped)


def sanitize_label_value(value: Any) -> str:
    str_val = str(value).strip()
    return _SANITIZE_LABEL_REGEX.sub("_", str_val)


@dataclass(frozen=True, slots=True)
class TelemetryEvent:
    name: str
    value: float | int
    event_type: EventType
    timestamp: datetime
    labels: dict[str, str] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "labels": dict(self.labels),
        }


class BaseExporter(Protocol):
    def export(self, events: Sequence[TelemetryEvent]) -> None:
        ...


class InMemoryExporter:
    """Thread-safe in-memory exporter ideal for hermetic tests and stubs."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._exported_batches: list[list[TelemetryEvent]] = []

    def export(self, events: Sequence[TelemetryEvent]) -> None:
        with self._lock:
            self._exported_batches.append(list(events))

    @property
    def exported_events(self) -> list[TelemetryEvent]:
        with self._lock:
            return [evt for batch in self._exported_batches for evt in batch]

    @property
    def batches(self) -> list[list[TelemetryEvent]]:
        with self._lock:
            return [list(b) for b in self._exported_batches]

    def clear(self) -> None:
        with self._lock:
            self._exported_batches.clear()


@dataclass(frozen=True, slots=True)
class TelemetryConfig:
    buffer_capacity: int = 1000
    max_batch_size: int = 100
    drop_policy: DropPolicy = DropPolicy.DROP_OLDEST

    def __post_init__(self) -> None:
        if self.buffer_capacity <= 0:
            raise ValueError("buffer_capacity must be greater than zero.")
        if self.max_batch_size <= 0:
            raise ValueError("max_batch_size must be greater than zero.")


class TelemetryPipeline:
    """
    Core telemetry processor providing robust collection, aggregation, buffer management,
    and graceful degradation against transport or exporter failures.
    """

    def __init__(
        self,
        exporter: BaseExporter,
        config: TelemetryConfig | None = None,
    ) -> None:
        self._exporter = exporter
        self._config = config or TelemetryConfig()
        self._buffer: deque[TelemetryEvent] = deque()
        self._lock = threading.RLock()
        self._dropped_events_count = 0
        self._failed_dispatches_count = 0
        self._total_recorded_count = 0

    @property
    def dropped_events_count(self) -> int:
        with self._lock:
            return self._dropped_events_count

    @property
    def failed_dispatches_count(self) -> int:
        with self._lock:
            return self._failed_dispatches_count

    @property
    def buffer_size(self) -> int:
        with self._lock:
            return len(self._buffer)

    @property
    def total_recorded_count(self) -> int:
        with self._lock:
            return self._total_recorded_count

    def _sanitize_labels(self, labels: Mapping[str, Any] | None) -> dict[str, str]:
        if not labels:
            return {}
        return {
            sanitize_label_key(k): sanitize_label_value(v)
            for k, v in labels.items()
        }

    def record(
        self,
        name: str,
        value: float | int,
        event_type: EventType = EventType.METRIC,
        labels: Mapping[str, Any] | None = None,
        timestamp: datetime | None = None,
    ) -> bool:
        """
        Records a telemetry event into the buffer.
        Guaranteed not to raise unhandled exceptions to the business caller.
        """
        try:
            event = TelemetryEvent(
                name=sanitize_name(name),
                value=value,
                event_type=event_type,
                timestamp=timestamp or datetime.now(timezone.utc),
                labels=self._sanitize_labels(labels),
            )

            with self._lock:
                self._total_recorded_count += 1
                if len(self._buffer) >= self._config.buffer_capacity:
                    self._dropped_events_count += 1
                    if self._config.drop_policy == DropPolicy.DROP_CURRENT:
                        logger.warning(
                            "Telemetry buffer full. Dropping incoming event: %s",
                            event.name,
                        )
                        return False
                    
                    # Drop oldest policy
                    dropped = self._buffer.popleft()
                    logger.warning(
                        "Telemetry buffer full. Dropping oldest event: %s",
                        dropped.name,
                    )

                self._buffer.append(event)
                return True
        except Exception as exc:
            logger.error("Unexpected error while recording telemetry event: %s", exc, exc_info=True)
            return False

    def record_metric(self, name: str, value: float | int, labels: Mapping[str, Any] | None = None) -> bool:
        return self.record(name=name, value=value, event_type=EventType.METRIC, labels=labels)

    def record_span(self, name: str, duration_ms: float, labels: Mapping[str, Any] | None = None) -> bool:
        return self.record(name=name, value=duration_ms, event_type=EventType.SPAN, labels=labels)

    def flush(self, max_records: int | None = None) -> int:
        """
        Dispatches buffered events to the configured exporter in batches.
        Catches exporter and I/O failures to ensure graceful degradation.
        Returns the count of successfully exported events.
        """
        with self._lock:
            if not self._buffer:
                return 0

            limit = max_records if max_records is not None else self._config.max_batch_size
            batch_to_export: list[TelemetryEvent] = []
            for _ in range(min(limit, len(self._buffer))):
                batch_to_export.append(self._buffer.popleft())

        if not batch_to_export:
            return 0

        try:
            self._exporter.export(batch_to_export)
            return len(batch_to_export)
        except Exception as exc:
            logger.error(
                "Failed to export telemetry batch of %d events: %s",
                len(batch_to_export),
                exc,
                exc_info=True,
            )
            with self._lock:
                self._failed_dispatches_count += 1
            return 0

    def flush_all(self) -> int:
        """Flushes all items in buffer until empty or export failure."""
        total_dispatched = 0
        while True:
            with self._lock:
                has_more = len(self._buffer) > 0
            if not has_more:
                break
            dispatched = self.flush()
            if dispatched == 0:
                break
            total_dispatched += dispatched
        return total_dispatched
