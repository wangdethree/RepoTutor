from __future__ import annotations


class ProjectImprovementService:
    """根据项目分析和学习闭环生成可落地的改进建议。"""

    def build(
        self,
        project: dict,
        analysis: dict,
        plan: dict | None,
        progress: dict,
        practice_progress: dict | None,
        quiz_results: list[dict],
    ) -> dict:
        suggestions = self._suggestions(analysis, plan, progress, practice_progress, quiz_results)
        priority_counts = {
            "HIGH": len([item for item in suggestions if item["priority"] == "HIGH"]),
            "MEDIUM": len([item for item in suggestions if item["priority"] == "MEDIUM"]),
            "LOW": len([item for item in suggestions if item["priority"] == "LOW"]),
        }
        return {
            "project_id": project["id"],
            "project_name": project["name"],
            "suggestion_count": len(suggestions),
            "priority_counts": priority_counts,
            "highest_priority": self._highest_priority(priority_counts),
            "next_actions": self._next_actions(suggestions),
            "suggestions": suggestions,
        }

    def _suggestions(
        self,
        analysis: dict,
        plan: dict | None,
        progress: dict,
        practice_progress: dict | None,
        quiz_results: list[dict],
    ) -> list[dict]:
        candidates = [
            self._testing_suggestion(analysis),
            self._api_contract_suggestion(analysis),
            self._data_migration_suggestion(analysis),
            self._learning_gap_suggestion(plan, progress, quiz_results),
            self._practice_gap_suggestion(practice_progress),
            self._architecture_document_suggestion(analysis, plan),
        ]
        suggestions = [item for item in candidates if item]
        return sorted(
            suggestions,
            key=lambda item: (self._priority_order(item["priority"]), item["id"]),
        )

    def _testing_suggestion(self, analysis: dict) -> dict | None:
        summary = analysis.get("summary", {})
        files = analysis.get("files", [])
        test_files = [file for file in files if file.get("module_type") == "test" or "/test" in f"/{file.get('path', '')}"]
        python_file_count = summary.get("python_file_count", 0)
        route_count = summary.get("route_count", 0)
        if test_files and len(test_files) >= max(1, python_file_count // 8):
            return None
        priority = "HIGH" if route_count >= 3 and not test_files else "MEDIUM"
        focus_files = self._top_files(analysis, {"api", "service", "repository"}, limit=4)
        return self._suggestion(
            "testing_baseline",
            "测试兜底",
            priority,
            "补齐核心流程测试",
            f"当前识别到 {len(test_files)} 个测试文件，项目包含 {route_count} 个路由和 {python_file_count} 个 Python 文件。",
            [
                "为项目导入、静态分析、学习路线生成各补 1 条接口测试。",
                "为核心 service 或 repository 增加确定性单元测试。",
                "把测试命名为能直接对应演示链路的用例，方便面试时讲清质量保障。",
            ],
            focus_files,
            [],
            "pages/9_Source_Browser.py",
        )

    def _api_contract_suggestion(self, analysis: dict) -> dict | None:
        routes = analysis.get("routes", [])
        if not routes:
            return None
        missing_response_model = [route for route in routes if not route.get("response_model")]
        if len(missing_response_model) < max(1, len(routes) // 2):
            return None
        related_files = sorted({route["file_path"] for route in missing_response_model})[:5]
        return self._suggestion(
            "api_contracts",
            "接口契约",
            "MEDIUM",
            "收敛 API 请求响应边界",
            f"{len(missing_response_model)} 个路由未显式声明 response_model。",
            [
                "优先给列表、详情、创建类接口补 Pydantic 响应模型。",
                "把错误响应和空状态整理成统一格式，减少前端判断分支。",
                "为核心路由补一条契约测试，锁住字段名和状态码。",
            ],
            related_files,
            [],
            "pages/2_Architecture_Diagrams.py",
        )

    def _data_migration_suggestion(self, analysis: dict) -> dict | None:
        summary = analysis.get("summary", {})
        tech_stack = summary.get("tech_stack", [])
        if summary.get("model_count", 0) == 0 or "Alembic" in tech_stack:
            return None
        model_files = self._top_files(analysis, {"model"}, limit=4)
        return self._suggestion(
            "data_migrations",
            "数据演进",
            "MEDIUM",
            "补充数据库迁移与约束说明",
            f"当前识别到 {summary.get('model_count', 0)} 个数据模型，但技术栈中没有发现 Alembic。",
            [
                "为核心表补迁移脚本或建表说明，明确字段、索引和外键策略。",
                "检查关键字段是否需要唯一约束、非空约束和默认值。",
                "在项目报告里补充数据模型演进风险，便于面试时说明工程化考虑。",
            ],
            model_files,
            [],
            "pages/2_Architecture_Diagrams.py",
        )

    def _learning_gap_suggestion(self, plan: dict | None, progress: dict, quiz_results: list[dict]) -> dict | None:
        lessons = (plan or {}).get("lessons", [])
        if not lessons:
            return self._suggestion(
                "learning_plan_missing",
                "学习闭环",
                "HIGH",
                "先生成项目学习路线",
                "当前项目还没有学习路线，后续练习、测验和复习链路都无法串起来。",
                [
                    "生成学习路线后，优先完成前两节核心课程。",
                    "为第一节课程提交一次测验，形成可展示的学习记录。",
                ],
                [],
                [],
                "pages/3_Learning_Plan.py",
            )
        weak_lessons = [lesson for lesson in progress.get("lessons", []) if lesson.get("status") == "NEEDS_REVIEW"]
        low_quiz_results = [result for result in quiz_results if result.get("score", 0) < 80]
        if progress.get("completion_rate", 0) >= 80 and not weak_lessons and not low_quiz_results:
            return None
        related_lessons = self._lesson_refs(weak_lessons or progress.get("lessons", [])[:3])
        return self._suggestion(
            "learning_gaps",
            "学习短板",
            "HIGH" if weak_lessons or progress.get("completion_rate", 0) < 50 else "MEDIUM",
            "收敛待复习课程",
            f"当前课程完成率 {progress.get('completion_rate', 0)}%，需复习课程 {len(weak_lessons)} 节，低于 80 分测验 {len(low_quiz_results)} 次。",
            [
                "优先处理需复习课程，把最近一次测验提升到 80 分以上。",
                "把低分测验中的缺失点整理成 3 条面试回答素材。",
                "完成下一节课程后立刻提交测验，避免只看不练。",
            ],
            self._lesson_files(weak_lessons or lessons[:3]),
            related_lessons,
            "pages/12_Review.py",
        )

    def _practice_gap_suggestion(self, practice_progress: dict | None) -> dict | None:
        if not practice_progress:
            return None
        remaining_tasks = practice_progress.get("remaining_tasks", 0)
        if remaining_tasks == 0 and practice_progress.get("completion_rate", 0) >= 80:
            return None
        pending_lessons = [
            lesson for lesson in practice_progress.get("lessons", [])
            if lesson.get("pending_tasks")
        ][:3]
        return self._suggestion(
            "practice_gaps",
            "动手练习",
            "MEDIUM",
            "补齐源码定位与调用链练习",
            f"当前动手任务完成率 {practice_progress.get('completion_rate', 0)}%，剩余 {remaining_tasks} 个任务。",
            [
                "先完成每节课的源码定位任务，保证能讲清文件入口。",
                "对核心接口补一次调用链复述，形成面试时可直接复述的路径。",
                "练习一次改动影响分析，说明改一个文件会波及哪些模块。",
            ],
            [],
            self._lesson_refs(pending_lessons),
            "pages/10_Progress.py",
        )

    def _architecture_document_suggestion(self, analysis: dict, plan: dict | None) -> dict | None:
        summary = analysis.get("summary", {})
        core_modules = summary.get("core_modules", [])
        if len(core_modules) < 3:
            return None
        return self._suggestion(
            "architecture_story",
            "面试包装",
            "LOW",
            "沉淀项目讲解主线",
            f"项目核心模块包含 {len(core_modules)} 个候选文件，适合整理成入口、业务、数据三段式讲述。",
            [
                "用核心模块整理一段 1 分钟项目介绍。",
                "把学习路线中的前 3 节课程映射到项目讲解顺序。",
                "导出学习报告和面试材料，作为演示最终产物。",
            ],
            core_modules[:5],
            self._lesson_refs((plan or {}).get("lessons", [])[:3]),
            "pages/13_Interview.py",
        )

    def _suggestion(
        self,
        suggestion_id: str,
        category: str,
        priority: str,
        title: str,
        reason: str,
        action_items: list[str],
        related_files: list[str],
        related_lessons: list[dict],
        page: str,
    ) -> dict:
        return {
            "id": suggestion_id,
            "category": category,
            "priority": priority,
            "title": title,
            "reason": reason,
            "action_items": action_items,
            "interview_talking_point": self._talking_point(suggestion_id, action_items),
            "related_files": related_files,
            "related_lessons": related_lessons,
            "page": page,
        }

    def _talking_point(self, suggestion_id: str, action_items: list[str]) -> str:
        first_action = action_items[0] if action_items else "继续补齐项目证据。"
        templates = {
            "testing_baseline": "我会把这个项目下一步的工程化重点放在测试兜底上，先覆盖核心接口和学习链路。{action}",
            "api_contracts": "我会继续收敛接口契约，让前后端边界更稳定，减少字段变更带来的联调成本。{action}",
            "data_migrations": "我会把数据模型演进显式化，补充迁移和约束说明，避免后续多人协作时数据库状态不可追踪。{action}",
            "learning_plan_missing": "当前最重要的是先建立学习路线，因为后续测验、练习和复习都需要围绕路线形成闭环。{action}",
            "learning_gaps": "我会把低分课程和缺失点转成复习计划，说明自己不是只看代码，而是用测验结果驱动补强。{action}",
            "practice_gaps": "我会继续补齐动手练习，重点证明自己能从源码定位、调用链复述走到改动影响判断。{action}",
            "architecture_story": "我会把核心模块整理成入口、业务、数据三段式讲述，让项目介绍更像一次真实工程复盘。{action}",
        }
        template = templates.get(suggestion_id, "我会基于当前项目事实继续推进改进，优先处理最影响演示和交付质量的事项。{action}")
        return template.format(action=first_action)

    def _top_files(self, analysis: dict, module_types: set[str], limit: int) -> list[str]:
        files = [
            file for file in analysis.get("files", [])
            if file.get("module_type") in module_types
        ]
        files.sort(key=lambda item: item.get("importance_score", 0), reverse=True)
        return [file["path"] for file in files[:limit]]

    def _lesson_files(self, lessons: list[dict]) -> list[str]:
        files: list[str] = []
        for lesson in lessons:
            for path in lesson.get("related_files", []):
                if path not in files:
                    files.append(path)
        return files[:5]

    def _lesson_refs(self, lessons: list[dict]) -> list[dict]:
        refs: list[dict] = []
        for lesson in lessons:
            lesson_id = lesson.get("lesson_id") or lesson.get("id")
            title = lesson.get("lesson_title") or lesson.get("title")
            if lesson_id and title:
                refs.append(
                    {
                        "id": lesson_id,
                        "title": title,
                        "order_index": lesson.get("order_index", 0),
                    }
                )
        return refs[:5]

    def _next_actions(self, suggestions: list[dict]) -> list[str]:
        actions: list[str] = []
        for suggestion in suggestions:
            if suggestion["action_items"]:
                actions.append(suggestion["action_items"][0])
        return actions[:5]

    def _highest_priority(self, counts: dict[str, int]) -> str:
        for priority in ("HIGH", "MEDIUM", "LOW"):
            if counts[priority]:
                return priority
        return "NONE"

    def _priority_order(self, priority: str) -> int:
        return {"HIGH": 0, "MEDIUM": 1, "LOW": 2}.get(priority, 3)
