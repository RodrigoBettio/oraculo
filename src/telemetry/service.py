from collections import deque
import logging
import threading
from typing import Mapping, Optional, Sequence, Union

from src.telemetry.exporter import TelemetryExporter
from src.telemetry.models import MetricRecord, MetricType, TagValue

logger = logging.getLogger(__name__)


class TelemetryService:
    """Serviço de telemetria thread-safe e tolerante a falhas (fail-safe).

    Gerencia bufferização em memória, despacho em lote e encerramento gracioso,
    garantindo isolamento total das regras de negócio contra falhas na observabilidade.
    """

    def __init__(
        self,
        exporter: TelemetryExporter,
        batch_size: int = 100,
        max_buffer_size: int = 10_000,
    ) -> None:
        if batch_size <= 0:
            raise ValueError("batch_size deve ser maior que zero")
        if max_buffer_size < batch_size:
            raise ValueError("max_buffer_size não pode ser menor que batch_size")

        self._exporter = exporter
        self._batch_size = batch_size
        self._max_buffer_size = max_buffer_size

        self._buffer: deque[MetricRecord] = deque()
        self._lock = threading.RLock()
        self._is_shutdown = False

    @property
    def is_shutdown(self) -> bool:
        with self._lock:
            return self._is_shutdown

    @property
    def pending_count(self) -> int:
        with self._lock:
            return len(self._buffer)

    def record_metric(
        self,
        name: str,
        value: Union[int, float],
        metric_type: MetricType = MetricType.COUNTER,
        tags: Optional[Mapping[str, TagValue]] = None,
    ) -> bool:
        """Registra uma métrica de forma não-bloqueante e resiliente.

        Nunca propaga exceções para o chamador da aplicação.
        """
        try:
            if not name or not isinstance(name, str):
                logger.debug("Nome de métrica inválido fornecido: %s", name)
                return False

            if not isinstance(value, (int, float)) or isinstance(value, bool):
                logger.debug("Valor numérico inválido para a métrica %s: %s", name, value)
                return False

            clean_attributes: dict[str, TagValue] = {}
            if tags is not None:
                for k, v in tags.items():
                    if isinstance(k, str) and isinstance(v, (str, int, float, bool)):
                        clean_attributes[k] = v

            record = MetricRecord(
                name=name,
                value=value,
                metric_type=metric_type,
                attributes=clean_attributes,
            )

            batch_to_export: list[MetricRecord] = []
            with self._lock:
                if self._is_shutdown:
                    logger.debug("TelemetryService encerrado. Descartando métrica: %s", name)
                    return False

                if len(self._buffer) >= self._max_buffer_size:
                    # Descarta o item mais antigo em caso de buffer transbordado (backpressure simples)
                    self._buffer.popleft()
                    logger.debug("Buffer cheio atingido (%d). Evento descartado.", self._max_buffer_size)

                self._buffer.append(record)

                if len(self._buffer) >= self._batch_size:
                    for _ in range(self._batch_size):
                        batch_to_export.append(self._buffer.popleft())

            if batch_to_export:
                self._dispatch(batch_to_export)

            return True
        except Exception as exc:
            logger.debug("Erro não tratado interceptado em record_metric: %s", exc, exc_info=True)
            return False

    def flush(self) -> int:
        """Drena imediatamente todos os itens acumulados no buffer em memória."""
        to_export: list[MetricRecord] = []
        with self._lock:
            while self._buffer:
                to_export.append(self._buffer.popleft())

        if not to_export:
            return 0

        self._dispatch(to_export)
        return len(to_export)

    def flush_and_close(self, timeout: float = 5.0) -> None:
        """Esvazia o buffer residual e finaliza o exportador graciosamente."""
        with self._lock:
            if self._is_shutdown:
                return
            self._is_shutdown = True

        try:
            self.flush()
        except Exception as exc:
            logger.debug("Exceção capturada durante flush no shutdown: %s", exc)

        try:
            self._exporter.shutdown()
        except Exception as exc:
            logger.debug("Exceção capturada durante shutdown do exporter: %s", exc)

    def _dispatch(self, batch: Sequence[MetricRecord]) -> bool:
        """Executa envio seguro ao exportador, isolando falhas de rede ou timeout."""
        if not batch:
            return True
        try:
            return self._exporter.export(batch)
        except Exception as exc:
            logger.debug("Falha no pipeline de transporte ao exportar lote: %s: %s", type(exc).__name__, exc)
            return False
