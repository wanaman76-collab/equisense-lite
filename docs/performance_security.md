# Performance & Security Hardening — Operational Guide

This document covers the Phase 5 improvements: batch-query optimisation for the
compute pipeline and security hardening of the auth/middleware layer.

---

## Compute pipeline — batch-query optimisation

### What changed

Previously `run_compute()` issued **one SQL query per analysis window** to fetch
the sensor readings belonging to that window (N+1 pattern).  For a 10-minute
session at the default 50 Hz sample rate that produces ~60 windows and therefore
~60 individual DB round-trips.

The optimised implementation issues a **single query** that fetches all sensor
readings for the session at once, then slices the in-memory NumPy array per
window:

```
Before: 1 range query + N window queries  (N = number of 10s windows)
After:  1 range query + 1 bulk read       (constant, regardless of session length)
```

### Performance expectations

| Session length | Windows | Old queries | New queries |
|---|---|---|---|
| 1 min | ~6 | 8 | 2 |
| 10 min | ~60 | 62 | 2 |
| 1 hr | ~360 | 362 | 2 |

For long sessions and/or high-frequency hardware the speedup can be significant.

### Memory considerations

All readings are loaded into a NumPy array.  At 50 Hz with 7 columns (float64)
a 10-minute session is approximately:

```
50 Hz × 600 s × 7 columns × 8 bytes = ~1.7 MB
```

This is well within the acceptable range for typical sessions.  If sessions
routinely exceed 60 minutes consider streaming the reads or batching by time
slice.

### Rollback

The refactor is purely internal to `backend/app/services/compute.py`.  Reverting
the `run_compute` function to the previous per-window query loop restores the old
behaviour with no schema or API changes.

---

## Security hardening

### Constant-time token comparison

The `token_guard` middleware now uses `hmac.compare_digest` instead of the `==`
operator for comparing the provided token with the expected secret:

```python
# Before (timing leak)
if token != expected:
    ...

# After (constant-time)
if not hmac.compare_digest(token.encode(), expected.encode()):
    ...
```

`hmac.compare_digest` takes the same amount of time regardless of *where* the
two strings first differ, preventing timing-based token oracle attacks.

### Security response headers

All HTTP responses now carry the following headers:

| Header | Value | Purpose |
|---|---|---|
| `X-Content-Type-Options` | `nosniff` | Prevents MIME-type sniffing |
| `X-Frame-Options` | `DENY` | Prevents clickjacking |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Limits referrer leakage |

The `security_headers` middleware is registered **last** (outermost position),
ensuring these headers are present even on 401 / 403 error responses generated
by earlier middleware.

### Middleware ordering note

In FastAPI/Starlette, `@app.middleware("http")` decorators are applied **LIFO**
(last-registered = outermost wrapper).  The current order ensures:

```
Request → security_headers → token_guard → app routes
Response ← security_headers ← token_guard ← app routes
```

This guarantees that security headers are appended to every response, including
early-exit 401s from `token_guard`.

### API_TOKEN environment variable

The expected token is read from the `API_TOKEN` environment variable at runtime.
For production deployments:

* Set `API_TOKEN` to a long random string (32+ characters).
* Never commit the value to source control.
* Rotate the token by updating the environment variable and redeploying; existing
  client sessions will need to refresh their stored token.

```bash
# Example: generate a strong token
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### Future auth roadmap (out of scope for Phase 5)

The current architecture uses a single shared static token — suitable for a
personal/prototype use-case.  For multi-user or production SaaS scenarios
consider:

1. **Per-user JWT tokens** — issue short-lived JWTs signed with a secret or RSA
   key; validate on every request without a DB lookup.
2. **Token rotation / refresh** — issue short-lived access tokens + long-lived
   refresh tokens; revoke on breach without forcing a full redeployment.
3. **OAuth 2.0 / OIDC** — delegate authentication to an identity provider
   (Auth0, Cognito, Supabase Auth) and focus your backend on authorisation.

---

## Running the full quality gate locally

```bash
# Backend
make backend-check          # ruff + black
make backend-test           # pytest

# Frontend
make frontend-test          # vitest
make frontend-build         # vite build + tsc
```
