import logging
from unittest.mock import MagicMock
import pytest
from src.telemetry.collector import TelemetryCollector
from src.telemetry.models import RecordType, TelemetryRecord
from src.telemetry.sanitizer import REDACTED_VALUE, TelemetrySanitizer
from src.telemetry.service import TelemetryService


@pytest.fixture
def mock_collector() -> MagicMock:
    collector = MagicMock(spec=TelemetryCollector)
    collector.send.return_value = True
    return collector


@pytest.fixture
def mock_logger() -> MagicMock:
    return MagicMock(spec=logging.Logger)


@pytest.fixture
def telemetry_service(
    mock_collector: MagicMock, mock_logger: MagicMock
) -> TelemetryService:
    return TelemetryService(
        collector=mock_collector,
        sanitizer=TelemetrySanitizer(),
        logger_instance=mock_logger,
    )


def test_emit_metric_success(mock_collector: MagicMock, telemetry_service: TelemetryService) -> None:
    tags = {"environment": "production", "region": "us-east-1"}
    result = telemetry_service.emit_metric("http.request.duration", 124.5, tags=tags)

    assert result is True
    mock_collector.send.assert_called_once()
    record: TelemetryRecord = mock_collector.send.call_args[0][0]

    assert record.name == "http.request.duration"
    assert record.record_type == RecordType.METRIC
    assert record.payload["value"] == 124.5
    assert record.payload["tags"] == tags
    assert record.record_id is not None
    assert record.timestamp is not None


def test_emit_metric_with_default_tags(mock_collector: MagicMock, telemetry_service: TelemetryService) -> None:
    result = telemetry_service.emit_metric("cache.hit", 1)

    assert result is True
    record: TelemetryRecord = mock_collector.send.call_args[0][0]
    assert record.payload == {"value": 1, "tags": {}}


def test_emit_event_success(mock_collector: MagicMock, telemetry_service: TelemetryService) -> None:
    details = {"order_id": "ord-987", "status": "PROCESSED"}
    result = telemetry_service.emit_event("order.checkout", payload=details, level="info")

    assert result is True
    record: TelemetryRecord = mock_collector.send.call_args[0][0]
    assert record.name == "order.checkout"
    assert record.record_type == RecordType.EVENT
    assert record.payload["level"] == "INFO"
    assert record.payload["details"] == details


def test_emit_event_defaults(mock_collector: MagicMock, telemetry_service: TelemetryService) -> None:
    result = telemetry_service.emit_event("app.started")

    assert result is True
    record: TelemetryRecord = mock_collector.send.call_args[0][0]
    assert record.payload["level"] == "INFO"
    assert record.payload["details"] == {}


def test_emit_span_success(mock_collector: MagicMock, telemetry_service: TelemetryService) -> None:
    attrs = {"component": "db_pool", "db.table": "users"}
    result = telemetry_service.emit_span(
        name="db.query",
        duration_ms=45.2,
        attributes=attrs,
        trace_id="trace-123",
        span_id="span-456",
    )

    assert result is True
    record: TelemetryRecord = mock_collector.send.call_args[0][0]
    assert record.name == "db.query"
    assert record.record_type == RecordType.SPAN
    assert record.payload["duration_ms"] == 45.2
    assert record.payload["trace_id"] == "trace-123"
    assert record.payload["span_id"] == "span-456"
    assert record.payload["attributes"] == attrs


def test_emit_span_generates_identifiers_and_sanitizes_negative_duration(
    mock_collector: MagicMock, telemetry_service: TelemetryService
) -> None:
    result = telemetry_service.emit_span("background.worker", duration_ms=-10.0)

    assert result is True
    record: TelemetryRecord = mock_collector.send.call_args[0][0]
    assert record.payload["duration_ms"] == 0.0
    assert isinstance(record.payload["trace_id"], str)
    assert isinstance(record.payload["span_id"], str)
    assert record.payload["attributes"] == {}


def test_collector_returns_false_logs_warning(
    mock_collector: MagicMock,
    mock_logger: MagicMock,
    telemetry_service: TelemetryService,
) -> None:
    mock_collector.send.return_value = False
    result = telemetry_service.emit_metric("error.rate", 0.05)

    assert result is False
    mock_logger.warning.assert_called_once()
    assert "Modo degradado" in mock_logger.warning.call_args[0][0]


@pytest.mark.parametrize(
    "exception_to_raise",
    [
        ConnectionError("Connection refused to collector:4317"),
        TimeoutError("Collector endpoint timed out after 3000ms"),
        OSError("Network is unreachable"),
        RuntimeError("Unexpected serialization fault"),
    ],
)
def test_fail_safe_isolation_on_collector_exceptions(
    mock_collector: MagicMock,
    mock_logger: MagicMock,
    telemetry_service: TelemetryService,
    exception_to_raise: Exception,
) -> None:
    mock_collector.send.side_effect = exception_to_raise

    # Garantia de resiliência: nenhuma exceção é propagada ao chamador
    result = telemetry_service.emit_metric("service.health", 1.0)

    assert result is False
    mock_logger.warning.assert_called_once()
    log_msg = mock_logger.warning.call_args[0][0]
    assert "degradado" in log_msg.lower()


def test_sanitization_applied_to_events(
    mock_collector: MagicMock, telemetry_service: TelemetryService
) -> None:
    sensitive_event_data = {
        "user_id": "usr_1029",
        "password": "UltraSecret123!",
        "nested": {
            "cpf": "123.456.789-00",
            "safe_note": "Valid operational detail",
        },
    }

    telemetry_service.emit_event("user.login", payload=sensitive_event_data)

    record: TelemetryRecord = mock_collector.send.call_args[0][0]
    details = record.payload["details"]

    assert details["user_id"] == "usr_1029"
    assert details["password"] == REDACTED_VALUE
    assert details["nested"]["cpf"] == REDACTED_VALUE
    assert details["nested"]["safe_note"] == "Valid operational detail"


def test_telemetry_record_to_dict() -> None:
    record = TelemetryRecord(
        name="api.latency",
        record_type=RecordType.METRIC,
        payload={"value": 42},
    )
    data = record.to_dict()

    assert data["name"] == "api.latency"
    assert data["record_type"] == "metric"
    assert data["payload"] == {"value": 42}
    assert "record_id" in data
    assert "timestamp" in data
