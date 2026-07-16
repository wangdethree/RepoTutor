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
        improvement_suggestions: dict | None = None,
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

        if improvement_suggestions:
            lines.extend(self._improvement_suggestion_lines(improvement_suggestions))

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
        practice_tasks: dict | None = None,
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

        if practice_tasks:
            lines.extend(["", "## 动手任务", ""])
            lines.extend(self._practice_task_lines(practice_tasks))

        lines.extend(["", "## 最近测验结果", ""])
        lines.extend(self._quiz_result_lines(quiz_results or []))
        return "\n".join(lines) + "\n"

    def build_interview_report(
        self,
        project: dict,
        kit: dict,
        readiness: dict | None = None,
        improvement_suggestions: dict | None = None,
    ) -> str:
        """导出面试讲解包，便于用户离线背诵和二次整理。"""

        lines = [
            f"# {project['name']} 面试准备材料",
            "",
            f"- 生成时间：{datetime.now(timezone.utc).isoformat()}",
            f"- 原始文件：{project['original_filename']}",
            f"- 讲解包：{kit['title']}",
            f"- 事实校验：{'已通过' if kit.get('fact_checked') else '未通过'}",
            "",
            "## 1 分钟项目介绍",
            "",
            kit["elevator_pitch"],
        ]
        if readiness:
            lines.extend(self._interview_readiness_lines(readiness))
        if improvement_suggestions:
            lines.extend(self._interview_improvement_lines(improvement_suggestions))
        lines.extend(["", "## 架构讲解路径", ""])
        lines.extend(self._numbered_list(kit.get("architecture_story", []), "暂无架构讲解路径。"))
        lines.extend(["", "## 技术亮点", ""])
        lines.extend(self._markdown_list(kit.get("technical_highlights", []), "- 暂无技术亮点。"))
        lines.extend(["", "## 权衡与风险", "", "### 技术权衡", ""])
        lines.extend(self._markdown_list(kit.get("tradeoffs", []), "- 暂无技术权衡。"))
        lines.extend(["", "### 风险提示", ""])
        lines.extend(self._markdown_list(kit.get("risk_points", []), "- 暂无风险提示。"))
        lines.extend(["", "## 高频问答", ""])
        for index, question in enumerate(kit.get("questions", []), start=1):
            lines.extend(
                [
                    f"### {index}. {question['question']}",
                    "",
                    f"- 分类：{question.get('category', '-')}",
                    "",
                    "#### 回答要点",
                    "",
                ]
            )
            lines.extend(self._markdown_list(question.get("answer_points", []), "- 暂无回答要点。"))
            lines.extend(["", "#### 源码证据", ""])
            lines.extend(self._reference_lines(question.get("references", [])))
            lines.append("")
        if not kit.get("questions"):
            lines.append("- 暂无高频问答。")

        lines.extend(["", "## 核心源码证据", ""])
        lines.extend(self._reference_lines(kit.get("core_references", [])))
        lines.extend(["", "## 收尾总结", "", kit["closing_summary"]])
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

    def _numbered_list(self, items: list[str], empty: str) -> list[str]:
        if not items:
            return [empty]
        return [f"{index}. {item}" for index, item in enumerate(items, start=1)]

    def _reference_lines(self, references: list[dict]) -> list[str]:
        if not references:
            return ["- 暂无源码证据。"]
        lines = []
        for reference in references:
            lines.append(
                (
                    f"- `{reference['file']}:{reference['line']}` "
                    f"{reference.get('kind', 'source')} "
                    f"{reference.get('name', '')}"
                ).strip()
            )
        return lines

    def _interview_readiness_lines(self, readiness: dict) -> list[str]:
        breakdown = readiness.get("score_breakdown", {})
        lines = [
            "## 面试准备度",
            "",
            f"- 准备度：{readiness.get('readiness_score', 0)}%",
            f"- 状态：{self._readiness_label(readiness.get('readiness_level', ''))}",
            f"- 课程完成：{breakdown.get('course_completion', 0)}%",
            f"- 动手练习：{breakdown.get('practice_completion', 0)}%",
            f"- 测验平均分：{breakdown.get('quiz_average', 0)}%",
            f"- 高频问答：{breakdown.get('question_rehearsal', 0)}%",
            f"- 源码证据：{breakdown.get('source_evidence', 0)}%",
            "",
            "### 准备清单",
            "",
            "| 项目 | 状态 | 当前情况 | 建议动作 |",
            "| --- | --- | --- | --- |",
        ]
        for item in readiness.get("checklist", []):
            lines.append(
                "| "
                f"{item['title']} | "
                f"{self._readiness_item_status(item['status'])} | "
                f"{item['detail']} | "
                f"{item['action']} |"
            )
        if not readiness.get("checklist"):
            lines.append("| - | - | 暂无准备清单 | - |")

        lines.extend(["", "### 下一步建议", ""])
        lines.extend(self._markdown_list(readiness.get("recommended_actions", []), "- 暂无下一步建议。"))
        if readiness.get("weak_lessons"):
            lines.extend(["", "### 优先复习课程", ""])
            lines.extend(
                self._markdown_list(
                    [
                        f"{lesson['order_index']}. {lesson['title']}"
                        for lesson in readiness["weak_lessons"]
                    ],
                    "- 暂无需复习课程。",
                )
            )
        if readiness.get("pending_practice_lessons"):
            lines.extend(["", "### 待完成动手任务", ""])
            lines.extend(
                self._markdown_list(
                    [
                        f"{lesson['order_index']}. {lesson['lesson_title']}："
                        + "、".join(lesson.get("pending_tasks", [])[:3])
                        for lesson in readiness["pending_practice_lessons"]
                    ],
                    "- 暂无待完成动手任务。",
                )
            )
        lines.append("")
        return lines

    def _improvement_suggestion_lines(self, payload: dict) -> list[str]:
        suggestions = payload.get("suggestions", [])
        counts = payload.get("priority_counts", {})
        lines = [
            "",
            "## 项目改进建议",
            "",
            f"- 建议数：{payload.get('suggestion_count', len(suggestions))}",
            f"- 最高优先级：{self._priority_label(payload.get('highest_priority', 'NONE'))}",
            f"- 高优先级：{counts.get('HIGH', 0)}",
            f"- 中优先级：{counts.get('MEDIUM', 0)}",
            f"- 低优先级：{counts.get('LOW', 0)}",
            "",
            "### 下一步任务",
            "",
        ]
        lines.extend(self._markdown_list(payload.get("next_actions", []), "- 暂无下一步任务。"))
        lines.extend(
            [
                "",
                "### 建议明细",
                "",
                "| 优先级 | 分类 | 建议 | 原因 |",
                "| --- | --- | --- | --- |",
            ]
        )
        for suggestion in suggestions:
            lines.append(
                "| "
                f"{self._priority_label(suggestion['priority'])} | "
                f"{self._table_cell(suggestion['category'])} | "
                f"{self._table_cell(suggestion['title'])} | "
                f"{self._table_cell(suggestion['reason'])} |"
            )
        if not suggestions:
            lines.append("| - | - | 暂无改进建议 | - |")
        lines.extend(self._improvement_detail_lines(suggestions[:5]))
        return lines

    def _interview_improvement_lines(self, payload: dict) -> list[str]:
        suggestions = payload.get("suggestions", [])[:4]
        lines = [
            "",
            "## 项目改进讲述素材",
            "",
            f"- 最高优先级：{self._priority_label(payload.get('highest_priority', 'NONE'))}",
            "- 用途：面试中可把这些点讲成“我接下来会如何继续工程化这个项目”。",
            "",
        ]
        if not suggestions:
            lines.append("- 当前没有明显改进建议。")
            return lines

        for index, suggestion in enumerate(suggestions, start=1):
            lines.extend(
                [
                    f"### {index}. {suggestion['title']}",
                    "",
                    f"- 优先级：{self._priority_label(suggestion['priority'])}",
                    f"- 分类：{suggestion['category']}",
                    f"- 原因：{suggestion['reason']}",
                ]
            )
            if suggestion.get("interview_talking_point"):
                lines.append(f"- 面试说法：{suggestion['interview_talking_point']}")
            lines.extend(["", "#### 可讲行动", ""])
            lines.extend(self._markdown_list(suggestion.get("action_items", [])[:3], "- 暂无可讲行动。"))
            if suggestion.get("related_files"):
                files = [f"`{path}`" for path in suggestion["related_files"][:4]]
                lines.extend(["", "#### 关联文件", ""])
                lines.extend(self._markdown_list(files, "- 暂无关联文件。"))
            if suggestion.get("related_lessons"):
                lessons = [
                    f"{lesson.get('order_index', 0)}. {lesson.get('title', '')}"
                    for lesson in suggestion["related_lessons"][:3]
                ]
                lines.extend(["", "#### 关联课程", ""])
                lines.extend(self._markdown_list(lessons, "- 暂无关联课程。"))
            lines.append("")
        return lines

    def _improvement_detail_lines(self, suggestions: list[dict]) -> list[str]:
        if not suggestions:
            return []
        lines = ["", "### 可执行动作", ""]
        for suggestion in suggestions:
            lines.extend([f"#### {suggestion['title']}", ""])
            if suggestion.get("interview_talking_point"):
                lines.extend([f"面试说法：{suggestion['interview_talking_point']}", ""])
            lines.extend(self._markdown_list(suggestion.get("action_items", []), "- 暂无可执行动作。"))
            if suggestion.get("related_files"):
                files = [f"`{path}`" for path in suggestion["related_files"]]
                lines.extend(["", "关联文件："])
                lines.extend(self._markdown_list(files, "- 暂无关联文件。"))
            if suggestion.get("related_lessons"):
                lessons = [
                    f"{lesson.get('order_index', 0)}. {lesson.get('title', '')}"
                    for lesson in suggestion["related_lessons"]
                ]
                lines.extend(["", "关联课程："])
                lines.extend(self._markdown_list(lessons, "- 暂无关联课程。"))
            lines.append("")
        return lines

    def _priority_label(self, priority: str) -> str:
        return {
            "HIGH": "高",
            "MEDIUM": "中",
            "LOW": "低",
            "NONE": "无",
        }.get(priority, priority)

    def _table_cell(self, value: str) -> str:
        return str(value).replace("|", "\\|").replace("\n", " ")

    def _readiness_label(self, level: str) -> str:
        return {
            "READY": "可进入面试演练",
            "ALMOST_READY": "接近可面试",
            "NEEDS_WORK": "还需补强",
        }.get(level, level)

    def _readiness_item_status(self, status: str) -> str:
        return {
            "DONE": "已完成",
            "IN_PROGRESS": "进行中",
            "TODO": "待补齐",
        }.get(status, status)

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

    def _practice_task_lines(self, practice_tasks: dict) -> list[str]:
        tasks = practice_tasks.get("tasks", [])
        if not tasks:
            return ["- 暂无动手任务。"]

        lines = [
            f"- 任务数：{practice_tasks.get('task_count', 0)}",
            f"- 已完成：{practice_tasks.get('completed_task_count', 0)}",
            f"- 完成率：{practice_tasks.get('completion_rate', 0)}%",
            "",
        ]
        for index, task in enumerate(tasks, start=1):
            status = "已完成" if task.get("completed") else "未完成"
            lines.extend(
                [
                    f"### {index}. {task['title']}",
                    "",
                    f"- 状态：{status}",
                    f"- 类型：{task.get('task_type', '-')}",
                    f"- 预计时间：{task.get('estimated_minutes', 0)} 分钟",
                    f"- 目标：{task.get('objective', '-')}",
                    "",
                    "#### 目标文件",
                    "",
                ]
            )
            target_files = [f"`{file_path}`" for file_path in task.get("target_files", [])]
            lines.extend(self._markdown_list(target_files, "- 暂无目标文件。"))
            lines.extend(["", "#### 源码锚点", ""])
            references = [
                (
                    f"`{reference['file']}:{reference['line']}` "
                    f"{reference.get('kind', 'source')} "
                    f"{reference.get('name', '')}"
                ).strip()
                for reference in task.get("references", [])
            ]
            lines.extend(self._markdown_list(references, "- 暂无源码锚点。"))
            lines.extend(["", "#### 操作步骤", ""])
            lines.extend(self._markdown_list(task.get("steps", []), "- 暂无操作步骤。"))
            lines.extend(["", "#### 验收检查", ""])
            lines.extend(self._markdown_list(task.get("acceptance_checks", []), "- 暂无验收检查。"))
            if task.get("risk_notes"):
                lines.extend(["", "#### 注意事项", ""])
                lines.extend(self._markdown_list(task["risk_notes"], "- 暂无注意事项。"))
            lines.append("")
        return lines
