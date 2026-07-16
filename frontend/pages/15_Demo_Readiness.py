from __future__ import annotations

import os

import requests
import streamlit as st


API_URL = os.getenv("REPO_TUTOR_API_URL", "http://localhost:8000")


def _status_label(status: str) -> str:
    return {
        "DONE": "已完成",
        "IN_PROGRESS": "进行中",
        "TODO": "待完成",
    }.get(status, status)


st.set_page_config(page_title="演示准备", page_icon="RT", layout="wide")
st.title("演示准备")

project_id = st.session_state.get("project_id")
if not project_id:
    st.info("请先在首页上传或选择项目。")
    st.stop()

try:
    response = requests.get(f"{API_URL}/api/projects/{project_id}/demo-readiness", timeout=30)
    response.raise_for_status()
    readiness = response.json()
except requests.RequestException as exc:
    st.error(f"读取演示准备清单失败：{exc}")
    st.stop()

st.subheader(readiness["project_name"])
metrics = st.columns(4)
metrics[0].metric("演示准备度", f"{readiness['readiness_score']}%")
metrics[1].metric("已完成项", readiness["completed_items"])
metrics[2].metric("总检查项", readiness["total_items"])
metrics[3].metric("状态", "可演示" if readiness["ready_for_demo"] else "继续补齐")
st.progress(readiness["readiness_score"] / 100)

if readiness["next_actions"]:
    st.subheader("下一步")
    for action in readiness["next_actions"]:
        st.write(f"- {action}")

st.subheader("闭环检查")
for item in readiness["items"]:
    with st.container(border=True):
        cols = st.columns([1, 3, 5, 1])
        cols[0].write(_status_label(item["status"]))
        cols[1].markdown(f"**{item['title']}**")
        cols[2].write(item["detail"])
        if cols[3].button("打开", key=f"demo-readiness-{item['id']}"):
            st.switch_page(item["page"])
        if item["status"] != "DONE":
            st.caption(item["action"])
