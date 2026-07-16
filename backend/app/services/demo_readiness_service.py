from __future__ import annotations


class DemoReadinessService:
    """汇总项目演示前需要确认的关键闭环。"""

    def build(
        self,
        project: dict,
        analysis: dict | None,
        plan: dict | None,
        diagrams: list[dict],
        progress: dict,
        practice_progress: dict | None,
        quiz_results: list[dict],
        interview_readiness: dict | None,
    ) -> dict:
        items = [
            self._analysis_item(analysis),
            self._diagram_item(diagrams),
            self._plan_item(plan),
            self._course_progress_item(progress),
            self._practice_item(practice_progress),
            self._quiz_item(quiz_results, progress),
            self._interview_item(interview_readiness),
            self._report_item(analysis, plan),
        ]
        completed = len([item for item in items if item["status"] == "DONE"])
        total = len(items)
        score = round(completed / total * 100) if total else 0
        return {
            "project_id": project["id"],
            "project_name": project["name"],
            "readiness_score": score,
            "completed_items": completed,
            "total_items": total,
            "ready_for_demo": score >= 80,
            "items": items,
            "next_actions": [item["action"] for item in items if item["status"] != "DONE"][:4],
        }

    def _analysis_item(self, analysis: dict | None) -> dict:
        summary = (analysis or {}).get("summary", {})
        return self._item(
            "analysis",
            "项目静态分析",
            bool(analysis),
            f"已识别 {summary.get('python_file_count', 0)} 个 Python 文件、{summary.get('route_count', 0)} 个路由。",
            "先完成项目导入和静态分析。",
            "pages/1_Project_Overview.py",
        )

    def _diagram_item(self, diagrams: list[dict]) -> dict:
        return self._item(
            "diagrams",
            "架构图生成",
            len(diagrams) >= 3,
            f"当前已生成 {len(diagrams)} 张架构图。",
            "进入架构图页面生成分层图、组件图、ER 图和调用图。",
            "pages/2_Architecture_Diagrams.py",
            started=bool(diagrams),
        )

    def _plan_item(self, plan: dict | None) -> dict:
        lessons = (plan or {}).get("lessons", [])
        return self._item(
            "learning_plan",
            "学习路线",
            bool(lessons),
            f"当前学习路线包含 {len(lessons)} 节课程。",
            "生成学习路线，确保演示时能从课程入口进入。",
            "pages/3_Learning_Plan.py",
        )

    def _course_progress_item(self, progress: dict) -> dict:
        completion_rate = progress.get("completion_rate", 0)
        return self._item(
            "course_progress",
            "课程学习进度",
            completion_rate >= 60,
            f"当前课程完成率 {completion_rate}%。",
            "至少完成 1 到 2 节核心课程，并提交测验形成进度记录。",
            "pages/10_Progress.py",
            started=completion_rate > 0,
        )

    def _practice_item(self, practice_progress: dict | None) -> dict:
        completion_rate = (practice_progress or {}).get("completion_rate", 0)
        total_tasks = (practice_progress or {}).get("total_tasks", 0)
        return self._item(
            "practice_tasks",
            "动手任务闭环",
            total_tasks > 0 and completion_rate >= 60,
            f"当前动手任务完成率 {completion_rate}%，任务数 {total_tasks}。",
            "完成课程页中的源码定位、调用链复述和改动影响演练。",
            "pages/4_Lesson_Quiz.py",
            started=completion_rate > 0,
        )

    def _quiz_item(self, quiz_results: list[dict], progress: dict) -> dict:
        average_score = self._average_score(quiz_results)
        return self._item(
            "quiz_review",
            "测验与复习记录",
            bool(quiz_results) and average_score >= 60 and progress.get("needs_review_lessons", 0) <= 1,
            f"当前测验次数 {len(quiz_results)}，平均分 {average_score}。",
            "至少提交一次课程测验，并通过复习中心处理低分记录。",
            "pages/12_Review.py",
            started=bool(quiz_results),
        )

    def _interview_item(self, interview_readiness: dict | None) -> dict:
        score = (interview_readiness or {}).get("readiness_score", 0)
        return self._item(
            "interview",
            "面试准备材料",
            score >= 60,
            f"当前面试准备度 {score}%。",
            "进入面试准备页，标记高频问答掌握状态并导出面试材料。",
            "pages/13_Interview.py",
            started=score > 0,
        )

    def _report_item(self, analysis: dict | None, plan: dict | None) -> dict:
        return self._item(
            "reports",
            "报告导出",
            bool(analysis and plan),
            "项目学习报告、课程报告和面试材料均可导出为 Markdown。",
            "进入报告导出页，下载项目报告和单节课程报告。",
            "pages/11_Reports.py",
        )

    def _item(
        self,
        item_id: str,
        title: str,
        done: bool,
        detail: str,
        action: str,
        page: str,
        started: bool = False,
    ) -> dict:
        if done:
            status = "DONE"
        elif started:
            status = "IN_PROGRESS"
        else:
            status = "TODO"
        return {
            "id": item_id,
            "title": title,
            "status": status,
            "detail": detail,
            "action": action,
            "page": page,
        }

    def _average_score(self, quiz_results: list[dict]) -> int:
        if not quiz_results:
            return 0
        return round(sum(result.get("score", 0) for result in quiz_results) / len(quiz_results))
