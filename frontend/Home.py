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

st.subheader("快速体验")
demo_cols = st.columns([1, 3])
if demo_cols[0].button("加载示例项目", type="primary"):
    with st.status("准备内置 FastAPI Shop Demo", expanded=True) as status:
        demo_response = requests.post(
            f"{API_URL}/api/demo-projects/fastapi-shop",
            json={
                "python_level": "基础",
                "fastapi_level": "了解基础",
                "learning_goals": ["看懂项目结构", "准备项目面试"],
                "daily_time": "1 小时",
            },
            timeout=180,
        )
        if demo_response.status_code >= 400:
            st.error(demo_response.text)
            st.stop()
        payload = demo_response.json()
        st.session_state["project_id"] = payload["project"]["id"]
        st.write(f"架构图：{payload['demo']['diagrams']} 张")
        st.write(f"课程：{payload['demo']['lessons']} 节")
        status.update(label="示例项目已准备好", state="complete")
    st.success("已选择 FastAPI Shop Demo。")
    st.rerun()
demo_cols[1].caption("FastAPI Shop Demo")

st.divider()

project_name = st.text_input("项目名称", value="FastAPI Demo")
import_mode = st.radio("导入方式", ["上传 ZIP", "GitHub URL"], horizontal=True)
zip_file = None
github_url = ""
if import_mode == "上传 ZIP":
    zip_file = st.file_uploader("上传 ZIP 项目", type=["zip"])
else:
    github_url = st.text_input("GitHub 仓库 URL", placeholder="https://github.com/owner/repo")

col1, col2 = st.columns(2)
with col1:
    python_level = st.selectbox("Python 水平", ["入门", "基础", "熟练"])
    learning_goals = st.multiselect(
        "学习目标",
        ["看懂项目结构", "掌握 FastAPI 开发", "准备项目面试", "学会修改现有项目"],
        default=["看懂项目结构"],
    )
with col2:
    fastapi_level = st.selectbox("FastAPI 水平", ["未学习", "了解基础", "做过简单项目"])
    daily_time = st.selectbox("每天可用时间", ["30 分钟", "1 小时", "2 小时"])

can_start = zip_file is not None if import_mode == "上传 ZIP" else bool(github_url.strip())

if st.button("开始分析", type="primary", disabled=not can_start):
    profile_payload = {
        "project_name": project_name,
        "python_level": python_level,
        "fastapi_level": fastapi_level,
        "learning_goal": "、".join(learning_goals),
        "learning_goals": learning_goals,
        "daily_time": daily_time,
    }
    with st.status("上传并分析项目", expanded=True) as status:
        if import_mode == "上传 ZIP":
            files = {"zip_file": (zip_file.name, zip_file.getvalue(), "application/zip")}
            form_payload = {**profile_payload, "learning_goals": ",".join(learning_goals)}
            response = requests.post(f"{API_URL}/api/projects/upload", data=form_payload, files=files, timeout=120)
        else:
            payload = {**profile_payload, "github_url": github_url}
            response = requests.post(f"{API_URL}/api/projects/import-github", json=payload, timeout=180)
        if response.status_code >= 400:
            st.error(response.text)
            st.stop()
        project = response.json()["project"]
        project_id = project["id"]
        st.session_state["project_id"] = project_id
        st.write("项目源码已安全导入")

        run_response = requests.post(f"{API_URL}/api/projects/{project_id}/agent-runs/onboarding", timeout=180)
        run_response.raise_for_status()
        run = run_response.json()
        st.session_state["agent_run_id"] = run["id"]
        st.write("Agent 工作流完成")
        st.write(f"运行记录：{run['id']}")
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
