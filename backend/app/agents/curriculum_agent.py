from __future__ import annotations

from app.schemas.analysis import AnalysisResult


class CurriculumAgent:
    """根据项目事实和学习者画像生成 5 到 10 节课程。"""

    def generate(self, analysis: AnalysisResult, profile: dict) -> dict:
        daily_time = profile.get("daily_time", "1 小时")
        minutes = {"30 分钟": 30, "1 小时": 45, "2 小时": 60}.get(daily_time, 45)
        core_files = analysis.summary.core_modules
        route_files = sorted({route.file_path for route in analysis.routes})
        model_files = sorted({model.file_path for model in analysis.models})
        schema_files = sorted({schema.file_path for schema in analysis.schemas})

        lessons = [
            self._lesson(
                1,
                "项目入口与启动流程",
                ["识别 FastAPI 实例", "理解启动文件和配置加载"],
                core_files[:3],
                ["Python 模块导入", "ASGI 基础"],
                minutes,
            ),
            self._lesson(
                2,
                "路由注册与请求分发",
                ["看懂 API 路由", "定位请求处理函数"],
                route_files or core_files[:4],
                ["HTTP 方法", "FastAPI 装饰器"],
                minutes,
            ),
            self._lesson(
                3,
                "请求响应 Schema 与数据校验",
                ["理解 Pydantic Schema", "区分输入输出模型"],
                schema_files or core_files[:4],
                ["类型标注", "Pydantic BaseModel"],
                minutes,
            ),
            self._lesson(
                4,
                "数据库模型与仓储层",
                ["理解 SQLAlchemy 模型", "看懂数据访问边界"],
                model_files or core_files[:4],
                ["ORM", "主键和外键"],
                minutes,
            ),
            self._lesson(
                5,
                "Service 层业务调用链",
                ["梳理路由到业务层的调用关系", "识别核心业务函数"],
                self._files_by_type(analysis, "service") or core_files[:5],
                ["函数调用", "分层设计"],
                minutes,
            ),
            self._lesson(
                6,
                "认证、配置与横切关注点",
                ["理解认证配置", "定位 JWT、Redis、日志等横切模块"],
                self._security_files(analysis) or core_files[:5],
                ["依赖注入", "配置管理"],
                minutes,
            ),
            self._lesson(
                7,
                "测试、异常处理与修改影响分析",
                ["评估修改影响范围", "找到测试和异常处理入口"],
                self._files_by_type(analysis, "test") or core_files[:5],
                ["pytest", "回归风险"],
                minutes,
            ),
        ]

        if profile.get("learning_goal") == "准备项目面试":
            lessons.append(
                self._lesson(
                    8,
                    "项目面试讲解与架构取舍",
                    ["用架构图讲清项目", "解释分层和技术选型"],
                    core_files[:6],
                    ["架构表达", "技术取舍"],
                    minutes,
                )
            )

        estimated_days = max(1, round(len(lessons) * minutes / max(self._daily_minutes(daily_time), 30)))
        return {
            "id": f"plan-{analysis.project_id}",
            "project_id": analysis.project_id,
            "title": f"{analysis.summary.project_type} 个性化学习路线",
            "estimated_days": estimated_days,
            "total_lessons": len(lessons),
            "status": "ACTIVE",
            "profile": profile,
            "lessons": lessons,
        }

    def _lesson(
        self,
        order: int,
        title: str,
        objectives: list[str],
        files: list[str],
        prerequisites: list[str],
        minutes: int,
    ) -> dict:
        return {
            "id": f"lesson-{order}",
            "title": title,
            "order_index": order,
            "objectives": objectives,
            "related_files": files[:6],
            "prerequisites": prerequisites,
            "estimated_minutes": minutes,
            "status": "NOT_STARTED",
            "completion_criteria": ["能指出相关文件", "能解释核心调用关系", "能回答本节测验"],
        }

    def _files_by_type(self, analysis: AnalysisResult, module_type: str) -> list[str]:
        return [file.path for file in analysis.files if file.module_type == module_type][:6]

    def _security_files(self, analysis: AnalysisResult) -> list[str]:
        keywords = ("auth", "jwt", "security", "config", "redis", "middleware")
        return [file.path for file in analysis.files if any(keyword in file.path.lower() for keyword in keywords)][:6]

    def _daily_minutes(self, daily_time: str) -> int:
        return {"30 分钟": 30, "1 小时": 60, "2 小时": 120}.get(daily_time, 60)

