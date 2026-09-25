"""
============================================================
ORÁCULO - Guardian SRE Watchdog Tests (TDD)
============================================================
"""

import pytest
from orchestration.guardian import guardian, Incident

def test_guardian_initial_state():
    status = guardian.get_status()
    assert "status" in status
    assert "health_score" in status
    assert status["health_score"] >= 80.0

def test_guardian_sqlite_check():
    res = guardian.check_sqlite_health()
    assert res["healthy"] is True

def test_guardian_incident_logging():
    incident_id = guardian.log_incident(
        component="TestComponent",
        severity="WARNING",
        error_type="TEST_ERROR",
        message="Teste unitário de incidente",
        requires_human=False
    )
    assert incident_id > 0

    incidents = guardian.get_recent_incidents(limit=5)
    test_inc = next((inc for inc in incidents if inc["id"] == incident_id), None)
    assert test_inc is not None
    assert test_inc["component"] == "TestComponent"

    guardian.resolve_incident(incident_id, "Resolvido via teste unitário")
    incidents_updated = guardian.get_recent_incidents(limit=5)
    test_inc_updated = next((inc for inc in incidents_updated if inc["id"] == incident_id), None)
    assert test_inc_updated["resolution_status"] == "AUTO_RESOLVED"
