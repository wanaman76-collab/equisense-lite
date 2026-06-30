# EquiSense Lite

EquiSense Lite is a lightweight prototype for recording equine IMU sessions and producing basic anomaly analytics.

## Stack
- Backend: FastAPI + SQLAlchemy (SQLite in dev, PostgreSQL in production) · Python 3.12
- Frontend: React (Vite) · TypeScript

---

## Developer Quick-Start (Makefile)

> Requires `make` (pre-installed on macOS/Linux; Windows: use WSL or Git Bash).

```bash
make backend-install   # install Python deps
make backend-check     # lint (ruff) + format-check (black) + tests
make frontend-install  # npm ci
make frontend-test     # vitest
make dev-backend       # uvicorn --reload
make dev-frontend      # vite dev server
```

Run `make help` to see all available targets.

---

## Execution Instructions (Deployed System)

### Deployed links
- Backend API (Render): https://equisense-lite-api-docker.onrender.com  
- Web dashboard (Netlify): https://equisense-lite.netlify.app/  

### Quick check (backend is live)
Open:
- https://equisense-lite-api-docker.onrender.com/health

Expected response:
- `{"status":"ok"}`

> Note: Render services may take ~30–60 seconds to wake up if idle. Refresh if needed.

### How to use (end-to-end)
1. **Run the iOS app** (see “iOS App — EquiSenseLiteRecorder” section below).
2. In iOS **Settings**, set:
   - API Base URL: `https://equisense-lite-api-docker.onrender.com`
   - API Token: use the token configured in Render (provided separately for assessment).
3. Create/select a horse (example used in testing: **Amira**).
4. Create a session (note the `session_id`).
5. Record ~60 seconds (targets ~50 Hz).
6. Upload.
7. Compute.
8. View the report in iOS and/or on the web dashboard.

If the dashboard is empty, refresh the sessions list after creating a session via iOS.

---

## Local Development

### Prerequisites
- Python 3.12+
- Node.js 18+

### Backend

**macOS / Linux (bash):**
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

**Windows (PowerShell):**
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`.  
Swagger docs: `http://localhost:8000/docs`

The default API token for local dev is `dev-token` (set via `API_TOKEN` env var, defaults to `dev-token`).

> **Migrations:** Schema is managed by Alembic. Run `alembic upgrade head` before starting the server.
> See [docs/migrations.md](docs/migrations.md) for details.

### Frontend

**macOS / Linux / Windows:**
```bash
cd frontend
npm install
npm run dev
```

The app will open at `http://localhost:5173`.

> **Note:** Set `VITE_API_URL` to point at your backend if it is not on `http://localhost:8000`.

### Docker Compose (both services)

```bash
docker-compose up --build
```

---

## Running Backend Tests

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -r requirements-dev.txt
pytest tests/ -v
```

---

## iOS App — EquiSenseLiteRecorder

A native SwiftUI iPhone app for recording horse-mounted IMU data (accelerometer + gyroscope at 50 Hz) and uploading it to the EquiSense Lite backend.

### Location

```
ios/EquiSenseLiteRecorder/EquiSenseLiteRecorder.xcodeproj
```

### Requirements

- macOS with **Xcode 15+** (free from the Mac App Store)
- An iPhone running **iOS 16+**
- A running EquiSense Lite backend (local or Render)

### Build & Run (Xcode, no App Store needed)

1. Open the project in Xcode:
   ```bash
   open ios/EquiSenseLiteRecorder/EquiSenseLiteRecorder.xcodeproj
   ```

2. Connect your iPhone via USB (or use the Simulator for UI testing — CoreMotion will not produce real data in the Simulator).

3. In Xcode, select your iPhone as the run destination, then press **▶ Run** (⌘R).

4. The first time you run on a physical device, go to **Settings → General → VPN & Device Management** on the iPhone and trust your developer certificate.

### Required iOS Permissions

The following key is declared in `Info.plist` and will trigger a system permission prompt on first motion access:

| Key | Purpose |
|-----|---------|
| `NSMotionUsageDescription` | Allows the app to access accelerometer & gyroscope data via CoreMotion |

No additional entitlements or provisioning profiles are needed for personal/development use with automatic signing.

### App Flow

1. **Settings tab** — Enter your backend API Base URL (e.g., `https://your-app.onrender.com`) and API Token. Both are saved in `UserDefaults`.
2. **Horse & Session tab** — Create a new horse or pick an existing one, then tap **Start Session**.
3. **Recording tab** — Tap **Start Recording** to begin 50 Hz IMU capture. Elapsed time and sample count are shown live. Tap **Stop Recording** to end; samples are saved to a local JSON Lines file in the app's Documents directory.
4. **Upload tab** — Tap **Upload to Server** to batch-upload samples (200/batch with up to 3 retries per batch). After a successful upload, tap **Compute Analysis** to trigger anomaly detection on the backend.

### Notes

- Sampling rate: **50 Hz** (using `CMMotionManager.deviceMotionUpdateInterval = 1/50`).
- Timestamps: epoch-ms anchored at session start, offset by CoreMotion uptime for monotonic ordering.
- Offline-first: data is stored locally during recording and uploaded after stop.
- The app handles **409 Duplicate** responses from the backend gracefully (treated as success).
- **Live feed**: while recording is active, the app streams small sample batches every ~200 ms to the backend via `POST /sessions/{id}/live-ingest`. This feed is visible in real time on the Mac dashboard (see *Live Feed* section below).

---

## Live Feed — iPhone → Backend → Mac Dashboard

Phase 6 adds real-time streaming from the iOS recorder to the Mac web dashboard.

### How it works

```
iPhone (recording)
  └─→ POST /sessions/{id}/live-ingest  (every ~200 ms)
        └─→ FastAPI live hub
              └─→ WS broadcast → Mac browser
                    └─→ LiveFeedPanel (rolling chart)
```

### Quick start (local LAN)

1. **Start the backend** on your Mac:
   ```bash
   make dev-backend        # starts uvicorn on 0.0.0.0:8000
   ```

2. **Find your Mac's LAN IP** (not `localhost`!):
   ```bash
   ipconfig getifaddr en0   # Wi-Fi
   # example: 192.168.1.42
   ```

3. **Configure the iOS app** → Settings tab:
   - **API Base URL**: `http://192.168.1.42:8000`  *(use your Mac's actual LAN IP)*
   - **API Token**: `dev-token` (or your configured `API_TOKEN`)

4. **Open the Mac dashboard** at `http://localhost:5173` (or wherever `make dev-frontend` is running). Make sure the same token is entered in the Token field.

5. **Create a session** on iOS (Horse & Session tab) — note the session ID.

6. **Start recording** on iOS. The *Live Feed* panel on the Mac dashboard will appear automatically for the active session and show rolling accel/gyro charts within ~1 second.

7. **Stop recording** on iOS to end the live feed. The final upload and compute run automatically.

### Troubleshooting

| Problem | Fix |
|---------|-----|
| Live feed panel shows "Disconnected — retrying…" | Check that the Mac IP is reachable from the phone (same Wi-Fi) |
| iOS app can't reach backend | Use LAN IP (e.g. `192.168.x.x`), not `localhost` — `localhost` from the phone resolves to the phone itself |
| Firewall blocking connection | Allow incoming on port 8000 in macOS System Settings → Network → Firewall options |
| wss:// vs ws:// | For local LAN dev use `http://` base URL — the live WS uses `ws://`. For production (Render) the frontend will upgrade to `wss://` automatically via the `VITE_API_URL` env var |
| Panel doesn't appear | A session must be active (started via "Start" button or iOS). The panel is only shown while `sessionId` is set |

---

## Deployment

### Backend → Render (free tier)

1. Push the repo to GitHub and connect it to [Render](https://render.com).
2. Create a **Web Service**, set:
   - **Root directory:** `backend`
   - **Runtime:** Python 3
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
3. Add environment variables in the Render dashboard:
   | Key | Value |
   |-----|-------|
   | `API_TOKEN` | your secret token |
   | `DATABASE_URL` | postgres connection string (attach a Render Postgres DB) |

### Frontend → Netlify

1. Connect your GitHub repo to [Netlify](https://netlify.com).
2. Set the build settings:
   - **Base directory:** `frontend`
   - **Build command:** `npm run build`
   - **Publish directory:** `frontend/dist`
3. Add environment variable in the Netlify dashboard:
   | Key | Value |
   |-----|-------|
   | `VITE_API_URL` | `https://your-render-backend.onrender.com` |
