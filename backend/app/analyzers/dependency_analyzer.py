from __future__ import annotations

from pathlib import Path

from app.schemas.analysis import CodeFile, DependencyEdge


class DependencyAnalyzer:
    """将 import 语句解析为仓库内文件级依赖边。"""

    def build_edges(self, files: list[CodeFile]) -> list[DependencyEdge]:
        module_index = self._build_module_index(files)
        edges: list[DependencyEdge] = []
        imported_counter: dict[str, int] = {file.path: 0 for file in files}

        for file in files:
            for import_name in file.imports:
                target = self._resolve_import(import_name, module_index)
                if not target or target == file.path:
                    continue
                imported_counter[target] += 1
                edges.append(
                    DependencyEdge(
                        source=file.path,
                        target=target,
                        edge_type="imports",
                        confidence=1.0,
                        evidence=f"{file.path} imports {import_name}",
                    )
                )

        for file in files:
            file.imported_by = imported_counter.get(file.path, 0)

        unique: dict[tuple[str, str], DependencyEdge] = {}
        for edge in edges:
            unique[(edge.source, edge.target)] = edge
        return list(unique.values())

    def _build_module_index(self, files: list[CodeFile]) -> dict[str, str]:
        index: dict[str, str] = {}
        for file in files:
            if not file.path.endswith(".py"):
                continue
            without_suffix = file.path[:-3]
            dotted = without_suffix.replace("/", ".")
            variants = {dotted}
            if dotted.endswith(".__init__"):
                variants.add(dotted.removesuffix(".__init__"))
            parts = dotted.split(".")
            for idx in range(len(parts)):
                variants.add(".".join(parts[idx:]))
            for module in variants:
                if module:
                    index[module] = file.path
        return index

    def _resolve_import(self, import_name: str, module_index: dict[str, str]) -> str | None:
        normalized = import_name.lstrip(".")
        if normalized in module_index:
            return module_index[normalized]
        parts = normalized.split(".")
        while parts:
            candidate = ".".join(parts)
            if candidate in module_index:
                return module_index[candidate]
            parts.pop()
        return None

