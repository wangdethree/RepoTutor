from __future__ import annotations

from pathlib import Path

from app.analyzers.ast_parser import AstParser
from app.analyzers.dependency_analyzer import DependencyAnalyzer
from app.analyzers.file_scanner import FileScanner
from app.analyzers.importance_scorer import ImportanceScorer
from app.schemas.analysis import AnalysisResult, CodeFile, ProjectSummary


class AnalysisService:
    """仓库分析总入口，负责把文件扫描、AST、依赖图和评分串起来。"""

    def __init__(self) -> None:
        self.scanner = FileScanner()
        self.parser = AstParser()
        self.dependency_analyzer = DependencyAnalyzer()
        self.scorer = ImportanceScorer()

    def analyze(self, project_id: str, root_path: Path) -> AnalysisResult:
        files = self.scanner.scan(root_path)
        python_files = [file for file in files if file.path.endswith(".py")]
        source_by_path = self._read_sources(root_path, python_files)

        symbols = []
        routes = []
        models = []
        schemas = []
        imports_by_path: dict[str, list[str]] = {}

        for file in python_files:
            facts = self.parser.parse_file(file.path, source_by_path.get(file.path, ""))
            file.imports = facts.imports
            imports_by_path[file.path] = facts.imports
            symbols.extend(facts.symbols)
            routes.extend(facts.routes)
            models.extend(facts.models)
            schemas.extend(facts.schemas)

        dependencies = self.dependency_analyzer.build_edges(python_files)

        for file in files:
            if not file.path.endswith(".py"):
                file.importance_score = self._score_non_python(file)
                file.summary = self._summary_for_file(file)
                continue
            file_routes = [route for route in routes if route.file_path == file.path]
            file_symbols = [symbol for symbol in symbols if symbol.file_path == file.path]
            file.importance_score = self.scorer.score(
                file=file,
                source=source_by_path.get(file.path, ""),
                routes=file_routes,
                symbols=file_symbols,
            )
            file.summary = self._summary_for_file(file)

        summary = self._build_summary(files, python_files, routes, models, schemas, imports_by_path)
        return AnalysisResult(
            project_id=project_id,
            root_path=str(root_path),
            summary=summary,
            files=sorted(files, key=lambda item: item.importance_score, reverse=True),
            symbols=sorted(symbols, key=lambda item: (item.file_path, item.start_line)),
            routes=sorted(routes, key=lambda item: (item.file_path, item.line)),
            models=sorted(models, key=lambda item: (item.file_path, item.line)),
            schemas=sorted(schemas, key=lambda item: (item.file_path, item.line)),
            dependencies=dependencies,
        )

    def _read_sources(self, root_path: Path, files: list[CodeFile]) -> dict[str, str]:
        sources: dict[str, str] = {}
        for file in files:
            path = root_path / file.path
            try:
                sources[file.path] = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                sources[file.path] = ""
        return sources

    def _score_non_python(self, file: CodeFile) -> int:
        if file.path.endswith(("pyproject.toml", "requirements.txt")):
            return 25
        if file.path.lower().endswith("readme.md"):
            return 20
        return 10

    def _summary_for_file(self, file: CodeFile) -> str:
        labels = {
            "entrypoint": "项目入口或应用启动文件",
            "api": "API 路由层文件",
            "service": "业务服务层文件",
            "repository": "数据访问层文件",
            "model": "领域模型或数据库模型文件",
            "schema": "请求响应 Schema 文件",
            "core": "核心配置或基础设施文件",
            "test": "测试文件",
            "migration": "数据库迁移文件",
            "support": "辅助文件",
        }
        return labels.get(file.module_type, "辅助文件")

    def _build_summary(
        self,
        files: list[CodeFile],
        python_files: list[CodeFile],
        routes: list,
        models: list,
        schemas: list,
        imports_by_path: dict[str, list[str]],
    ) -> ProjectSummary:
        imports = {item for imports in imports_by_path.values() for item in imports}
        tech_stack = self._detect_tech_stack(imports, routes, files)
        project_type = "FastAPI 后端服务" if "FastAPI" in tech_stack or routes else "Python 项目"
        line_count = sum(file.line_count for file in files)
        difficulty = self._difficulty(len(python_files), len(routes), len(models), line_count)
        estimated_days = max(3, min(10, 2 + len(routes) // 4 + len(models) // 4 + len(python_files) // 20))
        core_modules = [file.path for file in sorted(files, key=lambda item: item.importance_score, reverse=True)[:8]]
        return ProjectSummary(
            project_type=project_type,
            tech_stack=tech_stack,
            file_count=len(files),
            python_file_count=len(python_files),
            line_count=line_count,
            route_count=len(routes),
            model_count=len(models),
            schema_count=len(schemas),
            difficulty=difficulty,
            estimated_days=estimated_days,
            core_modules=core_modules,
        )

    def _detect_tech_stack(self, imports: set[str], routes: list, files: list[CodeFile]) -> list[str]:
        stack: list[str] = []
        joined_imports = " ".join(imports).lower()
        file_names = " ".join(file.path.lower() for file in files)
        if "fastapi" in joined_imports or routes:
            stack.append("FastAPI")
        if "sqlalchemy" in joined_imports:
            stack.append("SQLAlchemy")
        if "pydantic" in joined_imports:
            stack.append("Pydantic")
        if "jwt" in joined_imports or "jose" in joined_imports:
            stack.append("JWT")
        if "redis" in joined_imports:
            stack.append("Redis")
        if "celery" in joined_imports:
            stack.append("Celery")
        if "pytest" in joined_imports or "/tests/" in f"/{file_names}":
            stack.append("pytest")
        if "alembic" in joined_imports or "alembic" in file_names:
            stack.append("Alembic")
        return stack or ["Python"]

    def _difficulty(self, file_count: int, route_count: int, model_count: int, line_count: int) -> str:
        score = file_count + route_count * 2 + model_count * 2 + line_count // 300
        if score < 25:
            return "入门"
        if score < 80:
            return "中等"
        return "进阶"

