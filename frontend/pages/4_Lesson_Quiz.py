from __future__ import annotations

import os

import requests
import streamlit as st


API_URL = os.getenv("REPO_TUTOR_API_URL", "http://localhost:8000")

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

st.header(lesson["title"])
st.subheader("为什么要学")
st.write(lesson["why"])
st.subheader("学习目标")
st.write("；".join(lesson["objectives"]))
st.subheader("核心代码位置")
st.dataframe(lesson["core_code_locations"], use_container_width=True)
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

