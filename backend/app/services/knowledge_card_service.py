from __future__ import annotations


class KnowledgeCardService:
    """把单节课程拆成可复习的知识卡片。"""

    def build(self, lesson: dict, quiz: dict) -> dict:
        cards: list[dict] = []
        cards.extend(self._objective_cards(lesson))
        cards.extend(self._code_location_cards(lesson))
        cards.extend(self._call_chain_cards(lesson))
        cards.extend(self._pitfall_cards(lesson))
        cards.extend(self._quiz_cards(quiz))

        unique_cards = self._dedupe(cards)
        return {
            "lesson_id": lesson["id"],
            "lesson_title": lesson["title"],
            "card_count": len(unique_cards),
            "cards": unique_cards,
        }

    def _objective_cards(self, lesson: dict) -> list[dict]:
        cards = []
        for index, objective in enumerate(lesson.get("objectives", []), start=1):
            cards.append(
                self._card(
                    lesson,
                    category="学习目标",
                    index=index,
                    front=f"本节需要掌握的目标 {index} 是什么？",
                    back=objective,
                    references=[],
                    review_prompt="用一句话解释这个目标为什么和当前项目有关。",
                )
            )
        return cards

    def _code_location_cards(self, lesson: dict) -> list[dict]:
        cards = []
        for index, location in enumerate(lesson.get("core_code_locations", [])[:6], start=1):
            cards.append(
                self._card(
                    lesson,
                    category="源码定位",
                    index=index,
                    front=f"`{location['name']}` 位于哪个文件和行号？",
                    back=f"{location['file']}:{location['line']}，类型是 {location['kind']}。",
                    references=[location],
                    review_prompt="回到源码浏览页，确认它在本节调用或结构中的作用。",
                )
            )
        return cards

    def _call_chain_cards(self, lesson: dict) -> list[dict]:
        cards = []
        for index, chain in enumerate(lesson.get("call_chains", [])[:3], start=1):
            steps = [step["symbol"] for step in chain.get("steps", [])]
            if not steps:
                continue
            cards.append(
                self._card(
                    lesson,
                    category="调用链",
                    index=index,
                    front=f"{chain['title']} 的主要路径是什么？",
                    back=" -> ".join(steps),
                    references=chain.get("references", []),
                    review_prompt="遮住答案后，按 Router、Service、Repository 的顺序复述一遍。",
                )
            )
        return cards

    def _pitfall_cards(self, lesson: dict) -> list[dict]:
        cards = []
        for index, pitfall in enumerate(lesson.get("pitfalls", [])[:4], start=1):
            cards.append(
                self._card(
                    lesson,
                    category="易错点",
                    index=index,
                    front="学习或讲解本节时容易犯什么错误？",
                    back=pitfall,
                    references=[],
                    review_prompt="说出一个避免这个错误的检查动作。",
                )
            )
        return cards

    def _quiz_cards(self, quiz: dict) -> list[dict]:
        cards = []
        for index, question in enumerate(quiz.get("questions", [])[:4], start=1):
            keywords = question.get("expected_keywords", [])
            cards.append(
                {
                    "id": f"{quiz['lesson_id']}-quiz-{index}",
                    "category": "测验关键词",
                    "front": question["prompt"],
                    "back": "；".join(keywords) if keywords else "请结合课程内容作答。",
                    "references": [],
                    "review_prompt": "先口头回答，再对照关键词补齐遗漏。",
                }
            )
        return cards

    def _card(
        self,
        lesson: dict,
        category: str,
        index: int,
        front: str,
        back: str,
        references: list[dict],
        review_prompt: str,
    ) -> dict:
        slug = category.replace(" ", "-")
        return {
            "id": f"{lesson['id']}-{slug}-{index}",
            "category": category,
            "front": front,
            "back": back,
            "references": references,
            "review_prompt": review_prompt,
        }

    def _dedupe(self, cards: list[dict]) -> list[dict]:
        seen: set[tuple[str, str]] = set()
        unique_cards: list[dict] = []
        for card in cards:
            key = (card["category"], card["front"])
            if key in seen:
                continue
            seen.add(key)
            unique_cards.append(card)
        return unique_cards
