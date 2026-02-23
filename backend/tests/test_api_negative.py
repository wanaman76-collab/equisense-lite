import pytest
from fastapi.testclient import TestClient
from your_app import app  # Adjust the import according to your app structure

client = TestClient(app)

API_TOKEN = "your_api_token"

# Using X-API-Token for authentication
headers = {"X-API-Token": API_TOKEN}

# Test /health endpoint

def test_health():
    response = client.get("/health", headers=headers)
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

# Test /sessions endpoint

def test_sessions():
    response = client.get("/sessions", headers=headers)
    assert response.status_code == 200

# Test /ingest endpoint

def test_ingest():
    data = {"session_data": "data_here"}
    response = client.post("/ingest", headers=headers, json=data)
    assert response.status_code == 201

# Test /sessions/999999/features endpoint

def test_session_features():
    response = client.get("/sessions/999999/features", headers=headers)
    assert response.status_code == 200

# Test /sessions/999999/anomalies endpoint

def test_session_anomalies():
    response = client.get("/sessions/999999/anomalies", headers=headers)
    assert response.status_code == 200
