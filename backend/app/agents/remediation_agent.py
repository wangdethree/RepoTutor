from __future__ import annotations

from app.llm.validators import CodeReferenceValidator
from app.schemas.analysis import AnalysisResult
from app.services.call_chain_service import CallChainService


class RemediationAgent:
    """根据低分测验结果生成补充讲解和二次测验。"""

    def generate(self, analysis: AnalysisResult, lesson: dict, quiz_result: dict) -> dict:
        references = CodeReferenceValidator(analysis).validate_many(self._references(analysis, lesson))
        call_chains = self._call_chains(analysis, lesson)
        focus_points = self._focus_points(quiz_result)
        retry_quiz = self._retry_quiz(analysis, lesson, quiz_result, references, call_chains)
        return {
            "id": f"remedial-{quiz_result['id']}",
            "lesson_id": lesson["id"],
            "source_result_id": quiz_result["id"],
            "title": f"补充讲解：{lesson['title']}",
            "trigger_score": quiz_result["score"],
            "focus_points": focus_points,
            "explanation": self._explanation(analysis, lesson, focus_points, call_chains),
            "practice_steps": self._practice_steps(references, call_chains),
            "code_locations": references,
            "call_chains": call_chains,
            "retry_quiz": retry_quiz,
            "fact_checked": True,
        }

    def _focus_points(self, quiz_result: dict) -> list[str]:
        points = []
        points.extend(str(item) for item in quiz_result.get("missing_points", []) if str(item).strip())
        points.extend(str(item) for item in quiz_result.get("misconceptions", []) if str(item).strip())
        return points or ["需要重新梳理本节核心文件、调用链和修改影响范围。"]

    def _explanation(
        self,
        analysis: AnalysisResult,
        lesson: dict,
        focus_points: list[str],
        call_chains: list[dict],
    ) -> list[str]:
        explanation = [
            f"本次补充讲解针对《{lesson['title']}》的薄弱点，先回到真实源码位置重新定位。",
            "低分通常不是因为概念不会，而是文件、函数和调用顺序没有对应到真实代码。",
        ]
        if focus_points:
            explanation.append("优先补齐这些缺口：" + "；".join(focus_points[:3]))
        if call_chains:
            chain = call_chains[0]
            explanation.append(
                "请先复述调用链："
                + " -> ".join(step["symbol"] for step in chain["steps"])
                + "，再解释每一步职责。"
            )
        else:
            explanation.append(f"请先围绕 {', '.join(lesson.get('related_files', [])[:3])} 建立阅读顺序。")
        route_count = analysis.summary.route_count
        model_count = analysis.summary.model_count
        explanation.append(
            f"当前项目识别到 {route_count} 个路由、{model_count} 个模型，"
            "补测时要把路由入口、业务层、数据层和 Schema 边界说清楚。"
        )
        return explanation

    def _practice_steps(self, references: list[dict], call_chains: list[dict]) -> list[str]:
        steps = [
            "先打开第一处源码证据，用自己的话说明它属于哪一层。",
            "再对照缺失点，把题目中的关键词写回真实文件名或函数名。",
        ]
        if call_chains:
            steps.append("最后按调用链顺序复述一次请求如何进入业务逻辑和数据访问。")
        if references:
            first = references[0]
            steps.append(f"复习起点建议放在 {first['file']}:{first['line']}。")
        return steps

    def _retry_quiz(
        self,
        analysis: AnalysisResult,
        lesson: dict,
        quiz_result: dict,
        references: list[dict],
        call_chains: list[dict],
    ) -> dict:
        first_reference = references[0] if references else {"file": "main.py", "name": "main"}
        chain_steps = call_chains[0]["steps"] if call_chains else []
        chain_keywords = self._chain_keywords(chain_steps)
        questions = [
            {
                "id": "rq1",
                "type": "补充定位题",
                "prompt": "请重新说明本节最重要的源码入口在哪里，并解释它为什么重要。",
                "expected_keywords": [first_reference["file"]],
            },
            {
                "id": "rq2",
                "type": "补充调用链题",
                "prompt": "请按顺序写出本节最关键的调用链，并说明每一步职责。",
                "expected_keywords": chain_keywords or ["Router", "Service", "Repository"],
            },
            {
                "id": "rq3",
                "type": "补充修改影响题",
                "prompt": "如果围绕本节相关功能做修改，你会同步检查哪些层和哪些测试？",
                "expected_keywords": ["route", "service", "repository", "schema", "test"],
            },
        ]
        return {
            "id": f"retry-{quiz_result['id']}",
            "lesson_id": lesson["id"],
            "questions": questions,
        }

    def _chain_keywords(self, chain_steps: list[dict]) -> list[str]:
        keywords: list[str] = []
        for step in chain_steps[:4]:
            symbol = step["symbol"]
            if "." in symbol:
                keywords.extend(part for part in symbol.split(".") if part)
            else:
                keywords.append(symbol)
        return list(dict.fromkeys(keywords))

    def _references(self, analysis: AnalysisResult, lesson: dict) -> list[dict]:
        references: list[dict] = []
        if lesson.get("core_code_locations"):
            references.extend(lesson["core_code_locations"])
        for file_path in lesson.get("related_files", [])[:4]:
            if any(reference.get("file") == file_path for reference in references):
                continue
            symbol = next((item for item in analysis.symbols if item.file_path == file_path), None)
            if symbol:
                references.append(
                    {
                        "file": symbol.file_path,
                        "line": symbol.start_line,
                        "name": symbol.qualified_name or symbol.name,
                        "kind": symbol.symbol_type,
                    }
                )
            else:
                references.append({"file": file_path, "line": 1, "name": "文件级阅读", "kind": "file"})
        if not references and analysis.files:
            first_file = analysis.files[0]
            references.append(
                {"file": first_file.path, "line": 1, "name": "核心文件", "kind": first_file.module_type}
            )
        return references[:8]

    def _call_chains(self, analysis: AnalysisResult, lesson: dict) -> list[dict]:
        related_files = lesson.get("related_files", [])
        chains = CallChainService().build_route_chains(analysis)
        matched = [
            chain
            for chain in chains
            if any(step["file"] in related_files for step in chain["steps"])
            or chain["route"].get("file") in related_files
        ]
        return (matched or chains[:1])[:2]
