# EquiSense Lite

EquiSense Lite is a lightweight prototype for recording equine IMU sessions and producing basic anomaly analytics.

## Stack
- Backend: FastAPI + SQLAlchemy (SQLite in dev, PostgreSQL in production)
- Frontend: React (Vite)

---

## Local Development

### Prerequisites
- Python 3.10+
- Node.js 18+

### Backend

**macOS / Linux (bash):**
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

**Windows (PowerShell):**
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`.  
Swagger docs: `http://localhost:8000/docs`

The default API token for local dev is `dev-token` (set via `API_TOKEN` env var, defaults to `dev-token`).

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
