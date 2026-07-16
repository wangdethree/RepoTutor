from __future__ import annotations

import os

import requests
import streamlit as st


API_URL = os.getenv("REPO_TUTOR_API_URL", "http://localhost:8000")


def _priority_label(priority: str) -> str:
    return {
        "HIGH": "高",
        "MEDIUM": "中",
        "LOW": "低",
        "NONE": "无",
    }.get(priority, priority)


st.set_page_config(page_title="项目改进建议", page_icon="RT", layout="wide")
st.title("项目改进建议")

project_id = st.session_state.get("project_id")
if not project_id:
    st.info("请先在首页上传或选择项目。")
    st.stop()

try:
    response = requests.get(
        f"{API_URL}/api/projects/{project_id}/improvement-suggestions",
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
except requests.RequestException as exc:
    st.error(f"读取项目改进建议失败：{exc}")
    st.stop()

st.subheader(payload["project_name"])
counts = payload["priority_counts"]
metrics = st.columns(5)
metrics[0].metric("建议数", payload["suggestion_count"])
metrics[1].metric("最高优先级", _priority_label(payload["highest_priority"]))
metrics[2].metric("高优先级", counts["HIGH"])
metrics[3].metric("中优先级", counts["MEDIUM"])
metrics[4].metric("低优先级", counts["LOW"])

if payload["next_actions"]:
    st.subheader("下一步")
    for action in payload["next_actions"]:
        st.write(f"- {action}")

if not payload["suggestions"]:
    st.success("当前没有明显的 V1.2 改进项。")
    st.stop()

for suggestion in payload["suggestions"]:
    with st.container(border=True):
        header_cols = st.columns([1, 1, 4, 1])
        header_cols[0].write(_priority_label(suggestion["priority"]))
        header_cols[1].write(suggestion["category"])
        header_cols[2].markdown(f"**{suggestion['title']}**")
        if header_cols[3].button("打开", key=f"improve-open-{suggestion['id']}"):
            st.switch_page(suggestion["page"])

        st.write(suggestion["reason"])
        if suggestion.get("interview_talking_point"):
            st.caption("面试说法")
            st.info(suggestion["interview_talking_point"])
        for action in suggestion["action_items"]:
            st.write(f"- {action}")

        if suggestion["related_files"]:
            st.caption("关联文件")
            file_cols = st.columns(2)
            for index, file_path in enumerate(suggestion["related_files"]):
                col = file_cols[index % 2]
                if col.button(file_path, key=f"improve-file-{suggestion['id']}-{index}"):
                    st.session_state["source_file_path"] = file_path
                    st.session_state["source_line"] = 1
                    st.switch_page("pages/9_Source_Browser.py")

        if suggestion["related_lessons"]:
            st.caption("关联课程")
            for lesson in suggestion["related_lessons"]:
                cols = st.columns([4, 1])
                cols[0].write(f"{lesson['order_index']}. {lesson['title']}")
                if cols[1].button("学习", key=f"improve-lesson-{suggestion['id']}-{lesson['id']}"):
                    st.session_state["lesson_id"] = lesson["id"]
                    st.switch_page("pages/4_Lesson_Quiz.py")
