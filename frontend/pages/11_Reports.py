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
