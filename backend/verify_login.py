import requests
import json

response = requests.post(
    'http://127.0.0.1:8000/api/user/login',
    json={'email': 'tonyniswin@gmail.com', 'password': 'password123'}
)

print(f"Status: {response.status_code}")
data = response.json()
print(f"\n{json.dumps(data, indent=2)}")

if response.status_code == 200:
    print(f"\n✅ LOGIN SUCCESSFUL!")
    print(f"   Token: {data['token'][:50]}...")
    print(f"   User ID: {data['user_id']}")
    print(f"   Name: {data['name']}")
