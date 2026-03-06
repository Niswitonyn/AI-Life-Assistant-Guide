from sqlalchemy.orm import declarative_base

# -----------------------------------------
# Base Model
# -----------------------------------------
# This is the declarative base for all SQLAlchemy models.
# By defining it here (separate from db.py), we avoid circular imports:
# - db.py can import Base without importing models
# - models.py can import Base without importing db (which might import models)
# This is the standard SQLAlchemy pattern.

Base = declarative_base()
