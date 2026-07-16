from __future__ import annotations

import os

import requests
import streamlit as st


API_URL = os.getenv("REPO_TUTOR_API_URL", "http://localhost:8000")


def _mastery_label(level: str) -> str:
    return {
        "MASTERED": "已掌握",
        "PARTIAL": "部分掌握",
        "NEEDS_REVIEW": "需复习",
    }.get(level, level)


st.set_page_config(page_title="复习中心", page_icon="RT", layout="wide")
st.title("复习中心")

project_id = st.session_state.get("project_id")
if not project_id:
    st.info("请先在首页上传或选择项目。")
    st.stop()

try:
    response = requests.get(f"{API_URL}/api/projects/{project_id}/quiz-results", timeout=30)
    response.raise_for_status()
    results = response.json()["quiz_results"]
except requests.RequestException as exc:
    st.error(f"读取测验记录失败：{exc}")
    st.stop()

try:
    practice_response = requests.get(
        f"{API_URL}/api/projects/{project_id}/practice-progress",
        timeout=30,
    )
    practice_response.raise_for_status()
    practice_progress = practice_response.json()
except requests.RequestException as exc:
    practice_progress = None
    st.warning(f"读取动手任务进度失败：{exc}")

try:
    interview_response = requests.get(f"{API_URL}/api/projects/{project_id}/interview-kit", timeout=30)
    interview_response.raise_for_status()
    interview_kit = interview_response.json()
except requests.RequestException as exc:
    interview_kit = None
    st.warning(f"读取面试题进度失败：{exc}")

pending_practice_lessons = [
    lesson for lesson in (practice_progress or {}).get("lessons", []) if lesson["pending_tasks"]
]
pending_interview_questions = [
    question for question in (interview_kit or {}).get("questions", []) if not question.get("mastered")
]
if not results and not pending_practice_lessons and not pending_interview_questions:
    st.info("当前项目还没有测验记录、待练习任务或待掌握面试题。完成课程测验、动手任务或面试问答演练后，这里会生成复习材料。")
    st.stop()

weak_results = [result for result in results if result["score"] < 80]
metrics = st.columns(6)
metrics[0].metric("测验次数", len(results))
metrics[1].metric("待复习", len(weak_results))
metrics[2].metric("待练任务", practice_progress["remaining_tasks"] if practice_progress else 0)
metrics[3].metric("待练面试题", len(pending_interview_questions))
metrics[4].metric("最高分", max(result["score"] for result in results) if results else "-")
metrics[5].metric("最近得分", results[0]["score"] if results else "-")

if pending_practice_lessons:
    st.subheader("待完成动手任务")
    for lesson in pending_practice_lessons[:5]:
        with st.container(border=True):
            cols = st.columns([4, 1, 1])
            cols[0].markdown(f"**{lesson['order_index']}. {lesson['lesson_title']}**")
            cols[1].metric("任务", f"{lesson['completed_task_count']}/{lesson['task_count']}")
            cols[2].metric("完成率", f"{lesson['completion_rate']}%")
            st.warning("待练习：" + "；".join(lesson["pending_tasks"][:3]))
            if st.button("去练习", key=f"practice-review-{lesson['lesson_id']}"):
                st.session_state["lesson_id"] = lesson["lesson_id"]
                st.switch_page("pages/4_Lesson_Quiz.py")

if pending_interview_questions:
    st.subheader("待掌握面试题")
    for question in pending_interview_questions[:5]:
        with st.container(border=True):
            cols = st.columns([4, 1])
            cols[0].caption(question["category"])
            cols[0].markdown(f"**{question['question']}**")
            for point in question["answer_points"][:3]:
                cols[0].write(f"- {point}")
            if cols[1].button("去练题", key=f"interview-question-review-{question['id']}"):
                st.switch_page("pages/13_Interview.py")

if weak_results:
    st.subheader("优先复习")
    for result in weak_results[:5]:
        with st.container(border=True):
            cols = st.columns([4, 1, 1])
            cols[0].markdown(f"**{result['lesson_order']}. {result['lesson_title']}**")
            cols[1].metric("得分", result["score"])
            cols[2].write(_mastery_label(result["mastery_level"]))
            if result["missing_points"]:
                st.warning("缺失点：" + "；".join(result["missing_points"]))
            if result["misconceptions"]:
                st.write("可能误区：" + "；".join(result["misconceptions"]))
            st.write("建议：" + result["recommended_action"])
            action_cols = st.columns(3)
            if action_cols[0].button("回到课程", key=f"review-lesson-{result['id']}"):
                st.session_state["lesson_id"] = result["lesson_id"]
                st.switch_page("pages/4_Lesson_Quiz.py")
            if action_cols[1].button("知识卡片", key=f"review-cards-{result['id']}"):
                st.session_state["lesson_id"] = result["lesson_id"]
                st.switch_page("pages/4_Lesson_Quiz.py")
            if result["score"] < 60 and action_cols[2].button("补充讲解", key=f"remedial-{result['id']}"):
                remediation_response = requests.post(
                    f"{API_URL}/api/quiz-results/{result['id']}/remediation",
                    timeout=60,
                )
                remediation_response.raise_for_status()
                st.session_state["lesson_id"] = result["lesson_id"]
                st.session_state[f"remediation_{result['lesson_id']}"] = remediation_response.json()
                st.switch_page("pages/4_Lesson_Quiz.py")

if results:
    st.subheader("全部测验记录")
    st.dataframe(
        [
            {
                "时间": result["created_at"],
                "课程": result["lesson_title"],
                "得分": result["score"],
                "掌握度": _mastery_label(result["mastery_level"]),
                "建议动作": result["recommended_action"],
            }
            for result in results
        ],
        use_container_width=True,
    )
