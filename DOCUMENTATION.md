# TARS Next-Gen AI Healthcare Assistant — Complete Documentation

> **Version:** 1.0.0  
> **Last Updated:** August 2026  
> **Repository:** `Health_AI`  

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture Overview](#2-architecture-overview)
3. [Technology Stack](#3-technology-stack)
4. [Project Structure](#4-project-structure)
5. [Backend Documentation](#5-backend-documentation)
   - 5.1 [Database Schema](#51-database-schema)
   - 5.2 [Authentication & Authorization](#52-authentication--authorization)
   - 5.3 [API Endpoints](#53-api-endpoints)
   - 5.4 [Services](#54-services)
   - 5.5 [WebSocket](#55-websocket)
6. [Frontend Documentation](#6-frontend-documentation)
   - 6.1 [Component Architecture](#61-component-architecture)
   - 6.2 [Routing](#62-routing)
   - 6.3 [State Management](#63-state-management)
7. [Setup & Installation](#7-setup--installation)
8. [Environment Variables](#8-environment-variables)
9. [Testing](#9-testing)
10. [Deployment](#10-deployment)
11. [Key Features Deep Dive](#11-key-features-deep-dive)
12. [Troubleshooting](#12-troubleshooting)

---

## 1. Project Overview

**TARS Next-Gen AI Healthcare Assistant** is a secure, next-generation AI-powered healthcare platform combining real-time voice assistance, YOLO-based computer vision diagnostics, automated clinical workflows, and emergency SOS services.

### Core Capabilities

| Capability | Description |
|------------|-------------|
| **TARS Voice Assistant** | Wake-word detection ("Hey TARS"), ultra-low latency STT via Groq Whisper, voice-native dashboard actions |
| **AI Diagnostics** | Medical imaging analysis for skin conditions, chest X-rays, and throat examinations |
| **Emergency SOS** | GPS-based alerts with 100km doctor notification radius using Haversine formula |
| **Clinical Workflows** | Doctor leave management, surgery reassignment, risk-prioritized consultations |
| **Video Consultations** | WebRTC-based video calls with LiveKit integration |
| **Multi-Language** | Dynamic translation of doctor profiles to Hindi and Telugu |

### User Roles

| Role | Description |
|------|-------------|
| `patient` | Book appointments, upload records, chat with AI, set medicine reminders, trigger SOS |
| `doctor` | Manage appointments, create prescriptions, update profiles, request leave, verify patients |
| `admin` | User management, doctor verification, audit logs, appointment oversight |
| `caregiver` | Assists patients with limited permissions |

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT LAYER                                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │   Landing   │  │  Dashboards │  │  Chat/Calls │  │  Imaging Diagnostics│ │
│  │   (React)   │  │   (React)   │  │  (WebRTC)   │  │   (File Upload)     │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────────┘ │
│                              React + Vite                                    │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼ HTTP / WebSocket
┌─────────────────────────────────────────────────────────────────────────────┐
│                              API LAYER                                       │
│                         FastAPI (Python 3.11+)                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │   Auth      │  │  Doctors    │  │ Appointments│  │  Medical Records    │ │
│  │   Router    │  │   Router    │  │   Router    │  │     Router          │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────────┘ │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │  Symptoms   │  │   Chats     │  │   Calls     │  │     Imaging         │ │
│  │   Router    │  │   Router    │  │   Router    │  │     Router          │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────────┘ │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │  Dashboard  │  │  Feedback   │  │  Palettes   │  │   Voice Socket      │ │
│  │   Router    │  │   Router    │  │   Router    │  │     (WebSocket)     │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼ SQLAlchemy
┌─────────────────────────────────────────────────────────────────────────────┐
│                            DATA LAYER                                        │
│  ┌─────────────────────────┐    ┌─────────────────────────────────────────┐ │
│  │  PostgreSQL (Supabase)  │    │  SQLite (Local Fallback / Testing)      │ │
│  │  - Production           │    │  - Development                          │ │
│  │  - Connection Pooling   │    │  - In-Memory Tests                      │ │
│  └─────────────────────────┘    └─────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼ External APIs
┌─────────────────────────────────────────────────────────────────────────────┐
│                         EXTERNAL SERVICES                                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │ Groq/Whisper│  │   Gemini    │  │    Brevo    │  │     LiveKit         │ │
│  │   (STT)     │  │   (LLM)     │  │   (Email)   │  │   (Video Calls)     │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────────┘ │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                         │
│  │Hugging Face │  │    Groq     │  │   faster_   │                         │
│  │   (LLM)     │  │   (LLM)     │  │  whisper    │                         │
│  └─────────────┘  └─────────────┘  └─────────────┘                         │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Technology Stack

### Backend

| Technology | Version | Purpose |
|------------|---------|---------|
| Python | 3.11+ | Runtime |
| FastAPI | Latest | Web framework |
| SQLAlchemy | Latest | ORM |
| PostgreSQL | 14+ | Production database |
| SQLite | 3.x | Local development / testing |
| Uvicorn | Latest | ASGI server |
| PyJWT (python-jose) | Latest | JWT token handling |
| bcrypt | Latest | Password hashing |
| httpx | Latest | HTTP client for external APIs |

### Frontend

| Technology | Version | Purpose |
|------------|---------|---------|
| React | 19.x | UI framework |
| Vite | 8.x | Build tool |
| Tailwind CSS | 4.x | Styling |
| React Router DOM | 7.x | Client-side routing |
| GSAP | 3.x | Animations |
| Lenis | 1.x | Smooth scrolling |
| Lucide React | 1.x | Icons |

### External APIs

| Service | Purpose |
|---------|---------|
| Groq Whisper API | Speech-to-text transcription |
| Gemini (Google) | LLM for AI chat & translations |
| Brevo (Sendinblue) | Transactional email & OTP |
| LiveKit | Video call infrastructure |
| Hugging Face | Fallback LLM & ML models |

---

## 4. Project Structure

```
Health_AI/
├── README.md                          # Original project README
├── package.json                       # Root-level npm config
│
├── backend/                           # FastAPI backend
│   ├── .env                           # Environment variables (not in git)
│   ├── .env.example                   # Environment template
│   ├── requirements.txt               # Python dependencies
│   ├── migrate.py                     # Database migration runner
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                    # FastAPI app entry point
│   │   ├── config.py                  # App configuration & system capabilities
│   │   ├── database.py                # DB engine, session, connection handling
│   │   ├── models.py                  # SQLAlchemy ORM models
│   │   ├── migrations.py              # Schema migration logic
│   │   ├── timezone_helper.py         # Timezone-aware datetime utilities
│   │   ├── websocket_manager.py       # WebSocket connection manager
│   │   ├── seed_guidelines.py         # Clinical guidelines seeding
│   │   ├── routes/                    # API route modules
│   │   │   ├── auth.py                # Authentication (login, register, OTP)
│   │   │   ├── profile.py             # User profile management
│   │   │   ├── symptoms.py            # Symptom logging & AI analysis
│   │   │   ├── doctors.py             # Doctor profiles, search, leave
│   │   │   ├── appointments.py        # Appointment booking & management
│   │   │   ├── records.py             # Medical records upload & fraud scan
│   │   │   ├── dashboard.py           # Dashboard data aggregation
│   │   │   ├── chats.py               # Private messaging
│   │   │   ├── calls.py               # Video call management
│   │   │   ├── feedback.py            # Patient feedback & ratings
│   │   │   ├── palettes.py            # User color theme preferences
│   │   │   ├── imaging.py             # Medical imaging diagnostics
│   │   │   └── voice_socket.py        # TARS voice WebSocket
│   │   └── services/                  # AI/ML service modules
│   │       ├── skin_ai.py             # Skin disease AI model
│   │       ├── xray_ai.py             # Chest X-ray AI model
│   │       └── throat_ai.py           # Throat analysis heuristics
│   ├── uploads/                       # Uploaded file storage
│   ├── test_images/                   # Test image fixtures
│   └── test_*.py                      # Test suites (pytest)
│
├── Frontend/                          # React frontend
│   ├── package.json                   # Frontend dependencies
│   ├── vite.config.js                 # Vite configuration
│   ├── tailwind.config.js             # Tailwind CSS configuration
│   ├── index.html                     # Entry HTML
│   └── src/
│       ├── main.jsx                   # React entry point
│       ├── App.jsx                    # Root component with routing
│       ├── App.css                    # Global app styles
│       ├── index.css                  # Tailwind directives + base styles
│       ├── assets/                    # Static images & assets
│       ├── components/                # Reusable components
│       │   ├── Layout.jsx             # Dashboard layout wrapper
│       │   ├── SideNavBar.jsx         # Sidebar navigation
│       │   ├── TopNavBar.jsx          # Top header bar
│       │   ├── GlobalAssistant.jsx    # TARS voice assistant widget
│       │   ├── ConstellationBackground.jsx
│       │   └── landing/               # Landing page sections
│       │       ├── AnimatedBackground.jsx
│       │       ├── HeroSection.jsx
│       │       ├── CapabilitiesSection.jsx
│       │       └── SlidingTextSection.jsx
│       ├── context/                   # React context providers
│       │   ├── AuthContext.jsx        # Authentication state
│       │   ├── ThemeContext.jsx       # Theme/color state
│       │   ├── LanguageContext.jsx    # i18n language state
│       │   ├── WebSocketContext.jsx   # WebSocket connection
│       │   └── CallContext.jsx        # Video call state
│       ├── pages/                     # Route-level page components
│       │   ├── Landing.jsx
│       │   ├── Login.jsx
│       │   ├── Register.jsx
│       │   ├── OtpVerify.jsx
│       │   ├── PatientDashboard.jsx
│       │   ├── DoctorDashboard.jsx
│       │   ├── AdminDashboard.jsx
│       │   ├── DoctorSearch.jsx
│       │   ├── MedicalRecords.jsx
│       │   ├── ImagingDiagnostics.jsx
│       │   ├── Chat.jsx
│       │   └── Settings.jsx
│       ├── services/
│       │   └── api.js                 # API service functions
│       └── utils/
│           ├── apiConfig.js           # API URL configuration
│           └── theme.js               # Theme utility functions
│
├── Frontend-Backup/                   # Legacy HTML prototype files
│   └── [various dashboard prototypes]
│
└── scratch/                           # Utility scripts
    ├── replace_tars.py
    └── webrtc_ice_fix.patch
```

---

## 5. Backend Documentation

### 5.1 Database Schema

#### Entity Relationship Diagram

```
┌─────────────┐       ┌─────────────────┐       ┌─────────────┐
│    users    │◄─────►│ patient_profiles│       │   doctors   │
├─────────────┤  1:1  ├─────────────────┤       ├─────────────┤
│ id (PK)     │       │ id (PK)         │       │ id (PK)     │
│ email (UQ)  │       │ user_id (FK,UQ) │       │ user_id(FK) │
│ password    │       │ name            │       │ name        │
│ role        │       │ date_of_birth   │       │specialization│
│ is_active   │       │ gender          │       │ location    │
│ otp         │       │ height          │       │ available   │
│ is_verified │       │ weight          │       │ contact     │
│ base_role   │       │ allergies       │       │ license_num │
│ created_at  │       │ address         │       │ latitude    │
└──────┬──────┘       └─────────────────┘       │ longitude   │
       │                                         └──────┬──────┘
       │ 1:N                                              │ 1:N
       ▼                                                  ▼
┌─────────────┐       ┌─────────────┐       ┌─────────────────────┐
│conversations│       │ symptom_logs│       │   appointments      │
├─────────────┤       ├─────────────┤       ├─────────────────────┤
│ id (PK)     │       │ id (PK)     │       │ id (PK)             │
│ user_id(FK) │       │ user_id(FK) │       │ patient_id (FK)     │
│ title       │       │ symptoms    │       │ doctor_id (FK)      │
│ created_at  │       │ severity    │       │ date                │
└──────┬──────┘       │ duration    │       │ time                │
       │ 1:N          │ risk_category│      │ status              │
       ▼              │ created_at  │       │ priority            │
┌─────────────┐       └─────────────┘       │ created_at          │
│  messages   │                             └─────────────────────┘
├─────────────┤
│ id (PK)     │
│ conv_id(FK) │
│ role        │
│ content     │
│ timestamp   │
└─────────────┘
```

#### Complete Schema

| Table | Description |
|-------|-------------|
| `users` | Core user accounts with role-based access |
| `patient_profiles` | Extended patient demographic data |
| `doctors` | Doctor profiles with location & verification |
| `doctor_verifications` | KYC verification status for doctors |
| `conversations` | AI chat conversation threads |
| `messages` | Individual messages within conversations |
| `symptom_logs` | Patient symptom submissions with severity |
| `appointments` | Doctor-patient appointment bookings |
| `medical_records` | Uploaded files with anti-fraud status |
| `medical_imaging_diagnostics` | AI-generated imaging analysis reports |
| `patient_metrics` | Health metrics (heart rate, sleep, steps) |
| `emergency_alerts` | SOS alert records with GPS coordinates |
| `complaints` | Patient complaint submissions |
| `private_conversations` | 1:1 chat between users |
| `private_messages` | Messages in private conversations |
| `notifications` | In-app notification system |
| `call_records` | Video call session records |
| `call_participants` | Participants in video calls |
| `video_call_audit_logs` | Security audit logs for calls |
| `feedback` | Patient ratings & reviews for doctors |
| `user_color_palettes` | Custom UI theme preferences |
| `leave_requests` | Doctor leave applications |
| `medicine_reminders` | Patient medication schedule |
| `clinical_guidelines` | RAG knowledge base embeddings |
| `audit_logs` | System-wide action audit trail |

---

### 5.2 Authentication & Authorization

#### JWT Token Flow

```
┌─────────┐    Register/Login    ┌─────────┐    Verify OTP     ┌─────────┐
│  Client │ ──────────────────► │ Backend │ ────────────────► │  Client │
│         │ ◄── Access Token ── │         │ ◄─ Refresh Token │         │
└────┬────┘                     └─────────┘                  └────┬────┘
     │                                                           │
     │  Authenticated Request (Bearer token)                       │
     └────────────────────────────────────────────────────────────►│
```

#### Token Types

| Token | Expiry | Purpose |
|-------|--------|---------|
| Access Token | 24 hours | API authentication |
| Refresh Token | 7 days | Obtain new access tokens |

#### Role-Based Access Control (RBAC)

```python
# Dependency example
current_user: models.User = Depends(require_role(["doctor", "admin"]))
```

| Permission | Patient | Doctor | Admin | Caregiver |
|------------|:-------:|:------:|:-----:|:---------:|
| Book appointments | ✅ | ❌ | ✅ | ❌ |
| Create prescriptions | ❌ | ✅ | ❌ | ❌ |
| Verify doctors | ❌ | ❌ | ✅ | ❌ |
| Trigger SOS | ✅ | ✅ | ✅ | ✅ |
| Manage users | ❌ | ❌ | ✅ | ❌ |
| View medical records | ✅ (own) | ✅ (patients) | ✅ | ❌ |
| Switch role (admin↔base) | ❌ | ✅* | ✅* | ❌ |

*Requires `has_admin_permission = True`

#### OTP Verification Flow

1. User registers → OTP generated & emailed via Brevo
2. User submits OTP → account verified
3. Unverified users cannot access dashboards
4. OTP expiry: implicit (replaced on resend)

---

### 5.3 API Endpoints

#### Authentication (`/auth`)

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| POST | `/auth/register` | Register new user | No |
| POST | `/auth/login` | Login & receive tokens | No |
| POST | `/auth/verify-otp` | Verify email OTP | No |
| POST | `/auth/resend-otp` | Resend OTP email | No |
| POST | `/auth/refresh` | Refresh access token | No (refresh token) |
| POST | `/auth/logout` | Logout user | Yes |
| GET | `/auth/me` | Get current user profile | Yes |
| POST | `/auth/forgot-password` | Request password reset | No |
| POST | `/auth/forgot-password-verify` | Verify & login via OTP | No |
| POST | `/auth/request-admin` | Request admin promotion | Yes |
| POST | `/auth/switch-role` | Toggle admin/base role | Yes (admin perm) |
| POST | `/auth/toggle-status` | Activate/deactivate user | Yes (admin) |
| DELETE | `/auth/admin/users/{id}` | Delete user & all data | Yes (admin) |

#### Doctors (`/doctors`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/doctors` | List all doctors (with translation) |
| POST | `/doctors/register` | Register doctor profile |
| PUT | `/doctors/profile` | Update doctor profile |
| POST | `/doctors/leave-request` | Submit leave request |
| GET | `/doctors/leave-requests` | Get all leave requests (admin) |
| POST | `/doctors/leave-request/{id}/approve` | Approve leave |
| POST | `/doctors/leave-request/{id}/reject` | Reject leave |
| POST | `/doctors/{id}/trigger-surgery-replacement` | Emergency reassignment |

#### Appointments (`/appointments`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/appointments` | List user's appointments |
| POST | `/appointments` | Book new appointment |
| PUT | `/appointments/{id}/cancel` | Cancel appointment |
| PUT | `/appointments/{id}/priority` | Update priority (doctor) |

#### Medical Records (`/records`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/records` | Get user's records |
| POST | `/records/upload` | Upload new record |
| DELETE | `/records/{id}` | Delete record |
| POST | `/records/{id}/analyze` | AI analysis of record |
| POST | `/records/{id}/anti-fraud` | Run anti-fraud scan |

#### Imaging (`/imaging`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/imaging/analyze` | Analyze medical image |
| GET | `/imaging/my-diagnostics` | Get user's diagnostic history |
| DELETE | `/imaging/{id}` | Delete diagnostic report |

#### Dashboard

| Method | Endpoint | Access |
|--------|----------|--------|
| GET | `/dashboard/metrics` | Patient health metrics |
| POST | `/dashboard/metrics` | Log new metric |
| GET | `/doctor/dashboard` | Doctor dashboard data |
| GET | `/admin/dashboard` | Admin dashboard data |
| POST | `/admin/verify-doctor/{id}` | Verify/reject doctor |

#### Conversations (`/conversations`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/conversations` | Start new conversation |
| GET | `/conversations` | List user's conversations |
| GET | `/conversations/{id}` | Get conversation with messages |
| POST | `/conversations/{id}/messages` | Send message & get AI reply |

#### WebSocket

| Endpoint | Purpose |
|----------|---------|
| `/ws?token={jwt}` | Real-time signaling (WebRTC ICE/SDP) |

---

### 5.4 Services

#### AI Imaging Diagnostics

| Scan Type | AI Model | Fallback |
|-----------|----------|----------|
| Skin / Dermatology | `LaurianeMD/vit-skin-disease` (ViT) | Offline heuristics |
| Chest X-Ray | `hiroaki-f/my_chest_xray_model` (ViT NIH) | Offline heuristics |
| Throat / Pharynx | Deterministic feature heuristics | Offline heuristics |
| Default | Skin model | Offline heuristics |

#### Translation Pipeline (Doctor Profiles)

```
User Request (Accept-Language: hi)
        │
        ▼
┌─────────────────────┐
│ 1. Gemini 2.5 Flash │ ← Primary
└─────────────────────┘
        │ (timeout: 4s)
        ▼ (on failure)
┌─────────────────────┐
│ 2. Groq Llama-3.1   │ ← Fallback 1
└─────────────────────┘
        │ (timeout: 4s)
        ▼ (on failure)
┌─────────────────────┐
│ 3. HuggingFace LLM  │ ← Fallback 2
└─────────────────────┘
        │ (timeout: 5s)
        ▼ (on failure)
┌─────────────────────┐
│ 4. Rule-based       │ ← Final fallback
└─────────────────────┘
```

#### Voice Pipeline

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  Browser    │───►│  VAD +      │───►│  Groq       │───►│  TTS Queue  │
│  Microphone │    │  MediaRecorder│   │  Whisper    │    │  (Streaming)│
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
                                                              │
                              ┌───────────────────────────────┘
                              ▼
                        ┌─────────────┐
                        │ faster_     │ ← Local CPU backup
                        │ whisper     │
                        └─────────────┘
```

---

### 5.5 WebSocket

The WebSocket connection at `/ws` handles:

| Event | Direction | Description |
|-------|-----------|-------------|
| `ping` | C→S | Keep-alive ping |
| `pong` | S→C | Keep-alive response |
| `signal` | C→S | WebRTC ICE/SDP signaling |

Connection requires a valid JWT access token via query parameter.

---

## 6. Frontend Documentation

### 6.1 Component Architecture

```
App.jsx (Router)
    │
    ├── LanguageProvider
    │   └── AuthProvider
    │       └── ThemeProvider
    │           └── WebSocketProvider
    │               └── CallProvider
    │                   ├── Landing (public)
    │                   ├── Login (public)
    │                   ├── Register (public)
    │                   ├── OtpVerify (public)
    │                   │
    │                   └── Layout (authenticated)
    │                       ├── TopNavBar
    │                       ├── SideNavBar
    │                       └── [Page Content]
    │                           ├── PatientDashboard
    │                           ├── DoctorDashboard
    │                           ├── AdminDashboard
    │                           ├── DoctorSearch
    │                           ├── MedicalRecords
    │                           ├── ImagingDiagnostics
    │                           ├── Chat
    │                           └── Settings
    │
    └── GlobalAssistant (floating voice widget)
```

### 6.2 Routing

| Route | Component | Access |
|-------|-----------|--------|
| `/` | Landing | Public |
| `/login` | Login | Public |
| `/register` | Register | Public |
| `/otp-verify` | OtpVerify | Public (post-register) |
| `/dashboard` | DashboardRedirect | Authenticated |
| `/patient/:id` | PatientDashboard | Patient only |
| `/doctor/:id` | DoctorDashboard | Doctor only |
| `/admin/:id` | AdminDashboard | Admin only |
| `/appointments` | DoctorSearch | Patient |
| `/records` | MedicalRecords | Patient/Doctor |
| `/imaging` | ImagingDiagnostics | Patient/Doctor |
| `/chat` | Chat | Authenticated |
| `/settings` | Settings | Authenticated |
| `*` | PublicOrPrivateRedirect | All |

### 6.3 State Management

| Context | Responsibility |
|---------|---------------|
| `AuthContext` | JWT tokens, user state, login/logout/refresh |
| `ThemeContext` | Light/dark mode, custom color palettes |
| `LanguageContext` | Multi-language UI (i18n) |
| `WebSocketContext` | WebSocket connection, real-time messages |
| `CallContext` | Video call state, WebRTC peer connection |

---

## 7. Setup & Installation

### Prerequisites

- Python 3.11 or higher
- Node.js 18 or higher
- PostgreSQL (or Supabase account)

### Backend Setup

```bash
# 1. Navigate to backend
cd backend

# 2. Create virtual environment
python -m venv venv

# 3. Activate virtual environment
# Windows:
.\venv\Scripts\Activate.ps1
# macOS/Linux:
source venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Configure environment
cp .env.example .env
# Edit .env with your API keys and database URLs

# 6. Run migrations
python migrate.py

# 7. Start development server
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Setup

```bash
# 1. Navigate to frontend
cd Frontend

# 2. Install dependencies
npm install

# 3. Configure environment
cp .env.example .env
# Edit .env with your API base URL

# 4. Start development server
npm run dev
```

The frontend will be available at `http://localhost:5173` and the backend at `http://localhost:8000`.

---

## 8. Environment Variables

### Backend (`backend/.env`)

| Variable | Required | Description |
|----------|:--------:|-------------|
| `DATABASE_URL` | ✅ | PostgreSQL connection string (pooler) |
| `DIRECT_DATABASE_URL` | ✅ | Direct PostgreSQL connection (port 5432) |
| `SECRET_KEY` | ✅ | JWT signing secret |
| `ACCESS_TOKEN_EXPIRE_HOURS` | ❌ | JWT expiry (default: 24) |
| `GROQ_API_KEY` | ✅ | Groq API for Whisper STT |
| `GEMINI_API_KEY` | ❌ | Google Gemini for LLM features |
| `HUGGINGFACE_API_KEY` | ❌ | HuggingFace fallback LLM |
| `BREVO_API_KEY` | ✅ | Brevo email service |
| `BREVO_SENDER_EMAIL` | ✅ | Sender email address |
| `LIVEKIT_URL` | ❌ | LiveKit server URL |
| `LIVEKIT_API_KEY` | ❌ | LiveKit API key |
| `LIVEKIT_API_SECRET` | ❌ | LiveKit API secret |
| `TESTING` | ❌ | Set to `True` for test mode |

### Frontend (`Frontend/.env`)

| Variable | Description |
|----------|-------------|
| `VITE_API_BASE_URL` | Backend API URL (e.g., `http://localhost:8000`) |

---

## 9. Testing

### Backend Tests

```bash
cd backend

# Run all tests
python -m pytest -v

# Run specific test file
python -m pytest test_api.py -v
python -m pytest test_voice_pipeline.py -v
python -m pytest test_imaging_comprehensive.py -v
```

| Test File | Coverage |
|-----------|----------|
| `test_api.py` | Authentication, symptoms, RBAC |
| `test_calls.py` | LiveKit calling routes |
| `test_chats_notifications.py` | Notifications system |
| `test_feedback.py` | Feedback & ratings |
| `test_new_endpoints.py` | Whisper, prescriptions, anti-fraud |
| `test_voice_pipeline.py` | WebSocket transcription |
| `test_booking_rules.py` | Appointment booking logic |
| `test_dashboard_production.py` | Dashboard aggregation |
| `test_color_palettes_api.py` | Theme preferences |
| `test_imaging_comprehensive.py` | AI imaging diagnostics |

### Test Database

When `TESTING=True`, the app automatically:
1. Redirects to a test database (`healthai_test` on Supabase)
2. Falls back to SQLite `:memory:` if no database URL is set

---

## 10. Deployment

### Backend Deployment

**Recommended:** Deploy to a cloud provider (AWS, GCP, Azure) or use a PaaS:

```bash
# Production startup (no reload)
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# With gunicorn (multiple workers)
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### Frontend Deployment

The frontend includes `vercel.json` for Vercel deployment:

```bash
cd Frontend
npm run build
# Deploy dist/ folder to Vercel, Netlify, or any static host
```

### Supabase Configuration

1. Create a Supabase project
2. Get the connection strings from **Project Settings → Database**
3. Use the **Transaction** pooler URL for `DATABASE_URL` (port 6543)
4. Use the **Direct** connection string for `DIRECT_DATABASE_URL` (port 5432)
5. Run migrations: `python migrate.py`

---

## 11. Key Features Deep Dive

### 11.1 TARS Voice Assistant

- **Wake Word Detection:** Background speech recognizer listens for `"Hey TARS"`
- **STT Pipeline:** Groq Whisper API (< 200ms) with local `faster_whisper` fallback
- **Voice Actions:** Dashboard control via natural language (e.g., `"Set medicine reminder for Paracetamol at 8 AM"`)
- **TTS Queue:** Sentence-boundary streaming to prevent speech overlap

### 11.2 Medical Imaging Diagnostics

1. User uploads an image (PNG, JPG, WEBP)
2. System validates file type and runs anti-tampering check
3. Image is routed to appropriate AI model based on `scan_type`:
   - `skin` / `derma` → Skin disease ViT model
   - `x-ray` / `chest` → Chest X-ray ViT model
   - `throat` → Throat heuristic engine
4. If AI model fails, falls back to offline clinical heuristics
5. Results saved to database with severity classification

### 11.3 SOS Emergency Alert

1. Patient clicks SOS button → browser retrieves GPS coordinates
2. Backend calculates doctor distances using Haversine formula
3. Notifications sent to all doctors within 100km radius
4. Admin dashboard shows active alerts

### 11.4 Surgery Replacement Workflow

1. Doctor triggers emergency surgery replacement
2. All booked appointments reassigned to available doctors in same specialization
3. Patients and new doctors receive notifications
4. Private messages sent to affected patients
5. If no replacement available, appointments marked `pending_reschedule`

### 11.5 Anti-Fraud Document Scan

- Analyzes image metadata for tampering signatures
- Detects Photoshop/GIMP editing tags
- Checks file consistency and document signatures
- Returns `VERIFIED` or `FLAGGED` status

---

## 12. Troubleshooting

| Issue | Solution |
|-------|----------|
| Database connection fails | Check `DATABASE_URL` format; ensure `postgresql://` prefix |
| CORS errors | Verify backend `allow_origins=["*"]` in development |
| Email not sending | Check `BREVO_API_KEY` and `BREVO_SENDER_EMAIL` |
| AI models fail to load | Ensure `GEMINI_API_KEY` or `GROQ_API_KEY` is set |
| WebSocket disconnects | Verify token is passed as query parameter |
| Imaging upload fails | Check `UPLOADS_DIR` permissions |
| Test database locked | Set `TESTING=True` to use separate test DB |

---

## Appendix A: Demo Accounts

| Email | Role | Password |
|-------|------|----------|
| `patient@healthai.test` | Patient | `Password123!` |
| `alice.smith@hospital.com` | Doctor | `Password123!` |
| `admin@healthai.test` | Admin | `Password123!` |
| `sricharanpranav1@gmail.com` | Superadmin | `Pranav@123` |

## Appendix B: API Base URLs

| Environment | URL |
|-------------|-----|
| Development | `http://localhost:8000` |
| Frontend Dev | `http://localhost:5173` |

---

*Documentation generated for the TARS Next-Gen AI Healthcare Assistant project.*
