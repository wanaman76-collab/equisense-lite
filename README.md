# EquiSense Lite

EquiSense Lite is a lightweight prototype for recording equine IMU sessions and producing basic anomaly analytics.

## Stack
- Backend: FastAPI + SQLAlchemy
- Database: PostgreSQL (local via docker-compose) or SQLite (dev)
- Frontend: React (Vite)

## Quickstart (dev)

### Backend
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

### Docker
```bash
docker-compose up --build
```