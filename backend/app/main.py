from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router


app = FastAPI(
    title="RepoTutor API",
    description="面向 Python/FastAPI 代码库的交互式 AI 代码导师",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
def root() -> dict[str, object]:
    return {
        "name": "RepoTutor API",
        "status": "ok",
        "docs_url": "/docs",
        "health_url": "/health",
        "api_prefix": "/api",
        "frontend_url": "http://127.0.0.1:8501",
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
