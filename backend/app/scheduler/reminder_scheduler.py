import time
from datetime import datetime
from sqlalchemy.orm import Session

from app.database.db import SessionLocal
from app.database.models import Task
from app.notifications.desktop_notifier import DesktopNotifier


class ReminderScheduler:
    """
    Background scheduler to check task reminders.
    """

    def __init__(self):
        self.running = False

    def start(self):
        self.running = True
        print("🔔 Reminder Scheduler Started")

        while self.running:
            self.check_reminders()
            time.sleep(30)  # check every 30 seconds

    def check_reminders(self):
        db: Session = SessionLocal()

        try:
            now = datetime.now()
            print("Checking reminders...")
            print("Current time:", now)

            tasks = db.query(Task).filter(
                Task.completed == False,
                Task.due_date != None
            ).all()

            for task in tasks:
                print("Task:", task.title, "Due:", task.due_date)

                if task.due_date and task.due_date <= now:
                    DesktopNotifier.send(
                        title="Reminder",
                        message=task.title
                    )

                    print(f"⏰ Reminder: {task.title}")

                    # Mark completed so it doesn't repeat
                    task.completed = True
                    db.commit()

        finally:
            db.close()
