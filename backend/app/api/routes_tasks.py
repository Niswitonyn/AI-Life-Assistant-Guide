from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.database.db import get_db
from app.database.models import Task

router = APIRouter()


# -------------------------
# Schemas
# -------------------------

from pydantic import BaseModel
from datetime import datetime


class TaskCreate(BaseModel):
    title: str
    description: str | None = None
    due_date: datetime | None = None


class TaskResponse(BaseModel):
    id: int
    title: str
    description: str | None
    completed: bool

    class Config:
        from_attributes = True


# -------------------------
# Create Task
# -------------------------

@router.post("/", response_model=TaskResponse)
def create_task(task: TaskCreate, db: Session = Depends(get_db)):

    db_task = Task(
        title=task.title,
        description=task.description,
        due_date=task.due_date,
    )

    db.add(db_task)
    db.commit()
    db.refresh(db_task)

    return db_task


# -------------------------
# Get All Tasks
# -------------------------

@router.get("/", response_model=List[TaskResponse])
def get_tasks(db: Session = Depends(get_db)):
    return db.query(Task).all()


# -------------------------
# Complete Task
# -------------------------

@router.put("/{task_id}/complete")
def complete_task(task_id: int, db: Session = Depends(get_db)):

    task = db.query(Task).filter(Task.id == task_id).first()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    task.completed = True
    db.commit()

    return {"status": "completed"}


# -------------------------
# Delete Task
# -------------------------

@router.delete("/{task_id}")
def delete_task(task_id: int, db: Session = Depends(get_db)):

    task = db.query(Task).filter(Task.id == task_id).first()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    db.delete(task)
    db.commit()

    return {"status": "deleted"}

