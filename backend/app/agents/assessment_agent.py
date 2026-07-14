from __future__ import annotations

from app.graphs.learning_graph import route_next_action


class AssessmentAgent:
    """用关键词覆盖率进行 V1 测验评分，后续可接 LLM 做语义评估。"""

    def evaluate(self, quiz: dict, answers: dict[str, str]) -> dict:
        question_scores: list[int] = []
        missing_points: list[str] = []
        correct_points: list[str] = []

        for question in quiz.get("questions", []):
            answer = answers.get(question["id"], "").lower()
            keywords = [keyword.lower() for keyword in question.get("expected_keywords", [])]
            if not keywords:
                question_scores.append(100)
                continue
            matched = [keyword for keyword in keywords if keyword and keyword.lower() in answer]
            score = round(len(matched) / len(keywords) * 100)
            question_scores.append(score)
            if matched:
                correct_points.append(f"{question['id']}: 命中 {', '.join(matched)}")
            missing = [keyword for keyword in keywords if keyword not in matched]
            if missing:
                missing_points.append(f"{question['id']}: 缺少 {', '.join(missing)}")

        score = round(sum(question_scores) / max(len(question_scores), 1))
        mastery_level = self._mastery_level(score)
        return {
            "score": score,
            "mastery_level": mastery_level,
            "correct_points": correct_points,
            "missing_points": missing_points,
            "misconceptions": self._misconceptions(score),
            "feedback": self._feedback(score),
            "recommended_action": route_next_action(score),
        }

    def _mastery_level(self, score: int) -> str:
        if score >= 80:
            return "MASTERED"
        if score >= 60:
            return "PARTIAL"
        return "NEEDS_REVIEW"

    def _feedback(self, score: int) -> str:
        if score >= 80:
            return "掌握良好，可以进入下一节课程。"
        if score >= 60:
            return "已经理解主要路径，但需要复习缺失的代码定位点。"
        return "建议先回看本节课程，补充理解核心文件和调用链后再测一次。"

    def _misconceptions(self, score: int) -> list[str]:
        if score >= 80:
            return []
        if score >= 60:
            return ["可能还没有把文件位置和职责完全对应起来"]
        return ["可能混淆了路由层、业务层和数据访问层的边界"]

