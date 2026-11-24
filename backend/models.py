import datetime
import uuid
from typing import List, Optional
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    username: Mapped[Optional[str]] = mapped_column(String, unique=False, index=True, nullable=True)
    company_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    password: Mapped[str] = mapped_column(String, nullable=False)


class Statement(Base):
    __tablename__ = "statements"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    filename: Mapped[str] = mapped_column(String, nullable=False)
    bank_name: Mapped[str] = mapped_column(String, default="Access Bank Plc", nullable=False)
    currency: Mapped[str] = mapped_column(String, default="NGN", nullable=False)
    period_start: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    period_end: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    opening_balance: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    closing_balance: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    total_credits: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    total_debits: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    math_ok: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    math_error_detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_hash: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc)
    )

    transactions: Mapped[List["Transaction"]] = relationship(
        "Transaction", back_populates="statement", cascade="all, delete-orphan"
    )


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    statement_id: Mapped[str] = mapped_column(
        String, ForeignKey("statements.id", ondelete="CASCADE"), nullable=False, index=True
    )
    fingerprint: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    date: Mapped[str] = mapped_column(String, nullable=False)
    value_date: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    direction: Mapped[str] = mapped_column(String, nullable=False)  # 'debit' or 'credit'
    description_raw: Mapped[str] = mapped_column(Text, nullable=False)
    description_norm: Mapped[str] = mapped_column(Text, nullable=False)
    balance: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    element: Mapped[Optional[str]] = mapped_column(
        String, nullable=True, default="needs_review"
    )  # 'asset', 'liability', 'income', 'expense', 'capital', 'needs_review'
    tier: Mapped[Optional[str]] = mapped_column(
        String, nullable=True
    )  # 'rule', 'llm', 'validator', 'user'
    rule_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String, default="auto", nullable=False)  # 'auto' or 'reviewed'
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc)
    )

    statement: Mapped["Statement"] = relationship("Statement", back_populates="transactions")


class Rule(Base):
    __tablename__ = "rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pattern: Mapped[str] = mapped_column(String, nullable=False)
    match_type: Mapped[str] = mapped_column(
        String, default="word_regex", nullable=False
    )  # 'word_regex', 'exact_counterparty'
    direction: Mapped[str] = mapped_column(
        String, default="any", nullable=False
    )  # 'debit', 'credit', 'any'
    element: Mapped[str] = mapped_column(String, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    source: Mapped[str] = mapped_column(String, default="seed", nullable=False)  # 'seed' or 'user'
    hit_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc)
    )


class Override(Base):
    __tablename__ = "overrides"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    transaction_id: Mapped[str] = mapped_column(
        String, ForeignKey("transactions.id", ondelete="CASCADE"), nullable=False
    )
    predicted_element: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    predicted_tier: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    final_element: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc)
    )


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
