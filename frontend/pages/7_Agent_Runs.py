from __future__ import annotations

import os

import requests
import streamlit as st


API_URL = os.getenv("REPO_TUTOR_API_URL", "http://localhost:8000")

st.set_page_config(page_title="Agent 运行记录", page_icon="RT", layout="wide")
st.title("Agent 运行记录")

project_id = st.session_state.get("project_id")
if not project_id:
    st.info("请先在首页上传或选择项目。")
    st.stop()

runs_response = requests.get(f"{API_URL}/api/projects/{project_id}/agent-runs", timeout=30)
runs_response.raise_for_status()
runs = runs_response.json()["agent_runs"]

if not runs:
    st.info("当前项目还没有 Agent 运行记录。")
    st.stop()

run_options = {f"{run['started_at']} · {run['run_type']} · {run['status']}": run["id"] for run in runs}
selected_label = st.selectbox("选择运行记录", list(run_options.keys()))
run_id = run_options[selected_label]

run_response = requests.get(f"{API_URL}/api/agent-runs/{run_id}", timeout=30)
run_response.raise_for_status()
run = run_response.json()

cols = st.columns(4)
cols[0].metric("状态", run["status"])
cols[1].metric("类型", run["run_type"])
cols[2].metric("开始时间", run["started_at"])
cols[3].metric("结束时间", run["completed_at"] or "运行中")

if run.get("error"):
    st.error(run["error"])

st.subheader("节点事件")
st.dataframe(
    [
        {
            "时间": event["created_at"],
            "节点": event["step_name"],
            "状态": event["status"],
            "摘要": event["payload"],
        }
        for event in run["events"]
    ],
    use_container_width=True,
)

st.subheader("最终 State")
st.json(run["state"])

