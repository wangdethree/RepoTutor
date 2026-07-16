from __future__ import annotations


class PracticeTaskService:
    """把课程内容转换为可执行的动手练习任务。"""

    def build(self, lesson: dict, quiz: dict) -> dict:
        tasks = [
            self._source_walkthrough_task(lesson),
            self._call_chain_task(lesson),
            self._change_impact_task(lesson, quiz),
        ]
        tasks = [task for task in tasks if task]
        return {
            "lesson_id": lesson["id"],
            "lesson_title": lesson["title"],
            "task_count": len(tasks),
            "tasks": tasks,
        }

    def _source_walkthrough_task(self, lesson: dict) -> dict:
        references = lesson.get("core_code_locations", [])[:4]
        target_files = self._target_files(references)
        return {
            "id": f"{lesson['id']}-practice-source",
            "title": "源码定位走读",
            "task_type": "source_walkthrough",
            "objective": "能从真实文件和行号说清本节核心代码在哪里、负责什么。",
            "target_files": target_files,
            "references": references,
            "estimated_minutes": 12,
            "steps": [
                "打开每个目标文件，定位卡片中的行号。",
                "用一句话写下该函数、类或路由的职责。",
                "标出它属于入口、路由、Service、Repository、Model、Schema 中的哪一层。",
            ],
            "acceptance_checks": [
                "能说出至少 2 个真实文件路径。",
                "能指出一个核心符号的行号。",
                "能解释这些文件为什么属于本节重点。",
            ],
            "risk_notes": ["不要只背文件名，要回到源码确认真实行号和上下文。"],
        }

    def _call_chain_task(self, lesson: dict) -> dict | None:
        chains = lesson.get("call_chains", [])
        if not chains:
            return None
        chain = chains[0]
        steps = chain.get("steps", [])
        references = chain.get("references", [])
        return {
            "id": f"{lesson['id']}-practice-call-chain",
            "title": "调用链复述",
            "task_type": "call_chain",
            "objective": "能把一次请求从入口函数复述到后续核心函数或方法。",
            "target_files": self._target_files(references),
            "references": references,
            "estimated_minutes": 15,
            "steps": [
                f"先写下调用链标题：{chain['title']}。",
                "按顺序打开调用链中每个文件。",
                "把每一步的输入、输出或职责写成一句话。",
                "最后不看答案复述整条路径。",
            ],
            "acceptance_checks": [
                "能按顺序说出调用链中的主要符号。",
                "能解释 Router、Service、Repository 的职责差异。",
                "能指出链路中最容易产生修改影响的位置。",
            ],
            "risk_notes": [
                "调用链来自静态分析，遇到依赖注入或动态分发时要结合源码上下文确认。",
                "不要把 import 依赖直接等同于运行时调用。",
            ],
            "expected_path": " -> ".join(step["symbol"] for step in steps),
        }

    def _change_impact_task(self, lesson: dict, quiz: dict) -> dict:
        references = lesson.get("core_code_locations", [])[:5]
        target_files = self._target_files(references)
        keyword_hint = self._keyword_hint(quiz)
        return {
            "id": f"{lesson['id']}-practice-impact",
            "title": "改动影响演练",
            "task_type": "change_impact",
            "objective": "选择一个目标文件，演练修改前应该检查哪些相关模块。",
            "target_files": target_files,
            "references": references,
            "estimated_minutes": 18,
            "steps": [
                "从目标文件中选择一个函数、字段或路由作为假设修改点。",
                "列出它可能影响的 Schema、Service、Repository、Model 或测试文件。",
                "打开依赖图或 Diff 影响分析页面，对照静态依赖确认遗漏。",
                "写下至少 3 条提交前检查项。",
            ],
            "acceptance_checks": [
                "能说清修改点属于哪一层。",
                "能列出至少 3 个需要一起检查的模块。",
                "能把检查项转成测验答案或代码审查清单。",
            ],
            "risk_notes": [
                "这是修改前演练，不要求直接改源码。",
                "如果目标文件未出现在依赖图中，优先用命名约定和测试入口补充检查。",
            ],
            "keyword_hint": keyword_hint,
        }

    def _target_files(self, references: list[dict]) -> list[str]:
        files: list[str] = []
        for reference in references:
            file_path = reference.get("file")
            if file_path and file_path not in files:
                files.append(file_path)
        return files

    def _keyword_hint(self, quiz: dict) -> list[str]:
        keywords: list[str] = []
        for question in quiz.get("questions", []):
            for keyword in question.get("expected_keywords", []):
                if keyword not in keywords:
                    keywords.append(keyword)
        return keywords[:8]
