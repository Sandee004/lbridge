import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from config import DIST_DIR, build_frontend
from database import AsyncSessionLocal, Base, engine
import models
from routers import auth, categories, rules, statements, transactions, ingester
load_dotenv()

# Build frontend automatically if outdated
build_frontend()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Auto-create SQLite database tables on startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(
    title="API",
    description="",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
    swagger_ui_parameters={"persistAuthorization": True},
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API Routers (static paths before dynamic /{statement_id})
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(rules.router, prefix="/statements", tags=["rules"])
app.include_router(transactions.router, prefix="/statements", tags=["transactions"])
app.include_router(categories.router, prefix="/statements/categories", tags=["categories"])
app.include_router(categories.router, prefix="/categories", tags=["categories"])
app.include_router(statements.router, prefix="/statements", tags=["statements"])


@app.get("/health", tags=["system"])
def health_check():
    return {"status": "ok", "service": "api"}

# ------------------------------
# Static Files & React SPA Fallback (Must remain at bottom)
# ------------------------------
assets_path = os.path.join(DIST_DIR, "assets")
if os.path.exists(assets_path):
    app.mount("/assets", StaticFiles(directory=assets_path), name="assets")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    file_path = os.path.join(DIST_DIR, "favicon.ico")
    if os.path.exists(file_path):
        return FileResponse(file_path)
    return (
        FileResponse(os.path.join(DIST_DIR, "index.html"))
        if os.path.exists(os.path.join(DIST_DIR, "index.html"))
        else {"error": "Favicon not found"}
    )


@app.get("/{full_path:path}", include_in_schema=False)
async def serve_react(full_path: str):
    potential_file = os.path.join(DIST_DIR, full_path)
    if full_path and os.path.isfile(potential_file):
        return FileResponse(potential_file)

    index_path = os.path.join(DIST_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)

    return {
        "status": "ready",
        "detail": "API online. Connect your frontend client or view /docs.",
    }

# To run: uvicorn main:app --host 127.0.0.1 --port 8000 --reload
