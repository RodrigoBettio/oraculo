from __future__ import annotations

import logging
from unittest.mock import MagicMock
import pytest

from src.telemetry.client import TelemetryClient
from src.telemetry.models import TelemetryEvent
from src.telemetry.transport import NetworkException, TelemetryTransport, TelemetryTransportError


@pytest.fixture
def mock_transport() -> MagicMock:
    transport = MagicMock(spec=TelemetryTransport)
    transport.send_batch.return_value = None
    return transport


@pytest.fixture
def test_logger() -> logging.Logger:
    log = logging.getLogger("test.telemetry")
    log.setLevel(logging.DEBUG)
    return log


def test_event_model_serialization():
    event = TelemetryEvent(
        name="order_placed",
        properties={"order_id": "12345"},
        metrics={"amount": 99.5},
        context={"env": "production"},
    )
    data = event.to_dict()

    assert data["name"] == "order_placed"
    assert data["properties"] == {"order_id": "12345"}
    assert data["metrics"] == {"amount": 99.5}
    assert data["context"] == {"env": "production"}
    assert isinstance(data["event_id"], str) and len(data["event_id"]) > 0
    assert isinstance(data["timestamp"], str) and "T" in data["timestamp"]


def test_telemetry_client_initialization_invalid_buffer():
    transport = MagicMock(spec=TelemetryTransport)
    with pytest.raises(ValueError, match="buffer_size deve ser maior que zero"):
        TelemetryClient(transport=transport, buffer_size=0)


def test_track_event_formatting_and_context_injection(mock_transport: MagicMock):
    """Cenário: Registro e formatação bem-sucedida de evento de telemetria"""
    default_context = {"service": "order_service", "region": "sa-east-1"}
    client = TelemetryClient(
        transport=mock_transport,
        buffer_size=5,
        default_context=default_context,
    )

    success = client.track_event(
        name="item_added",
        properties={"sku": "ABC-999"},
        metrics={"quantity": 2, "invalid_metric": "not_a_number"},  # type: ignore
        context={"user_id": "user_01"},
    )

    assert success is True
    assert client.total_events_tracked == 1
    assert client.buffered_count == 1
    assert mock_transport.send_batch.call_count == 0

    # Inspeciona o evento no buffer interno
    buffered_event = client._buffer[0]
    assert buffered_event.name == "item_added"
    assert buffered_event.properties == {"sku": "ABC-999"}
    assert buffered_event.metrics == {"quantity": 2.0}
    assert buffered_event.context == {
        "service": "order_service",
        "region": "sa-east-1",
        "user_id": "user_01",
    }


@pytest.mark.parametrize(
    "invalid_name",
    [None, "", "   ", 12345],
)
def test_track_event_invalid_name(mock_transport: MagicMock, invalid_name: any):
    client = TelemetryClient(transport=mock_transport, buffer_size=3)
    result = client.track_event(name=invalid_name)  # type: ignore

    assert result is False
    assert client.total_events_tracked == 0
    assert client.buffered_count == 0


def test_automatic_flush_when_buffer_threshold_reached(mock_transport: MagicMock):
    """Cenário: Disparo automático de flush por limite de buffer"""
    buffer_limit = 3
    client = TelemetryClient(transport=mock_transport, buffer_size=buffer_limit)

    client.track_event(name="ev_1")
    assert client.buffered_count == 1
    assert mock_transport.send_batch.call_count == 0

    client.track_event(name="ev_2")
    assert client.buffered_count == 2
    assert mock_transport.send_batch.call_count == 0

    client.track_event(name="ev_3")
    # Limiar atingido: flush automático e esvaziamento determinístico
    assert client.buffered_count == 0
    assert client.total_events_tracked == 3
    assert client.total_events_sent == 3
    assert mock_transport.send_batch.call_count == 1

    # Valida que o lote continha os 3 eventos na ordem de inserção
    dispatched_batch: list[TelemetryEvent] = mock_transport.send_batch.call_args[0][0]
    assert len(dispatched_batch) == 3
    assert [e.name for e in dispatched_batch] == ["ev_1", "ev_2", "ev_3"]


@pytest.mark.parametrize(
    "error_instance",
    [
        TimeoutError("Conexão expirou após 5000ms"),
        NetworkException("Falha ao resolver DNS do endpoint de telemetria"),
        TelemetryTransportError("Erro 503 Service Unavailable"),
        RuntimeError("Falha genérica inesperada no driver de transporte"),
    ],
)
def test_failsafe_handling_on_transport_failure(mock_transport: MagicMock, error_instance: Exception):
    """Cenário: Tratamento de timeout e isolamento de falha de conexão"""
    mock_transport.send_batch.side_effect = error_instance
    client = TelemetryClient(transport=mock_transport, buffer_size=2)

    # Disparo ocorre no 2º evento
    client.track_event(name="ev_fail_1")
    result = client.track_event(name="ev_fail_2")

    # Garante que a exceção não sobe para a pilha de negócio
    assert result is True
    assert client.total_events_tracked == 2
    assert client.total_events_sent == 0
    assert client.total_failed_dispatches == 1
    assert client.buffered_count == 0  # Buffer esvaziado para não reter memória excessiva


def test_manual_flush_empty_buffer(mock_transport: MagicMock):
    client = TelemetryClient(transport=mock_transport, buffer_size=5)
    result = client.flush()

    assert result is True
    assert mock_transport.send_batch.call_count == 0


def test_close_flushes_remaining_events(mock_transport: MagicMock):
    client = TelemetryClient(transport=mock_transport, buffer_size=10)
    client.track_event(name="checkout_started")
    assert client.buffered_count == 1

    client.close()
    assert client.buffered_count == 0
    assert client.total_events_sent == 1
    assert mock_transport.send_batch.call_count == 1


def test_track_event_failsafe_on_unexpected_internal_exception(mock_transport: MagicMock, monkeypatch: pytest.MonkeyPatch):
    client = TelemetryClient(transport=mock_transport, buffer_size=5)

    # Simula erro não previsto dentro da execução de track_event
    def mock_broken_event(*args, **kwargs):
        raise MemoryError("Simulação de pane crítica no runtime")

    monkeypatch.setattr("src.telemetry.client.TelemetryEvent", mock_broken_event)

    # Operação não estoura MemoryError para a aplicação
    success = client.track_event(name="critical_operation")
    assert success is False
