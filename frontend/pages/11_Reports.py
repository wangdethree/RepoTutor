from __future__ import annotations

import os

import requests
import streamlit as st


API_URL = os.getenv("REPO_TUTOR_API_URL", "http://localhost:8000")

st.set_page_config(page_title="报告导出", page_icon="RT", layout="wide")
st.title("报告导出")

project_id = st.session_state.get("project_id")
if not project_id:
    st.info("请先在首页上传或选择项目。")
    st.stop()

try:
    response = requests.get(f"{API_URL}/api/projects/{project_id}/reports/learning", timeout=30)
    response.raise_for_status()
    markdown = response.json()["markdown"]
except requests.RequestException as exc:
    st.error(f"生成报告失败：{exc}")
    st.stop()

project_tab, lesson_tab = st.tabs(["项目报告", "课程报告"])

with project_tab:
    cols = st.columns([1, 1, 4])
    cols[0].download_button(
        "下载 Markdown",
        data=markdown,
        file_name="repotutor-learning-report.md",
        mime="text/markdown",
    )
    if cols[1].button("刷新报告"):
        st.rerun()

    preview_tab, source_tab = st.tabs(["预览", "Markdown"])
    with preview_tab:
        st.markdown(markdown)
    with source_tab:
        st.code(markdown, language="markdown")

with lesson_tab:
    try:
        plan_response = requests.get(f"{API_URL}/api/projects/{project_id}/learning-plan", timeout=30)
        plan_response.raise_for_status()
        lessons = plan_response.json()["lessons"]
    except requests.RequestException as exc:
        st.error(f"读取课程列表失败：{exc}")
        st.stop()

    if not lessons:
        st.info("当前学习路线还没有课程。")
        st.stop()

    lesson_options = {f"{lesson['order_index']}. {lesson['title']}": lesson["id"] for lesson in lessons}
    selected_label = st.selectbox("选择课程", list(lesson_options.keys()))
    selected_lesson_id = lesson_options[selected_label]
    lesson_response = requests.get(f"{API_URL}/api/lessons/{selected_lesson_id}/report.md", timeout=30)
    if lesson_response.status_code != 200:
        st.error(f"生成课程报告失败：{lesson_response.text}")
        st.stop()

    lesson_markdown = lesson_response.text
    lesson_cols = st.columns([1, 1, 4])
    lesson_cols[0].download_button(
        "下载课程 Markdown",
        data=lesson_markdown,
        file_name=f"{selected_lesson_id}-lesson-report.md",
        mime="text/markdown",
    )
    if lesson_cols[1].button("刷新课程报告"):
        st.rerun()

    lesson_preview_tab, lesson_source_tab = st.tabs(["预览", "Markdown"])
    with lesson_preview_tab:
        st.markdown(lesson_markdown)
    with lesson_source_tab:
        st.code(lesson_markdown, language="markdown")
