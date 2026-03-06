from sqlalchemy.orm import Session
from dateutil import parser as date_parser
from datetime import datetime

from app.database.models import Task


class TaskAgent:
    """
    AI Agent that converts natural language into tasks.
    """

    def __init__(self, db: Session):
        self.db = db

    def extract_due_date(self, text: str):
        """
        Try to extract date from text.
        """
        try:
            dt = date_parser.parse(text, fuzzy=True)
            return dt
        except Exception:
            return None

    def clean_title(self, text: str):
        """
        Remove trigger words from text.
        """
        words_to_remove = ["add task", "task", "remind me to", "remind", "please"]
        title = text.lower()

        for w in words_to_remove:
            title = title.replace(w, "")

        return title.strip().capitalize()

    def create_task_from_text(self, text: str):
        """
        Create a task from user text.
        """

        due_date = self.extract_due_date(text)
        title = self.clean_title(text)

        task = Task(
            title=title,
            description="Created from AI command",
            due_date=due_date,
        )

        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)

        return task
