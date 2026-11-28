import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError
import jwt

from database import get_db
from models import User

ph = PasswordHasher()
security = HTTPBearer(
    scheme_name="JWTBearer",
    description="Enter your JWT access token",
    auto_error=False,
)

# P3.3: Read one JWT_SECRET setting; if unset, generate random secret outside repo
JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    secret_cache_path = os.path.expanduser("~/.ledgerbridge_jwt_secret")
    if os.path.exists(secret_cache_path):
        try:
            with open(secret_cache_path, "r", encoding="utf-8") as f:
                JWT_SECRET = f.read().strip()
        except OSError:
            JWT_SECRET = secrets.token_hex(32)
    else:
        JWT_SECRET = secrets.token_hex(32)
        try:
            with open(secret_cache_path, "w", encoding="utf-8") as f:
                f.write(JWT_SECRET)
        except OSError:
            pass

SECRET_KEY = JWT_SECRET
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 30


def hash_password(password: str) -> str:
    return ph.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return ph.verify(hashed_password, plain_password)
    except (VerifyMismatchError, VerificationError):
        return False


def create_access_token(user_id: str, expires_delta: Optional[timedelta] = None) -> str:
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": user_id,
        "exp": expire,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


async def get_current_user(
    request: Request,
    auth: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    token: Optional[str] = None
    if auth and auth.credentials:
        token = auth.credentials
    elif request and request.cookies.get("access_token"):
        token = request.cookies.get("access_token")

    async def _get_default_local_user() -> User:
        result = await db.execute(select(User).limit(1))
        local_user = result.scalars().first()
        if local_user:
            return local_user
        return User(
            id="local-user",
            email="finance@company.com",
            username="finance",
            company_name="Access Capital Ltd",
            password="",
        )

    # P3.4 Option A: Single-user local mode. If no token, invalid token, or expired session,
    # automatically authenticate to the local user so the app works seamlessly offline without 401s.
    if not token:
        return await _get_default_local_user()

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id_raw: Optional[str] = payload.get("sub")
        if not user_id_raw:
            return await _get_default_local_user()
        user_id = str(user_id_raw)
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalars().first()
        if user is None:
            return await _get_default_local_user()
        return user
    except jwt.PyJWTError:
        return await _get_default_local_user()
