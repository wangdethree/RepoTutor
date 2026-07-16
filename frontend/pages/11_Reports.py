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

project_tab, lesson_tab, demo_tab, change_tab = st.tabs(["项目报告", "课程报告", "演示讲稿", "变更报告"])

with project_tab:
    try:
        response = requests.get(f"{API_URL}/api/projects/{project_id}/reports/learning", timeout=30)
        response.raise_for_status()
        markdown = response.json()["markdown"]
    except requests.RequestException as exc:
        st.error(f"生成项目报告失败：{exc}")
    else:
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
        lessons = []

    if not lessons:
        st.info("当前学习路线还没有课程。")
    else:
        lesson_options = {f"{lesson['order_index']}. {lesson['title']}": lesson["id"] for lesson in lessons}
        selected_label = st.selectbox("选择课程", list(lesson_options.keys()))
        selected_lesson_id = lesson_options[selected_label]
        lesson_response = requests.get(f"{API_URL}/api/lessons/{selected_lesson_id}/report.md", timeout=30)
        if lesson_response.status_code != 200:
            st.error(f"生成课程报告失败：{lesson_response.text}")
        else:
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

with demo_tab:
    try:
        demo_response = requests.get(f"{API_URL}/api/projects/{project_id}/demo-script.md", timeout=30)
        demo_response.raise_for_status()
    except requests.RequestException as exc:
        st.error(f"生成演示讲稿失败：{exc}")
    else:
        demo_markdown = demo_response.text
        demo_cols = st.columns([1, 1, 4])
        demo_cols[0].download_button(
            "下载演示讲稿",
            data=demo_markdown,
            file_name=f"{project_id}-demo-script.md",
            mime="text/markdown",
        )
        if demo_cols[1].button("刷新演示讲稿"):
            st.rerun()

        demo_preview_tab, demo_source_tab = st.tabs(["预览", "Markdown"])
        with demo_preview_tab:
            st.markdown(demo_markdown)
        with demo_source_tab:
            st.code(demo_markdown, language="markdown")

with change_tab:
    sample_diff = """diff --git a/app/api/orders.py b/app/api/orders.py
--- a/app/api/orders.py
+++ b/app/api/orders.py
@@ -1,2 +1,3 @@
+include_coupon = True
"""
    change_diff = st.text_area("粘贴 git diff", value="", placeholder=sample_diff, height=220)
    if st.button("生成变更报告", type="primary", disabled=not change_diff.strip()):
        try:
            pr_response = requests.post(
                f"{API_URL}/api/projects/{project_id}/pr-review.md",
                json={"diff": change_diff},
                timeout=60,
            )
            pr_response.raise_for_status()
            incremental_response = requests.post(
                f"{API_URL}/api/projects/{project_id}/incremental-learning.md",
                json={"diff": change_diff},
                timeout=60,
            )
            incremental_response.raise_for_status()
        except requests.RequestException as exc:
            st.error(f"生成变更报告失败：{exc}")
        else:
            st.session_state["report_pr_review_markdown"] = pr_response.text
            st.session_state["report_incremental_learning_markdown"] = incremental_response.text

    pr_markdown = st.session_state.get("report_pr_review_markdown")
    incremental_markdown = st.session_state.get("report_incremental_learning_markdown")
    if pr_markdown or incremental_markdown:
        download_cols = st.columns([1, 1, 4])
        if pr_markdown:
            download_cols[0].download_button(
                "下载 PR 讲解包",
                data=pr_markdown,
                file_name=f"{project_id}-pr-review.md",
                mime="text/markdown",
            )
        if incremental_markdown:
            download_cols[1].download_button(
                "下载增量学习建议",
                data=incremental_markdown,
                file_name=f"{project_id}-incremental-learning.md",
                mime="text/markdown",
            )

        pr_tab, incremental_tab = st.tabs(["PR 讲解包", "增量学习建议"])
        with pr_tab:
            if pr_markdown:
                st.markdown(pr_markdown)
        with incremental_tab:
            if incremental_markdown:
                st.markdown(incremental_markdown)
    else:
        st.info("粘贴一次 git diff 后可生成 PR 讲解包和增量学习建议。")
