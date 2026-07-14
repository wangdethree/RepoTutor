from __future__ import annotations

import os

import requests
import streamlit as st


API_URL = os.getenv("REPO_TUTOR_API_URL", "http://localhost:8000")

st.set_page_config(page_title="项目概览", page_icon="RT", layout="wide")
st.title("项目概览")

project_id = st.session_state.get("project_id")
if not project_id:
    st.info("请先在首页上传或选择项目。")
    st.stop()

analysis = requests.get(f"{API_URL}/api/projects/{project_id}/analysis", timeout=60).json()
summary = analysis["summary"]

metrics = st.columns(7)
metrics[0].metric("项目类型", summary["project_type"])
metrics[1].metric("文件数", summary["file_count"])
metrics[2].metric("Python 文件", summary["python_file_count"])
metrics[3].metric("代码行数", summary["line_count"])
metrics[4].metric("路由数", summary["route_count"])
metrics[5].metric("模型数", summary["model_count"])
metrics[6].metric("难度", summary["difficulty"])

st.subheader("技术栈")
st.write("、".join(summary["tech_stack"]))

st.subheader("核心模块")
st.dataframe(
    [
        {
            "文件": file["path"],
            "层级": file["module_type"],
            "行数": file["line_count"],
            "被依赖次数": file["imported_by"],
            "重要度": file["importance_score"],
            "说明": file["summary"],
        }
        for file in analysis["files"][:20]
    ],
    use_container_width=True,
)

st.subheader("路由")
st.dataframe(analysis["routes"], use_container_width=True)

st.subheader("模型与 Schema")
left, right = st.columns(2)
left.dataframe(analysis["models"], use_container_width=True)
right.dataframe(analysis["schemas"], use_container_width=True)

