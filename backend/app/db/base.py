"""SQLAlchemy declarative base — the parent class for all ORM models."""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Common base for all ORM models. Created here so models.py can import it."""
    pass