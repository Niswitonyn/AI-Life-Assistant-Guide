import requests
import json
from app.database.db import SessionLocal
from app.database.models import User

# Check user in DB
session = SessionLocal()
user = session.query(User).filter(User.email == 'tonyniswin@gmail.com').first()
print(f"User exists: {user is not None}")
if user:
    print(f"  Email: {user.email}")
    print(f"  User ID: {user.user_id}")
    print(f"  Name: {user.name}")
    print(f"  Password hash: {user.password[:30] if user.password else 'NO PASSWORD'}...")
    print(f"  Password is None: {user.password is None}")

# Try login
response = requests.post(
    'http://127.0.0.1:8000/api/user/login',
    json={'email': 'tonyniswin@gmail.com', 'password': 'test123'}
)

print(f"\nLogin Status: {response.status_code}")
print(f"Login Response: {json.dumps(response.json(), indent=2)}")
