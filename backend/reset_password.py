from app.database.db import SessionLocal
from app.database.models import User
from app.core.auth import hash_password

session = SessionLocal()
user = session.query(User).filter(User.email == 'tonyniswin@gmail.com').first()

if user:
    # Reset password to 'password123'
    user.password = hash_password('password123')
    session.commit()
    print(f"✅ Password reset for {user.email}")
    print(f"   New password: password123")
else:
    print("❌ User not found")
