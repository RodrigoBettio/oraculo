# ============================================================
# ORÁCULO - Dockerfile
# ============================================================
FROM python:3.13-slim AS base

# Instala dependências do sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instala dependências Python (camada cacheada)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia código da aplicação
COPY config.py main.py ./
COPY models/ models/
COPY ingestion/ ingestion/
COPY utils/ utils/
COPY web/ web/
COPY scripts/ scripts/
COPY orchestration/ orchestration/
COPY oraculo_mcp/ oraculo_mcp/

# Garante diretórios de dados (volumes são montados por cima)
RUN mkdir -p data/agents data/areas data/skills data/processed data/videos data/temp data/workspaces credentials

# Porta da aplicação
EXPOSE 8000

# Health check integrado ao Docker
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Entrypoint com script de inicialização
COPY scripts/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "web.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
