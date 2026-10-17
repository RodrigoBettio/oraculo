from __future__ import annotations

import concurrent.futures
from datetime import datetime, timezone
from unittest.mock import MagicMock
import pytest

from src.telemetry.pipeline import (
    BaseExporter,
    DropPolicy,
    EventType,
    InMemoryExporter,
    TelemetryConfig,
    TelemetryEvent,
    TelemetryPipeline,
    sanitize_label_key,
    sanitize_label_value,
    sanitize_name,
)


class FaultyExporter(BaseExporter):
    def __init__(self, exception_to_raise: Exception) -> None:
        self.exception_to_raise = exception_to_raise
        self.call_count = 0

    def export(self, events: list[TelemetryEvent]) -> None:
        self.call_count += 1
        raise self.exception_to_raise


def test_sanitization_rules() -> None:
    assert sanitize_name("   ") == "unnamed_metric"
    assert sanitize_name("cpu.usage#percent$") == "cpu.usage_percent_"
    assert sanitize_name("order:service/request_count") == "order:service/request_count"

    assert sanitize_label_key("  ") == "invalid_key"
    assert sanitize_label_key("host-name@zone!") == "host-name_zone_"

    assert sanitize_label_value("prod region 1") == "prod_region_1"
    assert sanitize_label_value(1234) == "1234"


def test_config_validation() -> None:
    with pytest.raises(ValueError, match="buffer_capacity must be greater than zero"):
        TelemetryConfig(buffer_capacity=0)

    with pytest.raises(ValueError, match="max_batch_size must be greater than zero"):
        TelemetryConfig(max_batch_size=-1)


def test_telemetry_event_payload_formatting() -> None:
    fixed_time = datetime(2026, 10, 16, 22, 33, 0, tzinfo=timezone.utc)
    event = TelemetryEvent(
        name="http.server.duration",
        value=142.5,
        event_type=EventType.SPAN,
        timestamp=fixed_time,
        labels={"env": "production", "status": "200"},
    )

    payload = event.to_payload()
    assert payload == {
        "name": "http.server.duration",
        "value": 142.5,
        "type": "span",
        "timestamp": "2026-10-16T22:33:00+00:00",
        "labels": {"env": "production", "status": "200"},
    }


def test_metric_and_span_collection() -> None:
    exporter = InMemoryExporter()
    pipeline = TelemetryPipeline(exporter=exporter)

    res_metric = pipeline.record_metric(
        name="api.requests/count",
        value=1,
        labels={"path": "/v1/checkout", "method": "POST"},
    )
    res_span = pipeline.record_span(
        name="db.query.execution",
        duration_ms=45.2,
        labels={"db.name": "users"},
    )

    assert res_metric is True
    assert res_span is True
    assert pipeline.buffer_size == 2
    assert pipeline.total_recorded_count == 2

    exported_count = pipeline.flush()
    assert exported_count == 2
    assert pipeline.buffer_size == 0

    exported_items = exporter.exported_events
    assert len(exported_items) == 2
    assert exported_items[0].name == "api.requests/count"
    assert exported_items[0].event_type == EventType.METRIC
    assert exported_items[1].name == "db.query.execution"
    assert exported_items[1].event_type == EventType.SPAN


def test_buffer_overflow_drop_oldest_policy() -> None:
    capacity = 3
    exporter = InMemoryExporter()
    config = TelemetryConfig(buffer_capacity=capacity, drop_policy=DropPolicy.DROP_OLDEST)
    pipeline = TelemetryPipeline(exporter=exporter, config=config)

    for i in range(5):
        accepted = pipeline.record_metric(f"metric_{i}", value=i)
        assert accepted is True

    assert pipeline.buffer_size == 3
    assert pipeline.dropped_events_count == 2
    assert pipeline.total_recorded_count == 5

    pipeline.flush_all()
    exported = exporter.exported_events
    assert len(exported) == 3
    # Expect metrics 2, 3, 4 retained; 0 and 1 dropped
    assert [e.name for e in exported] == ["metric_2", "metric_3", "metric_4"]


def test_buffer_overflow_drop_current_policy() -> None:
    capacity = 2
    exporter = InMemoryExporter()
    config = TelemetryConfig(buffer_capacity=capacity, drop_policy=DropPolicy.DROP_CURRENT)
    pipeline = TelemetryPipeline(exporter=exporter, config=config)

    assert pipeline.record_metric("event_0", 10) is True
    assert pipeline.record_metric("event_1", 20) is True
    assert pipeline.record_metric("event_2", 30) is False
    assert pipeline.record_metric("event_3", 40) is False

    assert pipeline.buffer_size == 2
    assert pipeline.dropped_events_count == 2
    assert pipeline.total_recorded_count == 4

    pipeline.flush_all()
    exported = exporter.exported_events
    assert len(exported) == 2
    assert [e.name for e in exported] == ["event_0", "event_1"]


@pytest.mark.parametrize(
    "error_instance",
    [
        TimeoutError("Connection to collector timed out"),
        ConnectionRefusedError("Collector socket closed"),
        IOError("Broken pipe during export"),
        RuntimeError("Unexpected internal telemetry failure"),
    ],
)
def test_exporter_resilience_and_graceful_degradation(error_instance: Exception) -> None:
    faulty_exporter = FaultyExporter(exception_to_raise=error_instance)
    pipeline = TelemetryPipeline(exporter=faulty_exporter)

    pipeline.record_metric("critical_transaction_latency", 350)

    # The caller must not receive an exception; dispatch failure is absorbed gracefully
    dispatched = pipeline.flush()
    assert dispatched == 0
    assert faulty_exporter.call_count == 1
    assert pipeline.failed_dispatches_count == 1


def test_empty_flush_and_batch_limits() -> None:
    exporter = InMemoryExporter()
    config = TelemetryConfig(buffer_capacity=10, max_batch_size=2)
    pipeline = TelemetryPipeline(exporter=exporter, config=config)

    # Empty buffer flush
    assert pipeline.flush() == 0

    for i in range(5):
        pipeline.record_metric(f"m_{i}", i)

    # First batch of size 2
    count1 = pipeline.flush()
    assert count1 == 2
    assert pipeline.buffer_size == 3

    # Second batch of size 2
    count2 = pipeline.flush()
    assert count2 == 2
    assert pipeline.buffer_size == 1

    # Flush remaining with flush_all
    remaining = pipeline.flush_all()
    assert remaining == 1
    assert pipeline.buffer_size == 0
    assert len(exporter.exported_events) == 5


def test_in_memory_exporter_clear() -> None:
    exporter = InMemoryExporter()
    pipeline = TelemetryPipeline(exporter=exporter)
    pipeline.record_metric("test_metric", 1.0)
    pipeline.flush()
    assert len(exporter.exported_events) == 1
    assert len(exporter.batches) == 1

    exporter.clear()
    assert len(exporter.exported_events) == 0
    assert len(exporter.batches) == 0


def test_thread_concurrency_determinism() -> None:
    exporter = InMemoryExporter()
    config = TelemetryConfig(buffer_capacity=2000, max_batch_size=500)
    pipeline = TelemetryPipeline(exporter=exporter, config=config)

    threads_count = 10
    items_per_thread = 50

    def worker(worker_id: int) -> None:
        for j in range(items_per_thread):
            pipeline.record_metric(
                name=f"worker_{worker_id}_metric",
                value=j,
                labels={"thread_id": str(worker_id)},
            )

    with concurrent.futures.ThreadPoolExecutor(max_workers=threads_count) as executor:
        futures = [executor.submit(worker, i) for i in range(threads_count)]
        for f in concurrent.futures.as_completed(futures):
            f.result()

    assert pipeline.total_recorded_count == threads_count * items_per_thread
    assert pipeline.buffer_size == threads_count * items_per_thread

    flushed = pipeline.flush_all()
    assert flushed == threads_count * items_per_thread
    assert len(exporter.exported_events) == threads_count * items_per_thread
    assert pipeline.dropped_events_count == 0
