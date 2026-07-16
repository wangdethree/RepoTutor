from __future__ import annotations


class PRReviewService:
    """把 diff 影响分析转成可执行的 PR 讲解和评审材料。"""

    def build(self, project: dict, diff_text: str, impact: dict) -> dict:
        stats = self._line_stats(diff_text)
        summary = impact.get("summary", {})
        risk_level = summary.get("risk_level", "LOW")
        return {
            "project_id": project["id"],
            "project_name": project["name"],
            "title": f"{project['name']} PR 讲解包",
            "risk_level": risk_level,
            "change_summary": self._change_summary(stats, impact),
            "line_stats": stats,
            "affected_surface": self._affected_surface(impact),
            "review_checklist": self._review_checklist(impact),
            "test_plan": self._test_plan(impact),
            "learning_impacts": self._learning_impacts(impact),
            "interview_talking_points": self._interview_talking_points(impact),
            "merge_advice": self._merge_advice(risk_level, impact),
        }

    def _line_stats(self, diff_text: str) -> dict:
        additions = 0
        deletions = 0
        for line in diff_text.splitlines():
            if line.startswith(("+++", "---")):
                continue
            if line.startswith("+"):
                additions += 1
            elif line.startswith("-"):
                deletions += 1
        return {
            "additions": additions,
            "deletions": deletions,
            "total_changed_lines": additions + deletions,
        }

    def _change_summary(self, stats: dict, impact: dict) -> str:
        summary = impact.get("summary", {})
        return (
            f"本次变更涉及 {summary.get('changed_file_count', 0)} 个文件，"
            f"新增 {stats['additions']} 行、删除 {stats['deletions']} 行，"
            f"静态分析识别到 {summary.get('impacted_file_count', 0)} 个受影响文件。"
        )

    def _affected_surface(self, impact: dict) -> dict:
        return {
            "changed_files": [item["path"] for item in impact.get("changed_files", [])],
            "impacted_files": [item["path"] for item in impact.get("impacted_files", [])],
            "routes": [
                f"{route['method']} {route['path']}"
                for route in impact.get("related_routes", [])
            ],
            "lessons": [
                f"{lesson['order_index']}. {lesson['title']}"
                for lesson in impact.get("related_lessons", [])
            ],
        }

    def _review_checklist(self, impact: dict) -> list[dict]:
        items = [
            self._check_item(
                "changed_files",
                "确认变更文件是否属于本项目静态分析范围",
                impact.get("summary", {}).get("unknown_changed_file_count", 0) == 0,
                "如果存在未知文件，先重新分析项目或确认 diff 路径是否正确。",
            ),
            self._check_item(
                "routes",
                "回归相关 API 路由",
                not impact.get("related_routes"),
                "命中路由时，需要确认请求参数、权限、业务调用和响应结构。",
            ),
            self._check_item(
                "dependencies",
                "检查依赖传播影响",
                not impact.get("impacted_files"),
                "存在受影响文件时，需要确认调用方和同业务命名模块是否仍然兼容。",
            ),
            self._check_item(
                "tests",
                "补充或运行相关测试",
                impact.get("summary", {}).get("risk_level") == "LOW",
                "中高风险变更提交前至少补充核心路径或回归测试。",
            ),
        ]
        return items

    def _check_item(self, item_id: str, title: str, passed: bool, action: str) -> dict:
        return {
            "id": item_id,
            "title": title,
            "status": "PASS" if passed else "NEEDS_CHECK",
            "action": action,
        }

    def _test_plan(self, impact: dict) -> list[str]:
        plan: list[str] = []
        if impact.get("related_routes"):
            plan.append("为命中的 API 路由补充请求成功、参数异常和权限边界测试。")
        if impact.get("impacted_files"):
            plan.append("运行受影响模块对应的 service/repository 单元测试。")
        if impact.get("related_lessons"):
            plan.append("复习命中的课程并重新完成相关测验，确认理解修改影响。")
        if impact.get("summary", {}).get("risk_level") == "HIGH":
            plan.append("高风险变更合并前需要增加回归测试，并在 PR 描述中列出影响范围。")
        if not plan:
            plan.append("当前 diff 未命中核心路径，至少执行一次静态检查和基础 smoke 测试。")
        return plan

    def _learning_impacts(self, impact: dict) -> list[dict]:
        return [
            {
                "lesson_id": lesson["id"],
                "title": lesson["title"],
                "order_index": lesson["order_index"],
                "matched_files": lesson.get("matched_files", []),
                "action": "回到课程复习相关源码，再结合 diff 检查改动影响。",
            }
            for lesson in impact.get("related_lessons", [])
        ]

    def _interview_talking_points(self, impact: dict) -> list[str]:
        points = [
            "我会先用静态影响分析确认变更文件，再沿着依赖图找到受影响模块。",
        ]
        if impact.get("related_routes"):
            points.append("如果变更命中 API 路由，我会优先说明请求入口、业务调用和响应契约如何保持稳定。")
        if impact.get("impacted_files"):
            points.append("我会把受影响文件作为回归测试范围，避免只看被修改文件。")
        if impact.get("related_lessons"):
            points.append("我会把命中的课程作为复习入口，用学习路线反向验证自己是否理解这次修改。")
        return points

    def _merge_advice(self, risk_level: str, impact: dict) -> str:
        if risk_level == "HIGH":
            return "建议暂缓直接合并，先补充测试、复核影响范围，并在 PR 描述中列出风险。"
        if risk_level == "MEDIUM":
            return "可以进入评审，但需要重点确认相关依赖和路由回归。"
        if impact.get("summary", {}).get("unknown_changed_file_count", 0):
            return "先确认未知文件路径是否属于当前项目，再决定是否合并。"
        return "可以按常规流程评审，合并前执行基础 smoke 测试。"
