from __future__ import annotations

import os

import requests
import streamlit as st


API_URL = os.getenv("REPO_TUTOR_API_URL", "http://localhost:8000")


def _readiness_level_label(level: str) -> str:
    return {
        "READY": "可进入面试演练",
        "ALMOST_READY": "接近可面试",
        "NEEDS_WORK": "还需补强",
    }.get(level, level)


def _checklist_status_label(status: str) -> str:
    return {
        "DONE": "已完成",
        "IN_PROGRESS": "进行中",
        "TODO": "待补齐",
    }.get(status, status)


st.set_page_config(page_title="面试准备", page_icon="RT", layout="wide")
st.title("面试准备")

project_id = st.session_state.get("project_id")
if not project_id:
    st.info("请先在首页上传或选择项目。")
    st.stop()

try:
    response = requests.get(f"{API_URL}/api/projects/{project_id}/interview-kit", timeout=30)
    response.raise_for_status()
    kit = response.json()
except requests.RequestException as exc:
    st.error(f"读取面试讲解包失败：{exc}")
    st.stop()

st.subheader(kit["title"])
st.success(kit["elevator_pitch"])

try:
    download_response = requests.get(f"{API_URL}/api/projects/{project_id}/interview-kit.md", timeout=30)
except requests.RequestException:
    download_response = None

try:
    readiness_response = requests.get(f"{API_URL}/api/projects/{project_id}/interview-readiness", timeout=30)
    readiness_response.raise_for_status()
    readiness = readiness_response.json()
except requests.RequestException:
    readiness = None

metrics = st.columns(4)
metrics[0].metric("高频问题", len(kit["questions"]))
metrics[1].metric("源码证据", len(kit["core_references"]))
metrics[2].metric("事实校验", "已通过" if kit["fact_checked"] else "未通过")
if download_response and download_response.status_code == 200:
    metrics[3].download_button(
        "下载面试材料",
        data=download_response.text,
        file_name=f"{project_id}-interview-kit.md",
        mime="text/markdown",
    )
else:
    metrics[3].button("下载面试材料", disabled=True)

if readiness:
    st.subheader("面试准备度")
    readiness_cols = st.columns(5)
    readiness_cols[0].metric("准备度", f"{readiness['readiness_score']}%")
    readiness_cols[1].metric("状态", _readiness_level_label(readiness["readiness_level"]))
    breakdown = readiness["score_breakdown"]
    readiness_cols[2].metric("课程", f"{breakdown['course_completion']}%")
    readiness_cols[3].metric("练习", f"{breakdown['practice_completion']}%")
    readiness_cols[4].metric("测验", f"{breakdown['quiz_average']}%")
    st.progress(readiness["readiness_score"] / 100)

    if readiness["recommended_actions"]:
        st.write("下一步")
        for action in readiness["recommended_actions"]:
            st.write(f"- {action}")

    with st.expander("准备清单", expanded=True):
        for item in readiness["checklist"]:
            cols = st.columns([1, 3, 4])
            cols[0].write(_checklist_status_label(item["status"]))
            cols[1].write(item["title"])
            cols[2].write(item["detail"])

    weak_lessons = readiness.get("weak_lessons", [])
    pending_practice_lessons = readiness.get("pending_practice_lessons", [])
    if weak_lessons or pending_practice_lessons:
        st.subheader("优先补强")
        for lesson in weak_lessons:
            cols = st.columns([4, 1])
            cols[0].warning(f"{lesson['order_index']}. {lesson['title']} 需要复习")
            if cols[1].button("去复习", key=f"interview-review-{lesson['id']}"):
                st.session_state["lesson_id"] = lesson["id"]
                st.switch_page("pages/4_Lesson_Quiz.py")
        for lesson in pending_practice_lessons:
            cols = st.columns([4, 1])
            pending = "；".join(lesson["pending_tasks"][:2])
            cols[0].info(f"{lesson['order_index']}. {lesson['lesson_title']} 待练习：{pending}")
            if cols[1].button("去练习", key=f"interview-practice-{lesson['lesson_id']}"):
                st.session_state["lesson_id"] = lesson["lesson_id"]
                st.switch_page("pages/4_Lesson_Quiz.py")

left, right = st.columns([1, 1])
with left:
    st.subheader("讲解路径")
    for index, item in enumerate(kit["architecture_story"], start=1):
        st.write(f"{index}. {item}")

    st.subheader("技术亮点")
    for item in kit["technical_highlights"]:
        st.write(f"- {item}")

with right:
    st.subheader("权衡与风险")
    for item in kit["tradeoffs"]:
        st.write(f"- {item}")
    for item in kit["risk_points"]:
        st.warning(item)

st.subheader("高频问答")
for question in kit["questions"]:
    with st.container(border=True):
        st.caption(question["category"])
        st.markdown(f"**{question['question']}**")
        for point in question["answer_points"]:
            st.write(f"- {point}")
        references = question.get("references", [])
        if references:
            st.write("源码证据")
            ref_cols = st.columns(min(3, len(references)))
            for index, reference in enumerate(references):
                column = ref_cols[index % len(ref_cols)]
                file_name = reference["file"].split("/")[-1]
                column.caption(f"{file_name}:{reference['line']}")
                if column.button("查看源码", key=f"{question['id']}-{index}", help=reference.get("name", "查看源码")):
                    st.session_state["source_file_path"] = reference["file"]
                    st.session_state["source_line"] = reference["line"]
                    st.switch_page("pages/9_Source_Browser.py")

st.subheader("收尾总结")
st.info(kit["closing_summary"])
