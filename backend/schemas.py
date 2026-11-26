import datetime
from typing import List, Optional
from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    company_name: Optional[str] = None
    username: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: str
    email: EmailStr
    company_name: Optional[str] = None
    username: Optional[str] = None

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# ------------------------------
# Statement & Transaction Schemas
# ------------------------------

class TransactionItem(BaseModel):
    date: str
    value_date: Optional[str] = None
    description_raw: str
    description_norm: str
    amount: float
    direction: str  # 'debit' or 'credit'
    balance: Optional[float] = None
    fingerprint: Optional[str] = None
    element: Optional[str] = "needs_review"
    tier: Optional[str] = None
    confidence: Optional[float] = None
    reason: Optional[str] = None
    status: Optional[str] = "auto"


class TransactionResponse(TransactionItem):
    id: str
    statement_id: str

    class Config:
        from_attributes = True


class StatementResponse(BaseModel):
    id: str
    filename: str
    bank_name: str
    currency: str = "NGN"
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    opening_balance: Optional[float] = None
    closing_balance: Optional[float] = None
    total_credits: Optional[float] = None
    total_debits: Optional[float] = None
    math_ok: bool
    math_error_detail: Optional[str] = None
    transaction_count: int
    transactions: List[TransactionResponse] = []

    class Config:
        from_attributes = True


class TransactionUpdateRequest(BaseModel):
    element: str  # 'asset', 'liability', 'income', 'expense', 'capital', 'needs_review'
    create_rule: bool = False
    rule_pattern: Optional[str] = None
    rule_direction: Optional[str] = "any"


class RuleCreateRequest(BaseModel):
    pattern: str
    element: str  # 'asset', 'liability', 'income', 'expense', 'capital'
    direction: str = "any"
    priority: int = 50
    match_type: str = "word_regex"


class RuleResponse(BaseModel):
    id: int
    pattern: str
    match_type: str
    direction: str
    element: str
    priority: int
    source: str
    hit_count: int
    active: bool
    created_at: Optional[datetime.datetime] = None

    class Config:
        from_attributes = True


class CategoryCreate(BaseModel):
    name: str
    direction: str = "any"  # 'any', 'debit', 'credit'
    color: str = "slate"
    description: Optional[str] = None


class CategoryResponse(BaseModel):
    id: int
    name: str
    slug: str
    direction: str
    color: str
    description: Optional[str] = None
    is_system: bool
    created_at: Optional[datetime.datetime] = None

    class Config:
        from_attributes = True


class UploadSummaryResponse(BaseModel):
    statement_id: str
    filename: str
    bank_name: str
    currency: str = "NGN"
    math_ok: bool
    math_error_detail: Optional[str] = None
    opening_balance: Optional[float] = None
    closing_balance: Optional[float] = None
    total_credits: Optional[float] = None
    total_debits: Optional[float] = None
    total_rows_parsed: int
    new_rows_stored: int
    duplicates_skipped: int
    rules_count: int = 0
    llm_count: int = 0
    needs_review_count: int = 0
    message: str
