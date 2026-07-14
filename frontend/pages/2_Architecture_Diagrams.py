from __future__ import annotations

import os

import requests
import streamlit as st


API_URL = os.getenv("REPO_TUTOR_API_URL", "http://localhost:8000")

st.set_page_config(page_title="架构图", page_icon="RT", layout="wide")
st.title("项目架构图")

project_id = st.session_state.get("project_id")
if not project_id:
    st.info("请先在首页上传或选择项目。")
    st.stop()

payload = requests.get(f"{API_URL}/api/projects/{project_id}/diagrams", timeout=60).json()
diagrams = payload.get("diagrams", [])
if not diagrams:
    if st.button("生成架构图"):
        requests.post(f"{API_URL}/api/projects/{project_id}/diagrams/generate", timeout=120).raise_for_status()
        st.rerun()
    st.stop()

titles = {diagram["title"]: diagram for diagram in diagrams}
selected_title = st.selectbox("图类型", list(titles.keys()))
diagram = titles[selected_title]

st.caption(diagram["description"])
if diagram["format"] == "mermaid":
    st.code(diagram["source"], language="mermaid")
else:
    st.code(diagram["source"], language="plantuml")

st.download_button(
    "下载源码",
    data=diagram["source"],
    file_name=f"{diagram['id']}.{diagram['format']}",
    mime="text/plain",
)

