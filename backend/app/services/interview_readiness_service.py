from __future__ import annotations


class InterviewReadinessService:
    """根据学习闭环数据计算项目面试准备度。"""

    def build(
        self,
        progress: dict,
        practice_progress: dict,
        quiz_results: list[dict],
        interview_kit: dict,
    ) -> dict:
        quiz_average = self._quiz_average(quiz_results)
        evidence_score = min(
            100,
            round(len(interview_kit.get("core_references", [])) / 6 * 100),
        )
        question_rehearsal_score = interview_kit.get("question_mastery_rate", 0)
        review_penalty_score = max(0, 100 - progress.get("needs_review_lessons", 0) * 20)
        score = round(
            progress.get("completion_rate", 0) * 0.25
            + practice_progress.get("completion_rate", 0) * 0.20
            + quiz_average * 0.20
            + question_rehearsal_score * 0.15
            + evidence_score * 0.10
            + review_penalty_score * 0.10
        )
        checklist = self._checklist(progress, practice_progress, quiz_results, interview_kit)
        blockers = [item for item in checklist if item["status"] == "TODO"]
        return {
            "readiness_score": score,
            "readiness_level": self._readiness_level(score, blockers),
            "score_breakdown": {
                "course_completion": progress.get("completion_rate", 0),
                "practice_completion": practice_progress.get("completion_rate", 0),
                "quiz_average": quiz_average,
                "question_rehearsal": question_rehearsal_score,
                "source_evidence": evidence_score,
                "review_risk": review_penalty_score,
            },
            "checklist": checklist,
            "blockers": blockers,
            "recommended_actions": self._recommended_actions(checklist),
            "weak_lessons": [
                lesson
                for lesson in progress.get("lessons", [])
                if lesson.get("status") == "NEEDS_REVIEW"
            ][:5],
            "pending_practice_lessons": [
                lesson
                for lesson in practice_progress.get("lessons", [])
                if lesson.get("pending_tasks")
            ][:5],
        }

    def _quiz_average(self, quiz_results: list[dict]) -> int:
        if not quiz_results:
            return 0
        return round(sum(result.get("score", 0) for result in quiz_results) / len(quiz_results))

    def _checklist(
        self,
        progress: dict,
        practice_progress: dict,
        quiz_results: list[dict],
        interview_kit: dict,
    ) -> list[dict]:
        return [
            self._item(
                "course_progress",
                "课程路线完成度",
                progress.get("completion_rate", 0) >= 80,
                progress.get("completion_rate", 0) > 0,
                f"当前课程完成率 {progress.get('completion_rate', 0)}%。",
                "优先完成核心课程，并把需复习课程重新测到 80 分以上。",
            ),
            self._item(
                "practice_progress",
                "动手任务完成度",
                practice_progress.get("completion_rate", 0) >= 80,
                practice_progress.get("completion_rate", 0) > 0,
                f"当前动手任务完成率 {practice_progress.get('completion_rate', 0)}%。",
                "补齐源码定位、调用链复述和改动影响演练。",
            ),
            self._item(
                "quiz_evidence",
                "测验成绩证据",
                bool(quiz_results) and self._quiz_average(quiz_results) >= 80,
                bool(quiz_results),
                f"当前测验平均分 {self._quiz_average(quiz_results)}%。",
                "至少完成一次测验，并把平均分提升到 80 分以上。",
            ),
            self._item(
                "source_evidence",
                "源码证据储备",
                len(interview_kit.get("core_references", [])) >= 6,
                len(interview_kit.get("core_references", [])) >= 3,
                f"当前可引用源码证据 {len(interview_kit.get('core_references', []))} 条。",
                "准备至少 6 条能讲清路径、模型或 Schema 的源码证据。",
            ),
            self._item(
                "question_rehearsal",
                "高频问答演练",
                interview_kit.get("question_mastery_rate", 0) >= 80,
                interview_kit.get("question_mastery_rate", 0) > 0,
                f"当前高频问答掌握率 {interview_kit.get('question_mastery_rate', 0)}%。",
                "逐题口头演练高频问答，并标记已掌握的问题。",
            ),
            self._item(
                "review_risk",
                "薄弱课程风险",
                progress.get("needs_review_lessons", 0) == 0,
                progress.get("needs_review_lessons", 0) <= 1,
                f"当前需复习课程 {progress.get('needs_review_lessons', 0)} 节。",
                "先处理标记为需复习的课程，再准备最终面试讲述。",
            ),
        ]

    def _item(
        self,
        item_id: str,
        title: str,
        done: bool,
        started: bool,
        detail: str,
        action: str,
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
        }

    def _readiness_level(self, score: int, blockers: list[dict]) -> str:
        if score >= 80 and not blockers:
            return "READY"
        if score >= 60:
            return "ALMOST_READY"
        return "NEEDS_WORK"

    def _recommended_actions(self, checklist: list[dict]) -> list[str]:
        actions = [item["action"] for item in checklist if item["status"] != "DONE"]
        return actions[:4] or ["保持当前节奏，导出面试材料并进行口头演练。"]
