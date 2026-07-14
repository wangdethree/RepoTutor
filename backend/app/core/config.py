from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    """应用配置，优先从环境变量读取，便于 Docker 和本地开发共用。"""

    database_url: str
    artifact_dir: Path
    upload_dir: Path
    diagram_dir: Path
    report_dir: Path
    llm_api_key: str
    llm_base_url: str
    llm_model: str
    llm_temperature: float


def get_settings() -> Settings:
    artifact_dir = Path(os.getenv("REPO_TUTOR_ARTIFACT_DIR", "./artifacts")).resolve()
    upload_dir = artifact_dir / "uploads"
    diagram_dir = artifact_dir / "diagrams"
    report_dir = artifact_dir / "reports"

    for directory in (artifact_dir, upload_dir, diagram_dir, report_dir):
        directory.mkdir(parents=True, exist_ok=True)

    return Settings(
        database_url=os.getenv("REPO_TUTOR_DATABASE_URL", "sqlite:///./repotutor.db"),
        artifact_dir=artifact_dir,
        upload_dir=upload_dir,
        diagram_dir=diagram_dir,
        report_dir=report_dir,
        llm_api_key=os.getenv("LLM_API_KEY", ""),
        llm_base_url=os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"),
        llm_model=os.getenv("LLM_MODEL", "gpt-4.1-mini"),
        llm_temperature=float(os.getenv("LLM_TEMPERATURE", "0.2")),
    )


settings = get_settings()

