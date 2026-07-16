from __future__ import annotations


class IncrementalLearningService:
    """把一次代码变更转成增量学习和复习建议。"""

    def build(self, project: dict, impact: dict, pr_review: dict) -> dict:
        recommendations = self._recommendations(impact, pr_review)
        return {
            "project_id": project["id"],
            "project_name": project["name"],
            "title": f"{project['name']} 增量学习建议",
            "change_summary": pr_review.get("change_summary", ""),
            "risk_level": pr_review.get("risk_level", "LOW"),
            "recommended_lessons": self._recommended_lessons(impact),
            "source_checkpoints": self._source_checkpoints(impact),
            "practice_tasks": self._practice_tasks(impact),
            "questions_to_ask": self._questions_to_ask(impact),
            "next_steps": recommendations,
        }

    def _recommended_lessons(self, impact: dict) -> list[dict]:
        lessons = []
        for lesson in impact.get("related_lessons", []):
            lessons.append(
                {
                    "lesson_id": lesson["id"],
                    "title": lesson["title"],
                    "order_index": lesson["order_index"],
                    "matched_files": lesson.get("matched_files", []),
                    "reason": "本次 diff 命中该课程关联源码，建议回到课程重新复述调用链。",
                }
            )
        return lessons

    def _source_checkpoints(self, impact: dict) -> list[dict]:
        checkpoints = []
        for file in impact.get("changed_files", []):
            checkpoints.append(
                {
                    "file": file["path"],
                    "checkpoint": "先阅读变更文件，确认新增逻辑、删除逻辑和接口边界。",
                    "kind": "changed",
                }
            )
        for file in impact.get("impacted_files", [])[:6]:
            checkpoints.append(
                {
                    "file": file["path"],
                    "checkpoint": "检查受影响调用方是否仍然满足原有契约。",
                    "kind": "impacted",
                }
            )
        return checkpoints

    def _practice_tasks(self, impact: dict) -> list[dict]:
        tasks = [
            {
                "title": "复述变更意图",
                "objective": "用 3 句话说明这次 diff 为什么改、改了哪里、影响哪里。",
                "acceptance": "能说出变更文件、至少 1 个受影响文件和回归测试重点。",
            }
        ]
        if impact.get("related_routes"):
            tasks.append(
                {
                    "title": "回归路由调用链",
                    "objective": "从命中的 API 路由出发，复述请求进入 service/repository 的路径。",
                    "acceptance": "能指出路由、处理函数和至少 1 个业务调用点。",
                }
            )
        if impact.get("related_lessons"):
            tasks.append(
                {
                    "title": "重做相关课程测验",
                    "objective": "回到命中的课程重新测验，确认理解修改影响。",
                    "acceptance": "相关课程测验达到 80 分以上。",
                }
            )
        return tasks

    def _questions_to_ask(self, impact: dict) -> list[str]:
        questions = [
            "这次修改解决了什么问题？有没有改变接口契约？",
            "如果只看被修改文件，会漏掉哪些受影响模块？",
        ]
        if impact.get("related_routes"):
            questions.append("命中的路由需要补哪些请求成功、异常和权限边界测试？")
        if impact.get("outgoing_dependencies"):
            questions.append("变更文件依赖的下游模块是否需要同步调整？")
        if impact.get("summary", {}).get("risk_level") == "HIGH":
            questions.append("这次变更为什么是高风险？合并前必须补哪类回归测试？")
        return questions

    def _recommendations(self, impact: dict, pr_review: dict) -> list[str]:
        steps = []
        if impact.get("related_lessons"):
            steps.append("先复习命中的学习课程，再重新解释这次 diff。")
        if impact.get("related_routes"):
            steps.append("沿着命中的 API 路由做一次端到端调用链走读。")
        steps.extend(pr_review.get("test_plan", [])[:2])
        return steps[:5] or ["先确认 diff 路径属于当前项目，再做基础静态检查。"]
