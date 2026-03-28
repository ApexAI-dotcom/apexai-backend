import pytest
from unittest import mock
from fastapi.testclient import TestClient

# Mock settings BEFORE importing main to avoid side effects
import os
os.environ["MON_KART_ENABLED"] = "true"

from src.api.main import app

client = TestClient(app)

# Dummy dependencies
async def mock_get_current_user():
    return "test-user-id"

# Apply overrides
from src.api.auth import get_current_user
app.dependency_overrides[get_current_user] = mock_get_current_user

@pytest.fixture(autouse=True)
def mock_kart_service():
    with mock.patch("src.api.kart_routes.KartService") as MockService:
        MockService.is_racer_or_team.return_value = True
        MockService.get_or_create_kart_profile.return_value = {"user_id": "test-user-id", "mon_kart_enabled": True}
        MockService.get_sessions.return_value = []
        MockService.update_kart_profile.return_value = {"user_id": "test-user-id", "engine_hours_current": 5.0}
        MockService.reset_component.return_value = {"user_id": "test-user-id", "tires_sessions_current": 0}
        MockService.delete_session_and_recalculate.return_value = {"success": True, "profile": {}}
        yield MockService

def test_get_kart_profile():
    response = client.get("/api/kart/profile")
    assert response.status_code == 200
    data = response.json()
    assert "profile" in data
    assert "recent_sessions" in data
    assert data["profile"]["user_id"] == "test-user-id"

def test_put_kart_profile():
    response = client.put("/api/kart/profile", json={"engine_hours_current": 5.0})
    assert response.status_code == 200
    assert response.json()["profile"]["engine_hours_current"] == 5.0

def test_reset_component():
    response = client.post("/api/kart/component-reset", json={"component_type": "tires"})
    assert response.status_code == 200
    assert response.json()["profile"]["tires_sessions_current"] == 0

def test_delete_session():
    response = client.delete("/api/kart/session/test-sess-123")
    assert response.status_code == 200
    assert response.json()["success"] is True

def test_rookie_access_forbidden(mock_kart_service):
    # Simulate rookie user who cannot use mutations
    mock_kart_service.is_racer_or_team.return_value = False
    
    response = client.put("/api/kart/profile", json={"engine_hours_current": 5.0})
    assert response.status_code == 403

    response = client.post("/api/kart/component-reset", json={"component_type": "tires"})
    assert response.status_code == 403
    
    response = client.delete("/api/kart/session/test-sess-123")
    assert response.status_code == 403

@mock.patch("src.api.kart_routes.is_mon_kart_enabled")
def test_feature_flag_disabled(mock_is_enabled):
    mock_is_enabled.return_value = False
    
    response = client.get("/api/kart/profile")
    assert response.status_code == 404
