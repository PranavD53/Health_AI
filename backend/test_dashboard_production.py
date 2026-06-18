import os
import sys
from dotenv import load_dotenv
from fastapi.testclient import TestClient

# Load env before importing database components
load_dotenv()

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.main import app
from app.routes.auth import create_access_token

def main():
    print("Testing /admin/dashboard endpoint directly via TestClient on Supabase DB...")
    
    # Generate token for sricharanpranav1@gmail.com (role: admin)
    token = create_access_token(data={"sub": "sricharanpranav1@gmail.com", "role": "admin"})
    
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token}"}
    
    print("Sending GET request to /admin/dashboard...")
    response = client.get("/admin/dashboard", headers=headers)
    
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        print("Success! Response JSON:")
        data = response.json()
        print(f"Total Patients: {data.get('total_patients')}")
        print(f"Total Doctors: {data.get('total_doctors')}")
        print(f"Pending Verifications: {data.get('pending_verifications')}")
        print(f"Verification Queue Length: {len(data.get('verification_queue', []))}")
        print(f"Users list Length: {len(data.get('users', []))}")
    else:
        print(f"Failure! Response text: {response.text}")
        
    print("\nSending GET request to /admin/complaints...")
    response2 = client.get("/admin/complaints", headers=headers)
    print(f"Status Code: {response2.status_code}")
    if response2.status_code == 200:
        print("Success! Complaints length:", len(response2.json()))
    else:
        print(f"Failure! Response text: {response2.text}")

if __name__ == "__main__":
    main()
