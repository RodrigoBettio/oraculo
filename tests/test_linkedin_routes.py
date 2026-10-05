"""
Testes automatizados da API do LinkedIn Smart Copilot.
"""

from fastapi.testclient import TestClient
from web.app import app

client = TestClient(app)


def test_smart_message_generation():
    """Testa geração de mensagem contextual e humana para um perfil."""
    payload = {
        "full_name": "Juliana Ferreira",
        "headline": "Product Manager na FinTech X"
    }
    resp = client.post("/api/linkedin/smart-message", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["first_name"] == "Juliana"
    assert "message" in data
    assert len(data["message"]) > 20
    assert "Juliana" in data["message"]
