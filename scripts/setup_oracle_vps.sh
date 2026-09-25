#!/usr/bin/env bash
# ==============================================================================
# 🔮 ORÁCULO - Script Automatizado de Provisionamento para Oracle Cloud (OCI)
# Suporta: Ubuntu 22.04 / 24.04 LTS (x86_64 e aarch64 / ARM Ampere A1)
# ==============================================================================
set -e

echo "=============================================================="
echo "🔮 Iniciando provisionamento do Oráculo na Oracle Cloud..."
echo "=============================================================="

# 1. Atualização do Sistema
echo "📦 Atualizando repositórios do sistema..."
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y curl git ufw iptables-persistent netfilter-persistent ffmpeg

# 2. Configuração Crítica de Firewall da Oracle Cloud
# AVISO: Por padrão, a Oracle Cloud bloqueia portas HTTP/HTTPS via iptables local
echo "🛡️ Configurando regras de firewall local para Oracle Cloud (Portas 80, 443, 8000)..."
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 8000 -j ACCEPT
sudo netfilter-persistent save

# 3. Instalação do Docker e Docker Compose (se não instalados)
if ! command -v docker &> /dev/null; then
    echo "🐳 Instalando Docker Engine oficial..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    rm get-docker.sh
    sudo usermod -aG docker $USER
    echo "✅ Docker instalado com sucesso."
else
    echo "✅ Docker já está instalado."
fi

# 4. Criação do arquivo .env a partir de exemplo caso não exista
if [ ! -f .env ]; then
    echo "📝 Criando arquivo .env padrão..."
    cat << 'EOF' > .env
ENVIRONMENT=production
DATA_DIR=data
MAX_STUDY_WORKERS=8
TELEGRAM_TARGET_FOLDER=Estudos
VIDEO_RETENTION_HOURS=24
# Preencha suas chaves abaixo:
TELEGRAM_API_ID=
TELEGRAM_API_HASH=
GEMINI_API_KEY=
GEMINI_API_KEYS=
EOF
    echo "⚠️ Por favor, edite o arquivo .env (nano .env) e insira suas credenciais."
fi

# 5. Build e Inicialização dos Containers
echo "🚀 Construindo e subindo os containers com Docker Compose..."
sudo docker compose build
sudo docker compose up -d

echo "=============================================================="
echo "🎉 Oráculo instalado e rodando na Oracle Cloud!"
echo "📍 Dashboard Web: http://$(curl -s ifconfig.me):8000"
echo "📍 Endpoint MCP:  http://$(curl -s ifconfig.me):8000/mcp/sse"
echo "=============================================================="
