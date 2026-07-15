from __future__ import annotations

import os

import requests
import streamlit as st


API_URL = os.getenv("REPO_TUTOR_API_URL", "http://localhost:8000")


def _status_label(status: str) -> str:
    return {
        "NOT_STARTED": "未开始",
        "IN_PROGRESS": "学习中",
        "NEEDS_REVIEW": "需复习",
        "COMPLETED": "已完成",
    }.get(status, status)


st.set_page_config(page_title="课程与测验", page_icon="RT", layout="wide")
st.title("课程与测验")

project_id = st.session_state.get("project_id")
lesson_id = st.session_state.get("lesson_id")
if not project_id:
    st.info("请先在首页上传或选择项目。")
    st.stop()

plan = requests.get(f"{API_URL}/api/projects/{project_id}/learning-plan", timeout=60).json()
lesson_options = {lesson["title"]: lesson["id"] for lesson in plan["lessons"]}
selected_title = st.selectbox(
    "选择课程",
    list(lesson_options.keys()),
    index=list(lesson_options.values()).index(lesson_id) if lesson_id in lesson_options.values() else 0,
)
lesson_id = lesson_options[selected_title]
st.session_state["lesson_id"] = lesson_id

lesson = requests.post(f"{API_URL}/api/lessons/{lesson_id}/generate", timeout=60).json()
if lesson.get("status") == "NOT_STARTED":
    status_response = requests.post(f"{API_URL}/api/lessons/{lesson_id}/status", json={"status": "IN_PROGRESS"}, timeout=20)
    if status_response.status_code == 200:
        lesson = status_response.json()

st.header(lesson["title"])
status_cols = st.columns(4)
status_cols[0].metric("课程状态", _status_label(lesson.get("status", "NOT_STARTED")))
status_cols[1].metric("最近得分", lesson.get("last_score", "-"))
status_cols[2].metric("掌握度", lesson.get("mastery_level", "-") or "-")
if status_cols[3].button("标记完成"):
    complete_response = requests.post(f"{API_URL}/api/lessons/{lesson_id}/complete", timeout=20)
    complete_response.raise_for_status()
    st.success("课程已标记完成")
    st.rerun()

st.subheader("为什么要学")
st.write(lesson["why"])
st.subheader("学习目标")
st.write("；".join(lesson["objectives"]))
st.subheader("核心代码位置")
for index, location in enumerate(lesson["core_code_locations"]):
    cols = st.columns([3, 1, 2, 1])
    cols[0].code(f"{location['file']}:{location['line']}")
    cols[1].write(location["kind"])
    cols[2].write(location["name"])
    if cols[3].button("查看源码", key=f"lesson-source-{index}"):
        st.session_state["source_file_path"] = location["file"]
        st.session_state["source_line"] = location["line"]
        st.switch_page("pages/9_Source_Browser.py")
if lesson.get("call_chains"):
    st.subheader("调用关系")
    for chain in lesson["call_chains"]:
        with st.container(border=True):
            st.markdown(f"**{chain['title']}**")
            st.write(" -> ".join(step["symbol"] for step in chain["steps"]))
            for edge_index, edge in enumerate(chain["edges"]):
                cols = st.columns([3, 4, 1])
                cols[0].code(f"{edge['file']}:{edge['line']}")
                cols[1].write(edge["expression"])
                if cols[2].button("查看源码", key=f"call-chain-{chain['id']}-{edge_index}"):
                    st.session_state["source_file_path"] = edge["file"]
                    st.session_state["source_line"] = edge["line"]
                    st.switch_page("pages/9_Source_Browser.py")
st.subheader("关键讲解")
for point in lesson["explanation"]:
    st.write(f"- {point}")
st.subheader("设计原因")
st.write(lesson["design_reason"])
st.subheader("容易出错的地方")
for pitfall in lesson["pitfalls"]:
    st.write(f"- {pitfall}")
st.subheader("本节总结")
st.write(lesson["summary"])

st.divider()
st.header("测验")
quiz = requests.post(f"{API_URL}/api/lessons/{lesson_id}/quiz", timeout=60).json()
answers: dict[str, str] = {}
for question in quiz["questions"]:
    st.markdown(f"**{question['type']}**")
    answers[question["id"]] = st.text_area(question["prompt"], key=question["id"])

if st.button("提交测验", type="primary"):
    result = requests.post(f"{API_URL}/api/quizzes/{quiz['id']}/submit", json=answers, timeout=60).json()
    st.metric("得分", result["score"])
    st.write(result["feedback"])
    st.write("推荐动作：" + result["recommended_action"])
    if result["missing_points"]:
        st.warning("缺失点：" + "；".join(result["missing_points"]))
    if result["score"] >= 80:
        st.success("本节已自动标记完成。")
    elif result["score"] >= 60:
        st.info("本节保持学习中，建议补齐缺失点后再测一次。")
    else:
        st.warning("本节已标记为需复习。")
