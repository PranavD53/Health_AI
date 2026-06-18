# AI Healthcare Assistant Backend

A FastAPI-based backend for an AI-powered healthcare assistant with role-based access control, symptom analysis, appointment management, and AI chat capabilities.

## Features

- **Authentication & RBAC** – JWT-based auth with roles: `patient`, `doctor`, `caregiver`, `admin`
- **Patient Profiles** – Manage health baselines (age, weight, allergies, conditions)
- **Doctor Directory** – Browse and filter doctors by specialization
- **Appointment Booking** – Book, view, and cancel appointments
- **AI Symptom Assessment** – Groq-powered analysis with emergency detection
- **AI Chat Assistant** – Multi-turn medical conversations with safety filters
- **Medical Records** – Upload and manage personal health documents
- **Patient Dashboard** – Unified view of appointments, symptoms, records, and health tips
- **Audit Logs** – Admin-only trail of all system actions

## Tech Stack

- **Framework**: FastAPI
- **Database**: SQLite (via SQLAlchemy ORM)
- **Auth**: JWT (python-jose) + bcrypt
- **AI**: Groq API (llama-3.1-8b-instant)
- **HTTP Client**: httpx
- **Server**: Uvicorn

## Setup

### 1. Clone the repository
```bash
git clone https://github.com/sriramtumu2006/AI-Healthcare-Assistant.git
cd AI-Healthcare-Assistant
```

### 2. Create virtual environment & install dependencies
```bash
python -m venv venv
.\venv\Scripts\Activate.ps1      # Windows
source venv/bin/activate           # macOS/Linux

pip install -r requirements.txt
```

### 3. Configure environment variables
```bash
cp .env.example .env
# Edit .env and add your GROQ_API_KEY and SECRET_KEY
```

### 4. Run the development server
```bash
cd backend
uvicorn app.main:app --reload
```

API docs available at: http://127.0.0.1:8000/docs
Frontend available at: http://127.0.0.1:8000/

### 5. Run tests
```bash
python test_api.py
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/register` | Register a new user |
| POST | `/auth/login` | Login and receive JWT tokens |
| POST | `/auth/refresh` | Refresh access token |
| POST | `/auth/logout` | Logout current user |
| POST | `/profile` | Create patient profile |
| GET | `/profile` | Get current user's profile |
| PUT | `/profile` | Update patient profile |
| GET | `/doctors` | List doctors (filterable by specialization) |
| POST | `/appointment/book` | Book an appointment |
| GET | `/appointment/my-appointments` | View my appointments |
| DELETE | `/appointment/cancel/{id}` | Cancel an appointment |
| POST | `/symptom/analyze` | AI symptom analysis |
| GET | `/symptom/history` | View symptom history |
| POST | `/conversations` | Start a new AI chat thread |
| GET | `/conversations` | List all conversations |
| POST | `/conversations/{id}/messages` | Send a message |
| POST | `/records/upload` | Upload a medical record |
| GET | `/records` | List medical records |
| GET | `/dashboard` | Get patient dashboard |
| POST | `/ai/chat` | Quick ad-hoc AI chat |
| POST | `/ai/symptom-check` | Quick symptom check |
| POST | `/notifications/send` | Send a notification |
| GET | `/audit/logs` | View audit logs (admin only) |

## Environment Variables

| Variable | Description |
|----------|-------------|
| `GROQ_API_KEY` | Your Groq API key |
| `SECRET_KEY` | JWT signing secret |
| `DATABASE_URL` | SQLAlchemy DB URL (default: SQLite) |
| `ACCESS_TOKEN_EXPIRE_HOURS` | Token expiry in hours (default: 24) |
