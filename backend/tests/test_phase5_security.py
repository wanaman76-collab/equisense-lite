"""Phase 5: security hardening tests.

Covers:
- Constant-time token comparison (_tokens_match)
- Security response headers on all responses
- Auth middleware: missing / invalid / valid token
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import _tokens_match, app

client = TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# _tokens_match helper
# ---------------------------------------------------------------------------


class TestTokensMatch:
    def test_matching_tokens_returns_true(self):
        assert _tokens_match("dev-token", "dev-token") is True

    def test_different_tokens_returns_false(self):
        assert _tokens_match("wrong-token", "dev-token") is False

    def test_empty_vs_nonempty_returns_false(self):
        assert _tokens_match("", "dev-token") is False

    def test_both_empty_returns_true(self):
        assert _tokens_match("", "") is True

    def test_partial_match_returns_false(self):
        assert _tokens_match("dev", "dev-token") is False


# ---------------------------------------------------------------------------
# Security response headers
# ---------------------------------------------------------------------------


class TestSecurityHeaders:
    def test_health_endpoint_has_security_headers(self):
        resp = client.get("/health")
        assert resp.headers.get("x-content-type-options") == "nosniff"
        assert resp.headers.get("x-frame-options") == "DENY"
        assert resp.headers.get("referrer-policy") == "strict-origin-when-cross-origin"

    def test_authenticated_endpoint_has_security_headers(self):
        resp = client.get("/sessions/", headers={"x-api-token": "dev-token"})
        assert resp.headers.get("x-content-type-options") == "nosniff"
        assert resp.headers.get("x-frame-options") == "DENY"
        assert resp.headers.get("referrer-policy") == "strict-origin-when-cross-origin"

    def test_unauthorised_response_has_security_headers(self):
        resp = client.get("/sessions/")
        assert resp.status_code == 401
        assert resp.headers.get("x-content-type-options") == "nosniff"


# ---------------------------------------------------------------------------
# Token auth middleware
# ---------------------------------------------------------------------------


class TestTokenAuthMiddleware:
    def test_missing_token_returns_401(self):
        resp = client.get("/sessions/")
        assert resp.status_code == 401
        assert "Missing" in resp.json()["detail"]

    def test_invalid_token_returns_401(self):
        resp = client.get("/sessions/", headers={"x-api-token": "wrong"})
        assert resp.status_code == 401
        assert "Invalid" in resp.json()["detail"]

    def test_valid_token_passes_through(self):
        resp = client.get("/sessions/", headers={"x-api-token": "dev-token"})
        assert resp.status_code == 200

    def test_options_preflight_bypasses_auth(self):
        resp = client.options("/sessions/")
        assert resp.status_code != 401

    def test_health_endpoint_bypasses_auth(self):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_docs_endpoint_bypasses_auth(self):
        resp = client.get("/docs")
        # 200 or redirect, never 401
        assert resp.status_code != 401
