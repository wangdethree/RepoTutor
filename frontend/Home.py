from __future__ import annotations

import os

import requests
import streamlit as st


API_URL = os.getenv("REPO_TUTOR_API_URL", "http://localhost:8000")

st.set_page_config(page_title="RepoTutor", page_icon="RT", layout="wide")
st.title("RepoTutor")
st.caption("上传 FastAPI 项目 ZIP，生成架构图、学习路线、课程和测验。")

with st.sidebar:
    st.subheader("当前项目")
    current_project_id = st.session_state.get("project_id")
    if current_project_id:
        st.code(current_project_id)
    else:
        st.info("尚未上传项目")

st.header("项目导入")

project_name = st.text_input("项目名称", value="FastAPI Demo")
zip_file = st.file_uploader("上传 ZIP 项目", type=["zip"])

col1, col2 = st.columns(2)
with col1:
    python_level = st.selectbox("Python 水平", ["入门", "基础", "熟练"])
    learning_goal = st.selectbox("学习目标", ["看懂项目结构", "掌握 FastAPI 开发", "准备项目面试", "学会修改现有项目"])
with col2:
    fastapi_level = st.selectbox("FastAPI 水平", ["未学习", "了解基础", "做过简单项目"])
    daily_time = st.selectbox("每天可用时间", ["30 分钟", "1 小时", "2 小时"])

if st.button("开始分析", type="primary", disabled=zip_file is None):
    files = {"zip_file": (zip_file.name, zip_file.getvalue(), "application/zip")}
    data = {
        "project_name": project_name,
        "python_level": python_level,
        "fastapi_level": fastapi_level,
        "learning_goal": learning_goal,
        "daily_time": daily_time,
    }
    with st.status("上传并分析项目", expanded=True) as status:
        response = requests.post(f"{API_URL}/api/projects/upload", data=data, files=files, timeout=120)
        if response.status_code >= 400:
            st.error(response.text)
            st.stop()
        project = response.json()["project"]
        project_id = project["id"]
        st.session_state["project_id"] = project_id
        st.write("ZIP 已安全解压")

        analysis_response = requests.post(f"{API_URL}/api/projects/{project_id}/analyze", timeout=120)
        analysis_response.raise_for_status()
        st.write("静态分析完成")

        diagrams_response = requests.post(f"{API_URL}/api/projects/{project_id}/diagrams/generate", timeout=120)
        diagrams_response.raise_for_status()
        st.write("架构图生成完成")

        plan_response = requests.post(f"{API_URL}/api/projects/{project_id}/learning-plan", timeout=120)
        plan_response.raise_for_status()
        st.write("学习路线生成完成")
        status.update(label="分析完成", state="complete")

    st.success("项目已导入，可以从左侧页面查看结果。")

st.divider()
st.subheader("最近项目")
try:
    projects = requests.get(f"{API_URL}/api/projects", timeout=20).json()["projects"]
    for project in projects[:8]:
        cols = st.columns([3, 2, 2, 1])
        cols[0].write(project["name"])
        cols[1].write(project.get("project_type") or "待分析")
        cols[2].write(project["analysis_status"])
        if cols[3].button("选择", key=project["id"]):
            st.session_state["project_id"] = project["id"]
            st.rerun()
except requests.RequestException:
    st.warning("后端服务暂不可用，请确认 FastAPI 已启动。")

