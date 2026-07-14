from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path

from app.schemas.analysis import ModelField, ModelInfo, RouteInfo, SchemaField, SchemaInfo, SymbolInfo


HTTP_METHODS = {"get", "post", "put", "patch", "delete", "options", "head"}


@dataclass
class FileAstFacts:
    imports: list[str] = field(default_factory=list)
    symbols: list[SymbolInfo] = field(default_factory=list)
    routes: list[RouteInfo] = field(default_factory=list)
    models: list[ModelInfo] = field(default_factory=list)
    schemas: list[SchemaInfo] = field(default_factory=list)
    calls: list[str] = field(default_factory=list)


class AstParser:
    """基于 Python AST 提取代码事实，避免导入或执行上传项目。"""

    def parse_file(self, file_path: str, source: str) -> FileAstFacts:
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return FileAstFacts()

        facts = FileAstFacts()
        facts.imports = self._extract_imports(tree)
        facts.calls = self._extract_calls(tree)

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                decorators = [self._unparse(item) for item in node.decorator_list]
                facts.symbols.append(
                    SymbolInfo(
                        file_path=file_path,
                        name=node.name,
                        symbol_type="async_function" if isinstance(node, ast.AsyncFunctionDef) else "function",
                        start_line=node.lineno,
                        end_line=getattr(node, "end_lineno", node.lineno),
                        signature=self._signature(node),
                        docstring=ast.get_docstring(node),
                        decorators=decorators,
                    )
                )
                route = self._route_from_function(file_path, node, decorators)
                if route:
                    facts.routes.append(route)

            if isinstance(node, ast.ClassDef):
                decorators = [self._unparse(item) for item in node.decorator_list]
                facts.symbols.append(
                    SymbolInfo(
                        file_path=file_path,
                        name=node.name,
                        symbol_type="class",
                        start_line=node.lineno,
                        end_line=getattr(node, "end_lineno", node.lineno),
                        signature=node.name,
                        docstring=ast.get_docstring(node),
                        decorators=decorators,
                    )
                )
                schema = self._schema_from_class(file_path, node)
                if schema:
                    facts.schemas.append(schema)
                model = self._model_from_class(file_path, node)
                if model:
                    facts.models.append(model)

        return facts

    def _extract_imports(self, tree: ast.AST) -> list[str]:
        imports: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                prefix = "." * node.level
                module = node.module or ""
                imports.append(prefix + module)
                for alias in node.names:
                    if module:
                        imports.append(f"{prefix}{module}.{alias.name}")
                    else:
                        imports.append(prefix + alias.name)
        return sorted(set(item for item in imports if item))

    def _extract_calls(self, tree: ast.AST) -> list[str]:
        calls: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                calls.append(self._call_name(node.func))
        return sorted(set(item for item in calls if item))

    def _route_from_function(
        self,
        file_path: str,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        decorators: list[str],
    ) -> RouteInfo | None:
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue
            method = self._decorator_http_method(decorator.func)
            if not method:
                continue
            route_path = self._first_string_arg(decorator) or "/"
            return RouteInfo(
                file_path=file_path,
                http_method=method.upper(),
                path=route_path,
                handler=node.name,
                line=node.lineno,
                response_model=self._keyword_value(decorator, "response_model"),
                dependencies=self._dependencies_from_keywords(decorator),
            )
        return None

    def _decorator_http_method(self, func: ast.AST) -> str | None:
        if isinstance(func, ast.Attribute) and func.attr.lower() in HTTP_METHODS:
            return func.attr.lower()
        if isinstance(func, ast.Name) and func.id.lower() in HTTP_METHODS:
            return func.id.lower()
        return None

    def _schema_from_class(self, file_path: str, node: ast.ClassDef) -> SchemaInfo | None:
        bases = [self._unparse(base) for base in node.bases]
        if not any("BaseModel" in base for base in bases):
            return None
        fields: list[SchemaField] = []
        for item in node.body:
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                default = self._unparse(item.value) if item.value else None
                fields.append(
                    SchemaField(
                        name=item.target.id,
                        field_type=self._unparse(item.annotation),
                        required=item.value is None,
                        default=default,
                    )
                )
        return SchemaInfo(file_path=file_path, class_name=node.name, line=node.lineno, fields=fields)

    def _model_from_class(self, file_path: str, node: ast.ClassDef) -> ModelInfo | None:
        bases = [self._unparse(base) for base in node.bases]
        body_text = " ".join(self._unparse(item) for item in node.body)
        looks_like_model = any(base.endswith("Base") or "SQLModel" in base for base in bases)
        looks_like_model = looks_like_model or "Column(" in body_text or "mapped_column(" in body_text
        if not looks_like_model or any("BaseModel" in base for base in bases):
            return None

        table_name: str | None = None
        fields: list[ModelField] = []
        relationships: list[str] = []
        for item in node.body:
            if isinstance(item, ast.Assign):
                names = [target.id for target in item.targets if isinstance(target, ast.Name)]
                if "__tablename__" in names and isinstance(item.value, ast.Constant):
                    table_name = str(item.value.value)
                for name in names:
                    field = self._model_field_from_value(name, item.value)
                    if field:
                        fields.append(field)
                    if self._call_name_from_value(item.value) == "relationship":
                        relationships.append(name)
            elif isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                field = self._model_field_from_value(item.target.id, item.value)
                if field:
                    if not field.field_type and item.annotation:
                        field.field_type = self._unparse(item.annotation)
                    fields.append(field)

        if not table_name and not fields and not relationships:
            return None

        return ModelInfo(
            file_path=file_path,
            class_name=node.name,
            table_name=table_name,
            line=node.lineno,
            fields=fields,
            relationships=relationships,
        )

    def _model_field_from_value(self, name: str, value: ast.AST | None) -> ModelField | None:
        if value is None:
            return None
        call_name = self._call_name_from_value(value)
        if call_name not in {"Column", "mapped_column", "relationship"}:
            return None
        value_text = self._unparse(value)
        if call_name == "relationship":
            return ModelField(name=name, field_type="relationship")
        return ModelField(
            name=name,
            field_type=self._first_call_arg(value) or "Column",
            is_primary_key="primary_key=True" in value_text,
            foreign_key=self._foreign_key(value_text),
            default=self._keyword_value(value, "default") if isinstance(value, ast.Call) else None,
        )

    def _signature(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
        args = [arg.arg for arg in node.args.args]
        returns = f" -> {self._unparse(node.returns)}" if node.returns else ""
        return f"{node.name}({', '.join(args)}){returns}"

    def _dependencies_from_keywords(self, call: ast.Call) -> list[str]:
        dependencies: list[str] = []
        for keyword in call.keywords:
            if keyword.arg in {"dependencies", "dependency"}:
                dependencies.append(self._unparse(keyword.value))
        return dependencies

    def _keyword_value(self, call: ast.Call | ast.AST, key: str) -> str | None:
        if not isinstance(call, ast.Call):
            return None
        for keyword in call.keywords:
            if keyword.arg == key:
                return self._unparse(keyword.value)
        return None

    def _first_string_arg(self, call: ast.Call) -> str | None:
        if call.args and isinstance(call.args[0], ast.Constant) and isinstance(call.args[0].value, str):
            return call.args[0].value
        return None

    def _first_call_arg(self, value: ast.AST) -> str | None:
        if isinstance(value, ast.Call) and value.args:
            return self._unparse(value.args[0])
        return None

    def _foreign_key(self, value_text: str) -> str | None:
        marker = "ForeignKey("
        if marker not in value_text:
            return None
        tail = value_text.split(marker, 1)[1]
        return tail.split(")", 1)[0].strip("'\"")

    def _call_name_from_value(self, value: ast.AST | None) -> str:
        if isinstance(value, ast.Call):
            return self._call_name(value.func)
        return ""

    def _call_name(self, node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return node.attr
        return self._unparse(node)

    def _unparse(self, node: ast.AST | None) -> str:
        if node is None:
            return ""
        try:
            return ast.unparse(node)
        except Exception:
            return ""
