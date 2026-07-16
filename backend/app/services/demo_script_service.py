from __future__ import annotations


class DemoScriptService:
    """生成项目演示讲稿，把学习闭环转成可复述的展示顺序。"""

    def build(
        self,
        project: dict,
        analysis: dict,
        plan: dict | None,
        progress: dict,
        demo_readiness: dict,
        improvement_suggestions: dict,
    ) -> dict:
        sections = [
            self._opening_section(project, analysis),
            self._architecture_section(analysis),
            self._learning_loop_section(plan, progress),
            self._demo_readiness_section(demo_readiness),
            self._improvement_section(improvement_suggestions),
            self._closing_section(project, demo_readiness),
        ]
        return {
            "project_id": project["id"],
            "project_name": project["name"],
            "title": f"{project['name']} 演示讲稿",
            "estimated_minutes": sum(section["duration_minutes"] for section in sections),
            "readiness_score": demo_readiness.get("readiness_score", 0),
            "sections": sections,
            "opening_sentence": self._opening_sentence(project, analysis),
            "closing_sentence": self._closing_sentence(project, demo_readiness),
        }

    def _opening_section(self, project: dict, analysis: dict) -> dict:
        summary = analysis.get("summary", {})
        return self._section(
            "opening",
            "开场定位",
            1,
            [
                self._opening_sentence(project, analysis),
                f"项目类型是 {summary.get('project_type', 'Python 项目')}，主要技术栈包括 {self._join(summary.get('tech_stack', []))}。",
                "这次演示我会按项目事实、学习闭环、面试包装和后续优化四段来讲。",
            ],
            [
                f"Python 文件：{summary.get('python_file_count', 0)}",
                f"路由：{summary.get('route_count', 0)}",
                f"模型：{summary.get('model_count', 0)}",
            ],
            "pages/1_Project_Overview.py",
        )

    def _architecture_section(self, analysis: dict) -> dict:
        summary = analysis.get("summary", {})
        core_modules = summary.get("core_modules", [])[:5]
        return self._section(
            "architecture",
            "架构与核心模块",
            1,
            [
                "这里我先从核心模块切入，说明项目入口、业务处理和数据边界。",
                "如果需要展开，可以打开架构图或源码浏览页，沿着路由和服务层继续讲。",
                "核心模块会作为后续学习路线和面试问答的源码证据。",
            ],
            core_modules or ["暂无核心模块，需要先完成项目分析。"],
            "pages/2_Architecture_Diagrams.py",
        )

    def _learning_loop_section(self, plan: dict | None, progress: dict) -> dict:
        if not plan:
            return self._section(
                "learning_loop",
                "学习闭环",
                1,
                [
                    "当前还没有生成学习路线，演示时应先进入学习路线页生成课程。",
                    "生成路线后，再通过课程、测验、复习中心和动手任务形成闭环。",
                ],
                ["学习路线：未生成"],
                "pages/3_Learning_Plan.py",
            )
        return self._section(
            "learning_loop",
            "学习闭环",
            1,
            [
                f"学习路线包含 {progress.get('total_lessons', 0)} 节课程，目前完成率 {progress.get('completion_rate', 0)}%。",
                "每节课会落到真实源码位置、调用链、测验和动手任务，避免只生成泛泛讲解。",
                "如果课程低分，会进入复习中心和补充讲解，形成可追踪的学习记录。",
            ],
            [
                f"已完成：{progress.get('completed_lessons', 0)}",
                f"需复习：{progress.get('needs_review_lessons', 0)}",
                f"下一步：{progress.get('next_action', '')}",
            ],
            "pages/10_Progress.py",
        )

    def _demo_readiness_section(self, readiness: dict) -> dict:
        pending = [item for item in readiness.get("items", []) if item.get("status") != "DONE"]
        return self._section(
            "demo_readiness",
            "演示准备状态",
            1,
            [
                f"当前演示准备度是 {readiness.get('readiness_score', 0)}%，已完成 {readiness.get('completed_items', 0)}/{readiness.get('total_items', 0)} 项。",
                "演示准备页会把分析、架构图、学习路线、进度、练习、面试和报告导出放在同一张检查清单里。",
                "这能帮助我快速判断项目是不是已经达到可展示状态。",
            ],
            [item["title"] for item in pending[:4]] or ["演示闭环已达到可展示状态。"],
            "pages/15_Demo_Readiness.py",
        )

    def _improvement_section(self, improvements: dict) -> dict:
        suggestions = improvements.get("suggestions", [])[:3]
        return self._section(
            "improvements",
            "后续优化计划",
            1,
            [
                "最后我会补充后续优化计划，说明这个项目不只是能跑，还能继续工程化。",
                "改进建议来自静态分析、学习进度、动手任务和测验记录，而不是凭空罗列。",
                "面试时可以把这些建议转成下一步行动，展示自己对项目质量的判断。",
            ],
            [
                suggestion.get("interview_talking_point") or suggestion.get("title", "")
                for suggestion in suggestions
            ] or ["当前没有明显改进建议。"],
            "pages/16_Improvement_Suggestions.py",
        )

    def _closing_section(self, project: dict, readiness: dict) -> dict:
        return self._section(
            "closing",
            "收尾表达",
            1,
            [
                self._closing_sentence(project, readiness),
                "如果面试官继续追问，我会从源码证据、调用链和改进计划三个方向展开。",
            ],
            readiness.get("next_actions", []) or ["可以导出报告和面试材料作为最终产物。"],
            "pages/11_Reports.py",
        )

    def _section(
        self,
        section_id: str,
        title: str,
        duration_minutes: int,
        talking_points: list[str],
        evidence: list[str],
        page: str,
    ) -> dict:
        return {
            "id": section_id,
            "title": title,
            "duration_minutes": duration_minutes,
            "talking_points": talking_points,
            "evidence": evidence,
            "page": page,
        }

    def _opening_sentence(self, project: dict, analysis: dict) -> str:
        summary = analysis.get("summary", {})
        return (
            f"RepoTutor 对 {project['name']} 做了静态分析，并把 "
            f"{summary.get('python_file_count', 0)} 个 Python 文件转成可学习、可测验、可复述的项目材料。"
        )

    def _closing_sentence(self, project: dict, readiness: dict) -> str:
        status = "已经具备演示条件" if readiness.get("ready_for_demo") else "还在补齐演示闭环"
        return f"所以这个项目现在不只是被分析出来了，也被整理成了学习、练习、面试和后续优化的一套闭环，当前状态是：{status}。"

    def _join(self, items: list[str]) -> str:
        return "、".join(items) if items else "Python"
