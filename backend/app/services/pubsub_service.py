import json
from app.config.paths import USERS_FILE

def start_watch_for_user(user_id, gmail_agent):

    topic = "projects/YOUR_PROJECT/topics/gmail-notifications"

    response = gmail_agent.start_watch(topic)

    data = {
        "user_id": user_id,
        "historyId": response.get("historyId")
    }

    path = USERS_FILE

    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            users = json.load(f)
    else:
        users = {}

    users[user_id] = data

    with open(path, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=2)
        
