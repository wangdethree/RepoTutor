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
        practice_progress: dict | None = None,
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

        if practice_progress:
            lines.extend(
                [
                    "",
                    "## 动手任务进度",
                    "",
                    f"- 总任务：{practice_progress['total_tasks']}",
                    f"- 已完成：{practice_progress['completed_tasks']}",
                    f"- 待完成：{practice_progress['remaining_tasks']}",
                    f"- 完成率：{practice_progress['completion_rate']}%",
                    "",
                    "| 序号 | 课程 | 任务完成 | 待练习 |",
                    "| ---: | --- | ---: | --- |",
                ]
            )
            for lesson in practice_progress.get("lessons", []):
                pending_tasks = "、".join(lesson.get("pending_tasks", [])[:2]) or "已完成"
                lines.append(
                    "| "
                    f"{lesson['order_index']} | "
                    f"{lesson['lesson_title']} | "
                    f"{lesson['completed_task_count']}/{lesson['task_count']} | "
                    f"{pending_tasks} |"
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

    def build_lesson_report(
        self,
        project: dict,
        lesson: dict,
        analysis: dict,
        quiz: dict,
        quiz_results: list[dict] | None = None,
    ) -> str:
        """导出单节课程，内容全部来自已生成课程和静态分析事实。"""

        summary = analysis["summary"]
        lines = [
            f"# {lesson['title']}",
            "",
            f"- 生成时间：{datetime.now(timezone.utc).isoformat()}",
            f"- 项目：{project['name']}",
            f"- 原始文件：{project['original_filename']}",
            f"- 项目类型：{summary['project_type']}",
            f"- 技术栈：{', '.join(summary['tech_stack'])}",
            f"- 课程状态：{self._status_label(lesson.get('status', 'NOT_STARTED'))}",
            f"- 最近得分：{lesson.get('last_score', '-')}",
            f"- 掌握度：{lesson.get('mastery_level') or '-'}",
            "",
            "## 学习目标",
            "",
        ]
        lines.extend(self._markdown_list(lesson.get("objectives", []), empty="- 暂无学习目标。"))

        lines.extend(
            [
                "",
                "## 为什么要学",
                "",
                lesson.get("why", "本节用于建立对相关代码模块的结构化理解。"),
                "",
                "## 核心代码位置",
                "",
                "| 文件 | 行号 | 类型 | 名称 |",
                "| --- | ---: | --- | --- |",
            ]
        )
        for location in lesson.get("core_code_locations", []):
            lines.append(
                f"| `{location['file']}` | {location['line']} | {location['kind']} | {location['name']} |"
            )
        if not lesson.get("core_code_locations"):
            lines.append("| - | - | - | 暂无核心代码位置 |")

        lines.extend(["", "## 调用关系", ""])
        lines.extend(self._call_chain_lines(lesson.get("call_chains", [])))

        lines.extend(
            [
                "",
                "## 架构提示",
                "",
                lesson.get("architecture_hint", "建议结合项目架构图和依赖图阅读本节相关文件。"),
                "",
                "## 关键讲解",
                "",
            ]
        )
        lines.extend(self._markdown_list(lesson.get("explanation", []), empty="- 暂无关键讲解。"))

        lines.extend(
            [
                "",
                "## 设计原因",
                "",
                lesson.get("design_reason", "本节重点关注代码分层、职责边界和修改影响范围。"),
                "",
                "## 容易出错的地方",
                "",
            ]
        )
        lines.extend(self._markdown_list(lesson.get("pitfalls", []), empty="- 暂无易错点。"))

        lines.extend(
            [
                "",
                "## 本节总结",
                "",
                lesson.get("summary", "完成本节后，应能复述相关模块在项目中的位置和职责。"),
                "",
                "## 测验题",
                "",
            ]
        )
        lines.extend(self._quiz_lines(quiz))

        lines.extend(["", "## 最近测验结果", ""])
        lines.extend(self._quiz_result_lines(quiz_results or []))
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

    def _markdown_list(self, items: list[str], empty: str) -> list[str]:
        if not items:
            return [empty]
        return [f"- {item}" for item in items]

    def _call_chain_lines(self, call_chains: list[dict]) -> list[str]:
        if not call_chains:
            return ["- 暂无调用链。"]

        lines: list[str] = []
        for chain in call_chains:
            lines.extend([f"### {chain['title']}", ""])
            steps = " -> ".join(step["symbol"] for step in chain.get("steps", []))
            lines.extend([steps or "暂无步骤。", ""])
            if chain.get("edges"):
                lines.extend(["| 文件 | 行号 | 调用表达式 |", "| --- | ---: | --- |"])
                for edge in chain["edges"]:
                    lines.append(f"| `{edge['file']}` | {edge['line']} | `{edge['expression']}` |")
                lines.append("")
        return lines

    def _quiz_lines(self, quiz: dict) -> list[str]:
        questions = quiz.get("questions", [])
        if not questions:
            return ["- 暂无测验题。"]

        lines: list[str] = []
        for index, question in enumerate(questions, start=1):
            lines.extend(
                [
                    f"### {index}. {question['type']}",
                    "",
                    question["prompt"],
                    "",
                ]
            )
            expected_keywords = question.get("expected_keywords", [])
            if expected_keywords:
                lines.extend([f"- 考察关键词：{', '.join(expected_keywords)}", ""])
        return lines

    def _quiz_result_lines(self, quiz_results: list[dict]) -> list[str]:
        if not quiz_results:
            return ["- 暂无测验提交记录。"]

        latest = quiz_results[0]
        lines = [
            f"- 得分：{latest['score']}",
            f"- 掌握度：{latest['mastery_level']}",
            f"- 建议动作：{latest['recommended_action']}",
            f"- 反馈：{latest['feedback']}",
        ]
        if latest.get("missing_points"):
            lines.append(f"- 缺失点：{'; '.join(latest['missing_points'])}")
        if latest.get("misconceptions"):
            lines.append(f"- 误区：{'; '.join(latest['misconceptions'])}")
        return lines
