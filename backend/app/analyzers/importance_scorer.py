from __future__ import annotations

from app.schemas.analysis import CodeFile, RouteInfo, SymbolInfo


class ImportanceScorer:
    """按项目书中的可解释规则给文件打分。"""

    def score(self, file: CodeFile, source: str, routes: list[RouteInfo], symbols: list[SymbolInfo]) -> int:
        score = 30
        if "FastAPI(" in source:
            score += 30
        if routes:
            score += 15
        score += 2 * file.imported_by

        module_bonus = {
            "service": 8,
            "repository": 6,
            "model": 6,
            "core": 5,
            "api": 10,
            "entrypoint": 12,
            "schema": 4,
            "test": -5,
            "migration": -15,
        }
        score += module_bonus.get(file.module_type, 0)

        has_behavior = any(symbol.file_path == file.path for symbol in symbols)
        if not has_behavior and file.line_count < 25:
            score -= 10

        return max(score, 0)

