from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping
import uuid


class RecordType(str, Enum):
    METRIC = "metric"
    EVENT = "event"
    SPAN = "span"


@dataclass(frozen=True)
class TelemetryRecord:
    name: str
    record_type: RecordType
    payload: dict[str, Any]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    record_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "record_type": self.record_type.value,
            "name": self.name,
            "timestamp": self.timestamp.isoformat(),
            "payload": self.payload,
        }
