import requests
import io

BASE_URL = "http://localhost:8000"
print(f"Testing live server at {BASE_URL}...")

email = "livetest1@healthai.com"
password = "Password123!"

# Register
requests.post(f"{BASE_URL}/auth/register", json={
    "email": email,
    "password": password,
    "role": "patient"
})

# Login
login_data = {"email": email, "password": password}
print("\n--- 1. Logging in ---")
res = requests.post(f"{BASE_URL}/auth/login", json=login_data)
if res.status_code != 200:
    print("Login failed!", res.text)
    exit(1)

token = res.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}
print("Login successful! Got token.")

# 2. Test Symptom Triage - Emergency
print("\n--- 2. Testing Symptom Triage (Emergency) ---")
res = requests.post(
    f"{BASE_URL}/chat/symptom",
    headers=headers,
    json={"message": "I am having severe chest pain and can't breathe."}
)
print("Status:", res.status_code)
print("Response:", res.json())
assert res.status_code == 200
assert res.json()["is_emergency"] is True

# 3. Test Lab Report - Unsupported
print("\n--- 3. Testing Lab Report (Unsupported PDF) ---")
import reportlab.pdfgen.canvas as canvas
pdf_buffer = io.BytesIO()
c = canvas.Canvas(pdf_buffer)
c.drawString(100, 750, "Random document about allergies that has enough text to pass.")
c.drawString(100, 730, "This is an extra line so that the text extraction sees more.")
c.drawString(100, 710, "This ensures it doesn't fail the minimum length check for pdfplumber.")
c.save()

files = {"file": ("unsupported.pdf", pdf_buffer.getvalue(), "application/pdf")}
res = requests.post(
    f"{BASE_URL}/chat/lab-report/upload",
    headers=headers,
    files=files
)
print("Status:", res.status_code)
print("Response:", res.json())
assert res.status_code == 200
assert res.json()["success"] is False

# 4. Test Lab Report - Supported CBC
print("\n--- 4. Testing Lab Report (Supported CBC) ---")
pdf_buffer = io.BytesIO()
c = canvas.Canvas(pdf_buffer)
c.drawString(100, 750, "CBC Test Results")
c.drawString(100, 730, "Hemoglobin: 11.0")
c.drawString(100, 710, "WBC: 6.0")
c.drawString(100, 690, "Platelet Count: 200.0")
c.drawString(100, 670, "Hematocrit: 40.0")
c.save()

files = {"file": ("cbc_test.pdf", pdf_buffer.getvalue(), "application/pdf")}
res = requests.post(
    f"{BASE_URL}/chat/lab-report/upload",
    headers=headers,
    files=files
)
print("Status:", res.status_code)
print("Response:", res.json())
assert res.status_code == 200
assert res.json()["success"] is True

print("\n--- ALL LIVE SERVER TESTS PASSED SUCCESSFULLY! ---")
