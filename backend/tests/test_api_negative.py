import pytest

@pytest.mark.parametrize("token,expected_status", [
    (None, 401),  # No token provided
    ("invalid_token", 401),  # Invalid token
])
def test_token_auth(client, token, expected_status):
    response = client.get("/api/some_endpoint", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == expected_status


def test_validation_errors(client):
    response = client.post("/api/some_endpoint", json={})  # Missing required fields
    assert response.status_code == 422  # Unprocessable Entity
    assert "error" in response.json()


def test_invalid_session_features(client):
    response = client.get("/api/features", headers={"Authorization": "Bearer valid_token"}, params={"session_id": "invalid_session"})
    assert response.status_code == 200
    assert response.json() == []  # Expecting empty list for invalid session


def test_invalid_session_anomalies(client):
    response = client.get("/api/anomalies", headers={"Authorization": "Bearer valid_token"}, params={"session_id": "invalid_session"})
    assert response.status_code == 200
    assert response.json() == []  # Expecting empty list for invalid session


def test_ingest_invalid_session(client):
    response = client.post("/api/ingest", json={"session_id": "invalid_session"})
    assert response.status_code == 404  # Not Found


def test_compute_no_readings(client):
    response = client.post("/api/compute", json={"session_id": "valid_session"})
    assert response.status_code == 400  # Bad Request
    assert response.json() == {"error": "No readings available"}

