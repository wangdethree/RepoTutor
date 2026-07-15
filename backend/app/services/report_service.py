from __future__ import annotations

from datetime import datetime, timezone


class ReportService:
    """基于已验证项目事实生成 Markdown 学习报告。"""

    def build_learning_report(
        self,
        project: dict,
        profile: dict,
        analysis: dict,
        plan: dict,
        progress: dict,
        diagrams: list[dict],
    ) -> str:
        summary = analysis["summary"]
        lines = [
            f"# {project['name']} 学习报告",
            "",
            f"- 生成时间：{datetime.now(timezone.utc).isoformat()}",
            f"- 原始文件：{project['original_filename']}",
            f"- 项目类型：{summary['project_type']}",
            f"- 技术栈：{', '.join(summary['tech_stack'])}",
            f"- 难度：{summary['difficulty']}",
            "",
            "## 学习者画像",
            "",
            f"- Python 水平：{profile['python_level']}",
            f"- FastAPI 水平：{profile['fastapi_level']}",
            f"- 学习目标：{profile['learning_goal']}",
            f"- 每日时间：{profile['daily_time']}",
            "",
            "## 项目事实摘要",
            "",
            f"- 文件数：{summary['file_count']}",
            f"- Python 文件数：{summary['python_file_count']}",
            f"- 代码行数：{summary['line_count']}",
            f"- 路由数：{summary['route_count']}",
            f"- 模型数：{summary['model_count']}",
            f"- Schema 数：{summary['schema_count']}",
            "",
            "## 核心模块",
            "",
            "| 文件 | 层级 | 行数 | 重要度 |",
            "| --- | --- | ---: | ---: |",
        ]
        for file in analysis.get("files", [])[:12]:
            lines.append(f"| `{file['path']}` | {file['module_type']} | {file['line_count']} | {file['importance_score']} |")

        lines.extend(
            [
                "",
                "## 学习路线进度",
                "",
                f"- 路线：{plan['title']}",
                f"- 总课程：{progress['total_lessons']}",
                f"- 已完成：{progress['completed_lessons']}",
                f"- 需复习：{progress['needs_review_lessons']}",
                f"- 完成率：{progress['completion_rate']}%",
                f"- 下一步：{self._next_action_label(progress['next_action'])}",
                "",
                "| 序号 | 课程 | 状态 | 最近得分 |",
                "| ---: | --- | --- | ---: |",
            ]
        )
        for lesson in progress.get("lessons", []):
            score = "" if lesson.get("last_score") is None else lesson["last_score"]
            lines.append(
                f"| {lesson['order_index']} | {lesson['title']} | {self._status_label(lesson['status'])} | {score} |"
            )

        lines.extend(["", "## 架构图清单", ""])
        if diagrams:
            for diagram in diagrams:
                lines.append(f"- {diagram['title']}：{diagram['description']}（{diagram['format']}）")
        else:
            lines.append("- 尚未生成架构图。")

        lines.extend(["", "## 建议", ""])
        lines.extend(self._recommendations(progress))
        return "\n".join(lines) + "\n"

    def _status_label(self, status: str) -> str:
        return {
            "NOT_STARTED": "未开始",
            "IN_PROGRESS": "学习中",
            "NEEDS_REVIEW": "需复习",
            "COMPLETED": "已完成",
        }.get(status, status)

    def _next_action_label(self, action: str) -> str:
        return {
            "PLAN_COMPLETED": "学习路线已完成",
            "REVIEW_WEAK_LESSONS": "优先复习薄弱课程",
            "CONTINUE_NEXT_LESSON": "继续下一节课程",
        }.get(action, action)

    def _recommendations(self, progress: dict) -> list[str]:
        if progress["next_action"] == "PLAN_COMPLETED":
            return ["- 学习路线已完成，可以导出报告并准备项目讲解或面试复盘。"]
        if progress["needs_review_lessons"]:
            return ["- 先复习标记为“需复习”的课程，再继续新课程。", "- 复习后重新提交测验，分数达到 80 后再进入下一节。"]
        return ["- 按推荐的下一节继续学习。", "- 每节课完成后提交测验，让掌握度记录保持最新。"]
