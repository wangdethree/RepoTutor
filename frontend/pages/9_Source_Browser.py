from __future__ import annotations

import os

import requests
import streamlit as st


API_URL = os.getenv("REPO_TUTOR_API_URL", "http://localhost:8000")

st.set_page_config(page_title="源码浏览", page_icon="RT", layout="wide")
st.title("源码浏览")

project_id = st.session_state.get("project_id")
if not project_id:
    st.info("请先在首页上传或选择项目。")
    st.stop()

try:
    response = requests.get(f"{API_URL}/api/projects/{project_id}/source-files", timeout=30)
    response.raise_for_status()
    files = response.json()["files"]
except requests.RequestException as exc:
    st.error(f"后端接口不可用：{exc}")
    st.stop()

if not files:
    st.info("当前项目没有可浏览的源码文件。")
    st.stop()

left, right = st.columns([1, 2])
with left:
    module_types = ["全部"] + sorted({file["module_type"] for file in files})
    selected_type = st.selectbox("层级", module_types)
    keyword = st.text_input("搜索文件", placeholder="main.py / api / service")
    filtered = files
    if selected_type != "全部":
        filtered = [file for file in filtered if file["module_type"] == selected_type]
    if keyword.strip():
        lowered = keyword.strip().lower()
        filtered = [file for file in filtered if lowered in file["path"].lower()]

    if not filtered:
        st.warning("没有匹配的文件。")
        st.stop()

    options = {
        f"{file['path']} · {file['module_type']} · {file['line_count']} 行": file["path"] for file in filtered
    }
    selected_label = st.selectbox("文件", list(options.keys()))
    selected_path = options[selected_label]

with right:
    try:
        detail_response = requests.get(f"{API_URL}/api/projects/{project_id}/source-files/{selected_path}", timeout=30)
        detail_response.raise_for_status()
        detail = detail_response.json()
    except requests.RequestException as exc:
        st.error(f"读取源码失败：{exc}")
        st.stop()

    file_meta = detail["file"]
    metrics = st.columns(4)
    metrics[0].metric("层级", file_meta["module_type"])
    metrics[1].metric("行数", file_meta["line_count"])
    metrics[2].metric("重要度", file_meta["importance_score"])
    metrics[3].metric("被依赖次数", file_meta["imported_by"])

    st.caption(file_meta["summary"])
    st.code(detail["content"], language="python" if selected_path.endswith(".py") else "text", line_numbers=True)
