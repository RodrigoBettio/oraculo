#!/bin/bash
# ============================================================
# ORÁCULO - Script de Deploy Automatizado para Ubuntu 24.04 LTS
# ============================================================
set -e

echo "🚀 Iniciando deploy do Oráculo no Google Compute Engine..."

# 1. Atualizar pacotes do sistema
echo "📦 Atualizando pacotes do sistema..."
sudo apt-get update -y
sudo apt-get install -y curl git ufw

# 2. Instalar Docker se não existir
if ! command -v docker &> /dev/null; then
    echo "🐳 Instalando Docker oficial..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    rm -f get-docker.sh
    echo "✅ Docker instalado com sucesso."
else
    echo "✅ Docker já está instalado."
fi

# 3. Configurar Firewall (UFW)
echo "🛡️ Configurando Firewall..."
sudo ufw allow 22/tcp comment 'SSH' || true
sudo ufw allow 80/tcp comment 'HTTP' || true
sudo ufw allow 443/tcp comment 'HTTPS' || true
sudo ufw allow 8000/tcp comment 'Oráculo App' || true
sudo ufw --force enable || true

# 4. Criar diretórios de persistência
echo "📂 Preparando diretórios de dados..."
mkdir -p data/agents data/areas data/skills data/processed data/videos data/temp credentials

# 5. Build e Inicialização via Docker Compose
echo "🏗️ Construindo containers e iniciando serviços..."
sudo docker compose down || true
sudo docker compose build --no-cache
sudo docker compose up -d

# 6. Aguardar inicialização e testar Health Check
echo "⏳ Aguardando inicialização da aplicação..."
sleep 8

HEALTH_STATUS=$(curl -s http://localhost:8000/health || echo "FAILED")
echo "🔍 Health Check: $HEALTH_STATUS"

GUARDIAN_STATUS=$(curl -s http://localhost:8000/api/guardian/status || echo "FAILED")
echo "🛡️ Guardian SRE Status: $GUARDIAN_STATUS"

echo "============================================================"
echo "🎉 DEPLOY CONCLUÍDO COM SUCESSO!"
echo "Acesse o painel pelo IP externo da VM:"
echo "👉 http://$(curl -s ifconfig.me):8000"
echo "============================================================"
