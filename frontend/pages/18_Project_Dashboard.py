from __future__ import annotations

import os

import requests
import streamlit as st


API_URL = os.getenv("REPO_TUTOR_API_URL", "http://localhost:8000")


def _status_label(status: str) -> str:
    return {
        "READY": "可展示",
        "BUILDING": "建设中",
        "NEEDS_SETUP": "待初始化",
    }.get(status, status)


def _level_label(level: str) -> str:
    return {
        "GOOD": "良好",
        "FAIR": "一般",
        "WEAK": "薄弱",
    }.get(level, level)


st.set_page_config(page_title="项目仪表盘", page_icon="RT", layout="wide")
st.title("项目仪表盘")

project_id = st.session_state.get("project_id")
if not project_id:
    st.info("请先在首页上传或选择项目。")
    st.stop()

try:
    response = requests.get(f"{API_URL}/api/projects/{project_id}/dashboard", timeout=30)
    response.raise_for_status()
    dashboard = response.json()
except requests.RequestException as exc:
    st.error(f"读取项目仪表盘失败：{exc}")
    st.stop()

st.subheader(dashboard["project_name"])
metrics = st.columns(3)
metrics[0].metric("总览评分", f"{dashboard['overall_score']}%")
metrics[1].metric("状态", _status_label(dashboard["status"]))
metrics[2].metric("维度", len(dashboard["dimensions"]))
st.progress(dashboard["overall_score"] / 100)

if dashboard["next_actions"]:
    st.subheader("下一步")
    for action in dashboard["next_actions"]:
        st.write(f"- {action}")

st.subheader("维度评分")
for dimension in dashboard["dimensions"]:
    with st.container(border=True):
        cols = st.columns([2, 1, 4, 1])
        cols[0].markdown(f"**{dimension['title']}**")
        cols[1].metric(_level_label(dimension["level"]), f"{dimension['score']}%")
        cols[2].write(dimension["detail"])
        if cols[3].button("打开", key=f"dashboard-{dimension['id']}"):
            st.switch_page(dimension["page"])
        st.progress(dimension["score"] / 100)
