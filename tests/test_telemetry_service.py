import concurrent.futures
import logging
from unittest.mock import MagicMock
import pytest

from src.telemetry.exporter import TelemetryExporter
from src.telemetry.models import MetricRecord, MetricType
from src.telemetry.service import TelemetryService


@pytest.fixture
def mock_exporter() -> MagicMock:
    exporter = MagicMock(spec=TelemetryExporter)
    exporter.export.return_value = True
    exporter.shutdown.return_value = None
    return exporter


@pytest.fixture
def telemetry_service(mock_exporter: MagicMock) -> TelemetryService:
    return TelemetryService(exporter=mock_exporter, batch_size=10, max_buffer_size=100)


class TestTelemetryMetricDispatch:
    """Cenário: Registro e despacho correto de métrica customizada com tags."""

    def test_record_metric_custom_with_tags_otel_spec(self, mock_exporter: MagicMock) -> None:
        service = TelemetryService(exporter=mock_exporter, batch_size=1)
        tags = {"environment": "production", "service": "order-api", "attempt": 1, "active": True}

        result = service.record_metric(
            name="http.requests.total",
            value=1,
            metric_type=MetricType.COUNTER,
            tags=tags,
        )

        assert result is True
        assert mock_exporter.export.call_count == 1
        batch: list[MetricRecord] = mock_exporter.export.call_args[0][0]
        assert len(batch) == 1

        item = batch[0]
        assert item.name == "http.requests.total"
        assert item.value == 1
        assert item.metric_type == MetricType.COUNTER
        assert item.attributes == tags

        otel_payload = item.to_otel_payload()
        assert otel_payload["name"] == "http.requests.total"
        assert otel_payload["type"] == "counter"
        assert otel_payload["value"] == 1
        assert otel_payload["attributes"] == tags
        assert isinstance(otel_payload["timestamp_nano"], int)

    def test_record_metric_batching_threshold(self, telemetry_service: TelemetryService, mock_exporter: MagicMock) -> None:
        # batch_size configurado para 10
        for i in range(9):
            telemetry_service.record_metric(f"event.{i}", i)
        assert mock_exporter.export.call_count == 0
        assert telemetry_service.pending_count == 9

        # 10º evento aciona despacho automático
        telemetry_service.record_metric("event.9", 9)
        assert mock_exporter.export.call_count == 1
        assert telemetry_service.pending_count == 0

        dispatched_batch = mock_exporter.export.call_args[0][0]
        assert len(dispatched_batch) == 10

    def test_record_metric_handles_gauge_and_histogram(self, mock_exporter: MagicMock) -> None:
        service = TelemetryService(exporter=mock_exporter, batch_size=1)

        service.record_metric("memory.usage_mb", 512.5, metric_type=MetricType.GAUGE)
        record_gauge: MetricRecord = mock_exporter.export.call_args[0][0][0]
        assert record_gauge.metric_type == MetricType.GAUGE
        assert record_gauge.value == 512.5

        service.record_metric("request.latency_ms", 42.1, metric_type=MetricType.HISTOGRAM)
        record_hist: MetricRecord = mock_exporter.export.call_args[0][0][0]
        assert record_hist.metric_type == MetricType.HISTOGRAM
        assert record_hist.value == 42.1


class TestTelemetryFailSafeDegradation:
    """Cenário: Degradação graciosa em caso de falha no pipeline de transporte."""

    def test_network_timeout_or_connection_error_is_swallowed_silently(
        self, mock_exporter: MagicMock, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.DEBUG)
        mock_exporter.export.side_effect = TimeoutError("Connection to collector timed out")

        service = TelemetryService(exporter=mock_exporter, batch_size=1)

        # Invocação não deve propagar erro sob hipótese alguma
        result = service.record_metric("critical.payment.success", 100)
        assert result is True  # O método executou com sucesso fail-safe
        assert mock_exporter.export.call_count == 1
        assert "Falha no pipeline de transporte" in caplog.text
        assert "TimeoutError" in caplog.text

    def test_exporter_runtime_crash_does_not_affect_caller(self, mock_exporter: MagicMock) -> None:
        mock_exporter.export.side_effect = RuntimeError("Driver crashed")
        service = TelemetryService(exporter=mock_exporter, batch_size=1)

        try:
            success = service.record_metric("system.metrics", 1)
            assert success is True
        except Exception as exc:
            pytest.fail(f"Exceção nunca deveria ter sido propagada para a aplicação: {exc}")

    def test_invalid_input_parameters_handled_gracefully(self, telemetry_service: TelemetryService) -> None:
        assert telemetry_service.record_metric("", 10) is False
        assert telemetry_service.record_metric(None, 10) is False  # type: ignore[arg-type]
        assert telemetry_service.record_metric("valid.name", "not_a_number") is False  # type: ignore[arg-type]
        assert telemetry_service.pending_count == 0


class TestTelemetryLifecycleAndGracefulShutdown:
    """Cenário: Drenagem correta do buffer no evento de shutdown (Flush)."""

    def test_flush_and_close_drains_all_residual_items(self, mock_exporter: MagicMock) -> None:
        service = TelemetryService(exporter=mock_exporter, batch_size=50)

        for i in range(15):
            service.record_metric("residual.metric", i, tags={"index": i})

        assert service.pending_count == 15
        assert mock_exporter.export.call_count == 0

        # Encerramento gracioso
        service.flush_and_close()

        assert service.is_shutdown is True
        assert service.pending_count == 0
        assert mock_exporter.export.call_count == 1
        mock_exporter.shutdown.assert_called_once()

        dispatched_batch = mock_exporter.export.call_args[0][0]
        assert len(dispatched_batch) == 15
        assert [item.value for item in dispatched_batch] == list(range(15))

    def test_calling_record_after_shutdown_is_safely_ignored(self, telemetry_service: TelemetryService) -> None:
        telemetry_service.flush_and_close()
        assert telemetry_service.is_shutdown is True

        result = telemetry_service.record_metric("post.shutdown", 1)
        assert result is False
        assert telemetry_service.pending_count == 0

    def test_multiple_calls_to_flush_and_close_are_idempotent(self, telemetry_service: TelemetryService, mock_exporter: MagicMock) -> None:
        telemetry_service.flush_and_close()
        telemetry_service.flush_and_close()

        assert mock_exporter.shutdown.call_count == 1

    def test_flush_when_buffer_empty_does_not_invoke_exporter(self, telemetry_service: TelemetryService, mock_exporter: MagicMock) -> None:
        drained = telemetry_service.flush()
        assert drained == 0
        assert mock_exporter.export.call_count == 0


class TestTelemetryBufferOverflowAndValidation:
    """Testes de limites de buffer e validações estruturais."""

    def test_buffer_overflow_drops_oldest_event(self, mock_exporter: MagicMock) -> None:
        # Configura batch_size e max_buffer_size consistentes com a validação
        service = TelemetryService(exporter=mock_exporter, batch_size=3, max_buffer_size=3)

        # Preenche o buffer até a capacidade máxima para simular saturação
        with service._lock:
            for i in range(1, 4):
                service._buffer.append(MetricRecord(name=f"item.{i}", value=i))
        assert service.pending_count == 3

        # Transbordo: item 1 deve ser descartado ao inserir o 4º item
        service.record_metric("item.4", 4)

        # O auto-flush despacha o lote restante sem o item descartado
        assert mock_exporter.export.call_count == 1
        dispatched_batch = mock_exporter.export.call_args[0][0]
        values = [rec.value for rec in dispatched_batch]
        assert values == [2, 3, 4]
        assert service.pending_count == 0

    def test_invalid_initialization_parameters(self, mock_exporter: MagicMock) -> None:
        with pytest.raises(ValueError, match="batch_size deve ser maior que zero"):
            TelemetryService(exporter=mock_exporter, batch_size=0)

        with pytest.raises(ValueError, match="max_buffer_size não pode ser menor que batch_size"):
            TelemetryService(exporter=mock_exporter, batch_size=100, max_buffer_size=50)


class TestTelemetryConcurrencyAndThreadSafety:
    """Testes de concorrência e thread-safety com escritas simultâneas."""

    def test_concurrent_writes_are_thread_safe_without_data_loss(self, mock_exporter: MagicMock) -> None:
        # Configura lote alto para acumular eventos em memória sem despacho prematuro
        service = TelemetryService(exporter=mock_exporter, batch_size=2000, max_buffer_size=2000)
        num_threads = 10
        events_per_thread = 100
        expected_total = num_threads * events_per_thread

        def worker(thread_id: int) -> None:
            for i in range(events_per_thread):
                service.record_metric(
                    name="concurrent.counter",
                    value=1,
                    tags={"thread": str(thread_id), "iteration": str(i)},
                )

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(worker, tid) for tid in range(num_threads)]
            concurrent.futures.wait(futures)

        assert service.pending_count == expected_total
        service.flush_and_close()

        assert mock_exporter.export.call_count == 1
        batch = mock_exporter.export.call_args[0][0]
        assert len(batch) == expected_total
        assert service.pending_count == 0
