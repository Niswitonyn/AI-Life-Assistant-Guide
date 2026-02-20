import os
import json

def start_watch_for_user(user_id, gmail_agent):

    topic = "projects/YOUR_PROJECT/topics/gmail-notifications"

    response = gmail_agent.start_watch(topic)

    data = {
        "user_id": user_id,
        "historyId": response.get("historyId")
    }

    path = "app/data/pubsub_users.json"

    if os.path.exists(path):
        with open(path, "r") as f:
            users = json.load(f)
    else:
        users = {}

    users[user_id] = data

    with open(path, "w") as f:
        json.dump(users, f, indent=2)
        