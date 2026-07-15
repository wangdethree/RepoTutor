from __future__ import annotations

from app.llm.validators import CodeReferenceValidator
from app.schemas.analysis import AnalysisResult


class InterviewAgent:
    """根据项目事实生成面试准备材料。"""

    def generate(self, analysis: AnalysisResult, profile: dict | None = None, progress: dict | None = None) -> dict:
        profile = profile or {}
        progress = progress or {}
        references = CodeReferenceValidator(analysis).validate_many(self._core_references(analysis))
        payload = {
            "project_id": analysis.project_id,
            "title": f"{analysis.summary.project_type} 面试讲解包",
            "elevator_pitch": self._elevator_pitch(analysis, profile),
            "architecture_story": self._architecture_story(analysis),
            "technical_highlights": self._technical_highlights(analysis),
            "tradeoffs": self._tradeoffs(analysis),
            "risk_points": self._risk_points(analysis, progress),
            "questions": self._questions(analysis, references),
            "closing_summary": self._closing_summary(analysis),
            "core_references": references,
            "fact_checked": True,
        }
        return payload

    def _elevator_pitch(self, analysis: AnalysisResult, profile: dict) -> str:
        goal = profile.get("learning_goal", "理解项目结构")
        stack = "、".join(analysis.summary.tech_stack)
        return (
            f"这是一个{analysis.summary.project_type}，技术栈主要包括{stack}。"
            f"项目包含 {analysis.summary.route_count} 个 API 路由、{analysis.summary.model_count} 个数据模型，"
            f"适合围绕“{goal}”来讲：先说明入口和路由，再解释业务层、数据层和测试如何支撑核心流程。"
        )

    def _architecture_story(self, analysis: AnalysisResult) -> list[str]:
        story = [
            "从入口文件开始讲应用如何创建、加载配置并挂载路由。",
            "再按 API -> Service -> Repository/Model 的方向说明请求如何进入业务逻辑和数据访问。",
            "最后用 Schema、测试和配置模块说明项目如何控制输入输出、回归风险和运行环境。",
        ]
        if analysis.routes:
            first = analysis.routes[0]
            story.append(f"可以用 {first.http_method} {first.path} 作为示例请求，追到处理函数 {first.handler}。")
        return story

    def _technical_highlights(self, analysis: AnalysisResult) -> list[str]:
        highlights = [
            f"静态分析识别出 {analysis.summary.python_file_count} 个 Python 文件，可用文件重要度解释阅读顺序。",
            f"项目显式包含 {analysis.summary.schema_count} 个 Schema，有利于讲清请求响应边界。",
        ]
        if analysis.dependencies:
            highlights.append("依赖图来自 import 关系，适合解释修改影响范围。")
        if "JWT" in analysis.summary.tech_stack:
            highlights.append("认证相关逻辑可作为安全设计和横切关注点的讲解入口。")
        if "pytest" in analysis.summary.tech_stack:
            highlights.append("测试文件可用于说明回归验证策略。")
        return highlights

    def _tradeoffs(self, analysis: AnalysisResult) -> list[str]:
        tradeoffs = [
            "分层结构提升可维护性，但需要额外说明每一层的职责边界。",
            "静态分析能快速定位事实，但调用链深处仍需要结合源码上下文确认。",
        ]
        if analysis.summary.model_count:
            tradeoffs.append("数据模型集中定义业务对象，修改字段时需要同步检查 Schema、Repository、Service 和测试。")
        return tradeoffs

    def _risk_points(self, analysis: AnalysisResult, progress: dict) -> list[str]:
        risks = [
            "面试中不要把 import 依赖直接说成运行时调用关系。",
            "讲 API 流程时要同时引用路由、处理函数和相关数据结构，避免只背文件名。",
        ]
        if progress.get("needs_review_lessons"):
            risks.append("学习进度中仍有需复习课程，面试前应优先补齐这些薄弱点。")
        if not analysis.routes:
            risks.append("未识别到明确 API 路由，需要准备如何解释项目入口和脚本运行方式。")
        return risks

    def _questions(self, analysis: AnalysisResult, references: list[dict]) -> list[dict]:
        first_route = analysis.routes[0] if analysis.routes else None
        route_question = (
            f"请讲一下 {first_route.http_method} {first_route.path} 从路由到业务逻辑的大致路径？"
            if first_route
            else "请讲一下项目的主要执行入口和核心调用路径？"
        )
        return [
            {
                "id": "interview-q1",
                "category": "项目概览",
                "question": "请用 1 分钟介绍这个项目。",
                "answer_points": [
                    f"项目类型是 {analysis.summary.project_type}",
                    f"核心技术栈是 {', '.join(analysis.summary.tech_stack)}",
                    f"规模上有 {analysis.summary.file_count} 个文件和 {analysis.summary.line_count} 行代码",
                ],
                "references": references[:3],
            },
            {
                "id": "interview-q2",
                "category": "架构理解",
                "question": route_question,
                "answer_points": [
                    "先定位入口和路由注册",
                    "再说明请求处理函数如何调用业务层",
                    "最后补充数据模型、Schema 或 Repository 的角色",
                ],
                "references": references[:5],
            },
            {
                "id": "interview-q3",
                "category": "修改影响",
                "question": "如果要修改一个模型字段，你会检查哪些地方？",
                "answer_points": [
                    "检查 SQLAlchemy Model 或领域模型",
                    "同步检查 Pydantic Schema、Repository、Service、API 和测试",
                    "用依赖图确认 import 影响范围",
                ],
                "references": references[:8],
            },
            {
                "id": "interview-q4",
                "category": "风险与质量",
                "question": "这个项目有哪些容易出错的地方，如何验证修改？",
                "answer_points": [
                    "区分静态依赖和真实运行时调用",
                    "优先针对路由、Service、Repository、模型字段补测试",
                    "用课程测验和复习记录暴露薄弱知识点",
                ],
                "references": references[:8],
            },
        ]

    def _closing_summary(self, analysis: AnalysisResult) -> str:
        return (
            "面试讲解时建议按“项目目标 -> 技术栈 -> 入口路由 -> 分层职责 -> 数据模型 -> 测试与风险”展开，"
            f"并至少引用 {min(3, len(analysis.summary.core_modules))} 个真实核心文件作为证据。"
        )

    def _core_references(self, analysis: AnalysisResult) -> list[dict]:
        references: list[dict] = []
        for route in analysis.routes[:5]:
            references.append(
                {
                    "file": route.file_path,
                    "line": route.line,
                    "name": f"{route.http_method} {route.path} -> {route.handler}",
                    "kind": "route",
                }
            )
        for model in analysis.models[:4]:
            references.append(
                {
                    "file": model.file_path,
                    "line": model.line,
                    "name": model.class_name,
                    "kind": "model",
                }
            )
        for schema in analysis.schemas[:4]:
            references.append(
                {
                    "file": schema.file_path,
                    "line": schema.line,
                    "name": schema.class_name,
                    "kind": "schema",
                }
            )
        for file_path in analysis.summary.core_modules[:4]:
            if not any(reference["file"] == file_path for reference in references):
                references.append({"file": file_path, "line": 1, "name": "核心模块", "kind": "file"})
        return references[:12]
