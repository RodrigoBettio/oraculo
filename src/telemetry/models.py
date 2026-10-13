from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class TelemetryEvent:
    """Representa um evento imutável e normalizado de telemetria."""

    name: str
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )
    properties: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, float] = field(default_factory=dict)
    context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serializa o evento para formato de dicionário compatível com JSON."""
        return {
            "event_id": self.event_id,
            "name": self.name,
            "timestamp": self.timestamp,
            "properties": dict(self.properties),
            "metrics": dict(self.metrics),
            "context": dict(self.context),
        }
