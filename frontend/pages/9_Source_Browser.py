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

if st.session_state.get("lesson_id"):
    if st.button("返回课程"):
        st.switch_page("pages/4_Lesson_Quiz.py")

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

    options = {f"{file['path']} · {file['module_type']} · {file['line_count']} 行": file["path"] for file in filtered}
    option_labels = list(options.keys())
    option_paths = list(options.values())
    target_path = st.session_state.get("source_file_path")
    default_index = option_paths.index(target_path) if target_path in option_paths else 0
    selected_label = st.selectbox("文件", option_labels, index=default_index)
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
    target_line = st.session_state.get("source_line") if selected_path == st.session_state.get("source_file_path") else None
    metrics = st.columns(4)
    metrics[0].metric("层级", file_meta["module_type"])
    metrics[1].metric("行数", file_meta["line_count"])
    metrics[2].metric("重要度", file_meta["importance_score"])
    metrics[3].metric("被依赖次数", file_meta["imported_by"])

    st.caption(file_meta["summary"])
    if target_line:
        line_number = int(target_line)
        focus_lines = detail["lines"][max(0, line_number - 4) : line_number + 3]
        st.info(f"当前引用位置：{selected_path}:{line_number}")
        st.code(
            "\n".join(f"{line['number']}: {line['text']}" for line in focus_lines),
            language="python" if selected_path.endswith(".py") else "text",
        )
    st.code(detail["content"], language="python" if selected_path.endswith(".py") else "text", line_numbers=True)
