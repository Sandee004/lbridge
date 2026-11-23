import datetime
import uuid
from sqlalchemy import DECIMAL, Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column
from database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    username: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    password: Mapped[str] = mapped_column(String, nullable=False)


class Statements(Base):
    __tablename__ = "statements"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    filename: Mapped[str] = mapped_column(String, nullable=False)
    bank_name: Mapped[str] = mapped_column(String, default='Generic')
    period_start: Mapped[DateTime] = mapped_column(DateTime)
    period_end: Mapped[DateTime] = mapped_column(DateTime)
    opening_balance: Mapped[float] = mapped_column(DECIMAL(precision=10, scale=2))
    closing_balance: Mapped[float] = mapped_column(DECIMAL(precision=10, scale=2))
    opening_balance: Mapped[float] = mapped_column(DECIMAL(precision=10, scale=2))
    closing_balance: Mapped[float] = mapped_column(DECIMAL(precision=10, scale=2))
    total_credits: Mapped[float] = mapped_column(DECIMAL(precision=10, scale=2))
    total_debits: Mapped[float] = mapped_column(DECIMAL(precision=10, scale=2))
    math_ok: Mapped[bool] = mapped_column(Boolean)
    math_error_detail: Mapped[str] = mapped_column(String)
    created_at: Mapped[DateTime] = mapped_column(DateTime, default=lambda: datetime.utcnow())