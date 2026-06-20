# TARS Next-Gen AI Healthcare Assistant

A secure, next-generation AI-powered healthcare platform combining real-time voice assistance, YOLO-based computer vision diagnostics, automated clinical workflows, and emergency SOS services.

---

## 🚀 Key Features

### 1. 🎙️ TARS Voice Assistant (Native Standby & Wake-Word)
- **Wake Word Detection**: Background speech recognizer constantly listens for `"Hey TARS"`. Operates globally in visitor/guest mode to direct users to register or log in.
- **Ultra-Low Latency STT**: Prioritizes Groq's Whisper API in the cloud, transcribing speech in under **200ms**, with a local CPU-bound `faster_whisper` backup.
- **Voice-Native Execution**: Complete dashboard actions natively via voice commands (e.g., `"Run anti-fraud scan on report"`, `"Set medicine reminder for Paracetamol at 8 AM"`).
- **Smooth Queue-Backed Text-to-Speech (TTS)**: Intelligently segments and streams spoken responses at sentence boundaries, avoiding speech overlaps and network stutter.

### 2. 👁️ YOLO Computer Vision & Diagnostics
- **Object Detection Overlay**: Visual diagnostic scans (skin mole reports, chest X-rays, etc.) render absolute YOLO bounding boxes (e.g., *Melanoma Risk Area*, *Benign Nevus*, *Clavicle Fracture*) directly over the scanned image in the AI Insights modal.
- **Authenticity Anti-Fraud Scan**: Core heuristics analyze image metadata and document signatures (tampering signatures, Photoshop/GIMP tag detection) to flag manipulated documents. Available via automated file uploads and a manual "Run Anti-Fraud Security Scan" button.

### 3. 🚨 Geolocation SOS & Emergency Doctor Alerts
- **GPS Coordinates**: Clicking the SOS button retrieves the patient's precise browser latitude and longitude.
- **100km Alert Radius**: The backend calculates patient-to-doctor distances using the Haversine formula and broadcasts instant alert notifications to **all registered doctors located within a 100km radius** of the patient's current location.
- **Interactive Clinic Mapping**: Doctors can input coordinate pinning and clinic addresses in profile settings to establish their emergency alert availability.

### 4. 📅 Clinical Workflows & Doctor Leave Management
- **One-Stop Surgery Reassignment**: A single emergency button on the doctor dashboard automatically reassigns all booked consultations to other available specialists in the same department.
- **Leave Request Approvals**: Doctors submit leave dates; Admins approve/reject them in the Admin dashboard, automatically setting doctor availability to `False`.
- **Manually Adjustable Risk Priorities**: Consultations display High, Normal, and Low risk priority badges, manually assignable by doctors via a dropdown selection.

### 5. 💊 Medicine Reminders & Email Notifications
- **Multi-Channel Delivery**: Patients schedule reminders with specific dosages, times, and channels (In-App notifications, Brevo-based Email notifications, or SMS).
- **Dashboard Management**: Complete card UI to toggle notification statuses or delete schedules dynamically.

---

## 🛠️ Technology Stack

### Backend (FastAPI)
- **Framework**: FastAPI (python 3.11+)
- **Database**: PostgreSQL (Supabase cloud integration with connection pooling) / SQLite for local fallback
- **Authentication**: JWT tokens with custom Role-Based Access Control (RBAC)
- **Notification Services**: Brevo API integration for automated emails
- **Object Detection**: YOLO-simulated coordinates based on diagnostic tags

### Frontend (React & Vite)
- **Styling**: Vanilla CSS with modern HSL theme variables
- **Interactive Visuals**: Glowing mouse-following grids, custom ECG heartbeat glowing lines, and immediate load animation hooks
- **VAD Audio Capture**: HTML5 MediaRecorder and Web Audio API VAD (Voice Activity Detection)

---

## 🔧 Installation & Setup

### Prerequisites
- Python 3.11 or higher
- Node.js (v18+)
- SQLite / PostgreSQL connection

### 1. Backend Setup
1. Navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   # On Windows:
   .\venv\Scripts\Activate.ps1
   # On macOS/Linux:
   source venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Configure environment variables in `.env` (refer to `.env.example`):
   ```ini
   DATABASE_URL=your_supabase_url
   DIRECT_DATABASE_URL=your_supabase_direct_url
   GROQ_API_KEY=your_groq_key
   BREVO_API_KEY=your_brevo_key
   SECRET_KEY=your_jwt_signing_key
   ```
5. Apply database schema and migrations:
   ```bash
   python migrate.py
   ```
6. Start the development server:
   ```bash
   python -m uvicorn app.main:app --reload
   ```

### 2. Frontend Setup
1. Navigate to the frontend directory:
   ```bash
   cd Frontend
   ```
2. Install npm packages:
   ```bash
   npm install
   ```
3. Start the Vite development server:
   ```bash
   npm run dev
   ```

---

## 🧪 Testing

Execute the complete backend test suite to verify endpoints, voice transcription channels, and database cascade deletion schemas:

```bash
cd backend
python -m pytest -v
```

All 6 core test files are verified and pass:
- `test_api.py` (Authentication, symptoms analysis, RBAC)
- `test_calls.py` (LiveKit calling routes)
- `test_chats_notifications.py` (System notifications logs)
- `test_feedback.py` (Auditing feedbacks logs)
- `test_new_endpoints.py` (Whisper, record analysis, online prescriptions, anti-fraud scans)
- `test_voice_pipeline.py` (TARS WebSocket transcription)
