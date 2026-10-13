from dataclasses import dataclass, field
from enum import Enum
import time
from typing import Any, Union

TagValue = Union[str, int, float, bool]


class MetricType(str, Enum):
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"


@dataclass
class MetricRecord:
    name: str
    value: Union[int, float]
    metric_type: MetricType = MetricType.COUNTER
    attributes: dict[str, TagValue] = field(default_factory=dict)
    timestamp_nano: int = field(default_factory=time.time_ns)

    def to_otel_payload(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "type": self.metric_type.value,
            "value": self.value,
            "attributes": self.attributes,
            "timestamp_nano": self.timestamp_nano,
        }
