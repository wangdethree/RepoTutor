from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path

from app.schemas.analysis import CallEdge, ModelField, ModelInfo, RouteInfo, SchemaField, SchemaInfo, SymbolInfo


HTTP_METHODS = {"get", "post", "put", "patch", "delete", "options", "head"}


@dataclass
class FileAstFacts:
    imports: list[str] = field(default_factory=list)
    symbols: list[SymbolInfo] = field(default_factory=list)
    routes: list[RouteInfo] = field(default_factory=list)
    models: list[ModelInfo] = field(default_factory=list)
    schemas: list[SchemaInfo] = field(default_factory=list)
    calls: list[str] = field(default_factory=list)
    call_edges: list[CallEdge] = field(default_factory=list)


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

        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._append_function_facts(file_path, node, facts)
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
                        qualified_name=node.name,
                    )
                )
                schema = self._schema_from_class(file_path, node)
                if schema:
                    facts.schemas.append(schema)
                model = self._model_from_class(file_path, node)
                if model:
                    facts.models.append(model)
                class_attr_types = self._class_self_attribute_types(node)
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        self._append_function_facts(
                            file_path,
                            item,
                            facts,
                            parent=node.name,
                            class_attr_types=class_attr_types,
                        )

        return facts

    def _append_function_facts(
        self,
        file_path: str,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        facts: FileAstFacts,
        parent: str = "",
        class_attr_types: dict[str, str] | None = None,
    ) -> None:
        decorators = [self._unparse(item) for item in node.decorator_list]
        qualified_name = f"{parent}.{node.name}" if parent else node.name
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
                qualified_name=qualified_name,
                parent=parent,
            )
        )
        route = self._route_from_function(file_path, node, decorators)
        if route:
            facts.routes.append(route)
        facts.call_edges.extend(self._call_edges_from_function(file_path, node, qualified_name, class_attr_types or {}))

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

    def _call_edges_from_function(
        self,
        file_path: str,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        source_symbol: str,
        class_attr_types: dict[str, str],
    ) -> list[CallEdge]:
        local_types = self._local_type_bindings(node)
        edges: list[CallEdge] = []
        for child in ast.walk(node):
            if not isinstance(child, ast.Call):
                continue
            target_name = self._call_target_name(child.func, local_types, class_attr_types, source_symbol)
            if not target_name:
                continue
            edges.append(
                CallEdge(
                    source_file=file_path,
                    source_symbol=source_symbol,
                    source_line=node.lineno,
                    call_line=getattr(child, "lineno", node.lineno),
                    target_name=target_name,
                    call_expression=self._unparse(child),
                    evidence=f"{file_path}:{getattr(child, 'lineno', node.lineno)} 调用 {target_name}",
                )
            )
        return edges

    def _call_target_name(
        self,
        func: ast.AST,
        local_types: dict[str, str],
        class_attr_types: dict[str, str],
        source_symbol: str,
    ) -> str:
        if isinstance(func, ast.Name):
            return func.id
        if isinstance(func, ast.Attribute):
            if isinstance(func.value, ast.Call):
                owner = self._constructor_name_from_value(func.value)
                return f"{owner}.{func.attr}" if owner else func.attr
            base = self._attribute_key(func.value)
            if base in local_types:
                return f"{local_types[base]}.{func.attr}"
            if base in class_attr_types:
                return f"{class_attr_types[base]}.{func.attr}"
            if base == "self" and "." in source_symbol:
                return f"{source_symbol.split('.', 1)[0]}.{func.attr}"
            return func.attr
        return self._unparse(func)

    def _local_type_bindings(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> dict[str, str]:
        bindings: dict[str, str] = {}
        for child in ast.walk(node):
            if isinstance(child, ast.Assign):
                target_type = self._constructor_name_from_value(child.value)
                if not target_type:
                    continue
                for target in child.targets:
                    key = self._attribute_key(target)
                    if key:
                        bindings[key] = target_type
            if isinstance(child, ast.AnnAssign):
                target_type = self._constructor_name_from_value(child.value)
                key = self._attribute_key(child.target)
                if target_type and key:
                    bindings[key] = target_type
        return bindings

    def _class_self_attribute_types(self, node: ast.ClassDef) -> dict[str, str]:
        bindings: dict[str, str] = {}
        for child in ast.walk(node):
            if not isinstance(child, (ast.Assign, ast.AnnAssign)):
                continue
            value = child.value
            target_type = self._constructor_name_from_value(value)
            if not target_type:
                continue
            targets = child.targets if isinstance(child, ast.Assign) else [child.target]
            for target in targets:
                key = self._attribute_key(target)
                if key and key.startswith("self."):
                    bindings[key] = target_type
        return bindings

    def _constructor_name_from_value(self, value: ast.AST | None) -> str:
        if not isinstance(value, ast.Call):
            return ""
        name = self._call_name(value.func)
        if name and name[:1].isupper():
            return name
        return ""

    def _attribute_key(self, node: ast.AST | None) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            base = self._attribute_key(node.value)
            return f"{base}.{node.attr}" if base else node.attr
        return ""

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
