import json
import os
import sys
import tempfile
from pathlib import Path
from typing import AsyncGenerator
import httpx
import pytest
import pytest_asyncio

# Ensure backend root is on sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Create a temporary database file for the test session
_temp_dir = tempfile.TemporaryDirectory()
_temp_db_path = Path(_temp_dir.name) / "test_project.db"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_temp_db_path}"

from database import Base, engine, AsyncSessionLocal
import models
from main import app


@pytest_asyncio.fixture(autouse=True)
async def clean_database_per_test():
    """Provides a clean database schema for each test."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator:
    """Yields an AsyncSession connected to the temporary test database."""
    async with AsyncSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Yields an AsyncClient connected to the FastAPI application."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def auth_headers(client: httpx.AsyncClient) -> dict:
    """Creates a test user and returns authorization headers."""
    payload = {
        "email": "tester@example.com",
        "password": "TestPassword123!",
        "company_name": "Test Company Ltd",
    }
    res = await client.post("/auth/signup", json=payload)
    if res.status_code in (200, 201):
        token = res.json()["access_token"]
    else:
        login_res = await client.post("/auth/login", json={"email": payload["email"], "password": payload["password"]})
        assert login_res.status_code == 200, f"Login failed: {login_res.text}"
        token = login_res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def mock_ollama(monkeypatch):
    """
    Mocks Ollama local API chat completions so all tests run offline,
    deterministically, and with zero latency.
    """
    orig_post = httpx.AsyncClient.post

    async def mock_post(self, url, *args, **kwargs):
        url_str = str(url)
        if "/api/chat" in url_str:
            req_json = kwargs.get("json", {})
            user_msg = ""
            for m in req_json.get("messages", []):
                if m.get("role") == "user":
                    user_msg = m.get("content", "")

            results = []
            try:
                if "Transactions:" in user_msg:
                    raw_json = user_msg.split("Transactions:", 1)[1].strip()
                    txns = json.loads(raw_json)
                    for t in txns:
                        tid = str(t.get("id"))
                        desc = (t.get("description") or "").upper()
                        elem = "expense"
                        conf = 0.88
                        if "INVOICE" in desc or "SALES" in desc:
                            elem = "income"
                        elif "CAPITAL" in desc or "EQUITY" in desc:
                            elem = "capital"
                        elif "LOAN" in desc:
                            elem = "liability"
                        elif "TRF TO PPL" in desc or "ATM" in desc or "UNKNOWN" in desc:
                            elem = "needs_review"
                            conf = 0.50

                        results.append({
                            "id": tid,
                            "element": elem,
                            "confidence": conf,
                            "reason": f"Classified by mocked LLM as {elem}",
                        })
            except Exception:
                pass

            mock_body = {"message": {"content": json.dumps({"results": results})}}
            return httpx.Response(200, json=mock_body, request=httpx.Request("POST", url))

        return await orig_post(self, url, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)
