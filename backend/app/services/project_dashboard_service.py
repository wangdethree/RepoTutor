from __future__ import annotations


class ProjectDashboardService:
    """汇总项目 V1 闭环状态，生成可扫描的总览评分。"""

    def build(
        self,
        project: dict,
        analysis: dict | None,
        plan: dict | None,
        progress: dict,
        practice_progress: dict | None,
        interview_readiness: dict | None,
        demo_readiness: dict,
        improvement_suggestions: dict,
    ) -> dict:
        dimensions = [
            self._dimension(
                "analysis",
                "项目分析",
                self._analysis_score(analysis),
                self._analysis_detail(analysis),
                "pages/1_Project_Overview.py",
            ),
            self._dimension(
                "learning",
                "学习路线",
                progress.get("completion_rate", 0) if plan else 0,
                f"课程完成率 {progress.get('completion_rate', 0)}%。" if plan else "尚未生成学习路线。",
                "pages/3_Learning_Plan.py",
            ),
            self._dimension(
                "practice",
                "动手练习",
                (practice_progress or {}).get("completion_rate", 0),
                self._practice_detail(practice_progress),
                "pages/10_Progress.py",
            ),
            self._dimension(
                "interview",
                "面试准备",
                (interview_readiness or {}).get("readiness_score", 0),
                f"面试准备度 {(interview_readiness or {}).get('readiness_score', 0)}%。",
                "pages/13_Interview.py",
            ),
            self._dimension(
                "demo",
                "演示准备",
                demo_readiness.get("readiness_score", 0),
                f"演示准备度 {demo_readiness.get('readiness_score', 0)}%。",
                "pages/15_Demo_Readiness.py",
            ),
            self._dimension(
                "improvement",
                "工程改进",
                self._improvement_score(improvement_suggestions),
                self._improvement_detail(improvement_suggestions),
                "pages/16_Improvement_Suggestions.py",
            ),
        ]
        overall_score = round(sum(item["score"] for item in dimensions) / len(dimensions)) if dimensions else 0
        return {
            "project_id": project["id"],
            "project_name": project["name"],
            "overall_score": overall_score,
            "status": self._status(overall_score),
            "dimensions": dimensions,
            "next_actions": self._next_actions(progress, demo_readiness, improvement_suggestions),
        }

    def _dimension(self, dimension_id: str, title: str, score: int, detail: str, page: str) -> dict:
        normalized_score = max(0, min(100, round(score)))
        return {
            "id": dimension_id,
            "title": title,
            "score": normalized_score,
            "level": self._level(normalized_score),
            "detail": detail,
            "page": page,
        }

    def _analysis_score(self, analysis: dict | None) -> int:
        if not analysis:
            return 0
        summary = analysis.get("summary", {})
        score = 40
        if summary.get("python_file_count", 0):
            score += 20
        if summary.get("route_count", 0):
            score += 15
        if analysis.get("dependencies"):
            score += 15
        if analysis.get("call_edges"):
            score += 10
        return min(score, 100)

    def _analysis_detail(self, analysis: dict | None) -> str:
        if not analysis:
            return "尚未完成项目分析。"
        summary = analysis.get("summary", {})
        return (
            f"已识别 {summary.get('python_file_count', 0)} 个 Python 文件、"
            f"{summary.get('route_count', 0)} 个路由、{summary.get('model_count', 0)} 个模型。"
        )

    def _practice_detail(self, practice_progress: dict | None) -> str:
        if not practice_progress:
            return "尚未生成动手练习进度。"
        return (
            f"动手任务完成率 {practice_progress.get('completion_rate', 0)}%，"
            f"剩余 {practice_progress.get('remaining_tasks', 0)} 个任务。"
        )

    def _improvement_score(self, improvement_suggestions: dict) -> int:
        counts = improvement_suggestions.get("priority_counts", {})
        penalty = counts.get("HIGH", 0) * 18 + counts.get("MEDIUM", 0) * 10 + counts.get("LOW", 0) * 4
        return max(0, 100 - penalty)

    def _improvement_detail(self, improvement_suggestions: dict) -> str:
        counts = improvement_suggestions.get("priority_counts", {})
        return (
            f"高优先级 {counts.get('HIGH', 0)} 项，"
            f"中优先级 {counts.get('MEDIUM', 0)} 项，"
            f"低优先级 {counts.get('LOW', 0)} 项。"
        )

    def _next_actions(self, progress: dict, demo_readiness: dict, improvement_suggestions: dict) -> list[str]:
        actions: list[str] = []
        actions.extend(demo_readiness.get("next_actions", []))
        actions.extend(improvement_suggestions.get("next_actions", []))
        next_action = progress.get("next_action", "")
        if next_action:
            actions.append(self._progress_action(next_action))
        deduped: list[str] = []
        for action in actions:
            if action and action not in deduped:
                deduped.append(action)
        return deduped[:6] or ["保持当前闭环，导出报告并进行演示演练。"]

    def _progress_action(self, action: str) -> str:
        return {
            "PLAN_COMPLETED": "学习路线已完成，可以准备最终演示。",
            "REVIEW_WEAK_LESSONS": "优先复习薄弱课程。",
            "CONTINUE_NEXT_LESSON": "继续下一节课程。",
        }.get(action, action)

    def _status(self, score: int) -> str:
        if score >= 80:
            return "READY"
        if score >= 50:
            return "BUILDING"
        return "NEEDS_SETUP"

    def _level(self, score: int) -> str:
        if score >= 80:
            return "GOOD"
        if score >= 50:
            return "FAIR"
        return "WEAK"
