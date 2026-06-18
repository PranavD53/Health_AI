import os
import sys
from dotenv import load_dotenv
from sqlalchemy.orm import Session

# Load env before importing database components
load_dotenv()

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal, engine
from app import models
from app.routes.auth import get_password_hash, create_access_token

def main():
    print("Connecting to database...")
    db: Session = SessionLocal()
    email = "sricharanpranav1@gmail.com"
    password = "Pranav@123"
    
    try:
        user = db.query(models.User).filter(models.User.email == email).first()
        hashed_password = get_password_hash(password)
        
        if user:
            print(f"User {email} exists. Updating role to admin and resetting password...")
            user.role = "admin"
            user.password = hashed_password
            user.is_verified = True
            user.admin_requested = False
            db.commit()
            print("User updated successfully.")
        else:
            print(f"User {email} does not exist. Creating a new admin user...")
            new_user = models.User(
                email=email,
                password=hashed_password,
                role="admin",
                is_verified=True,
                admin_requested=False
            )
            db.add(new_user)
            db.commit()
            db.refresh(new_user)
            user = new_user
            print("Admin user created successfully.")
            
        # Generate JWT Token
        token = create_access_token(data={"sub": user.email, "role": user.role})
        print("\n" + "="*50)
        print("SUPERADMIN JWT ACCESS TOKEN GENERATED SUCCESSFULLY:")
        print("="*50)
        print(token)
        print("="*50 + "\n")
        
    except Exception as e:
        db.rollback()
        print(f"Error occurred: {e}", file=sys.stderr)
    finally:
        db.close()

if __name__ == "__main__":
    main()
