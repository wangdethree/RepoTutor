from __future__ import annotations

import os

import requests
import streamlit as st


API_URL = os.getenv("REPO_TUTOR_API_URL", "http://localhost:8000")


def _risk_label(value: str) -> str:
    return {
        "LOW": "低",
        "MEDIUM": "中",
        "HIGH": "高",
    }.get(value, value)


st.set_page_config(page_title="增量学习", page_icon="RT", layout="wide")
st.title("增量学习")

project_id = st.session_state.get("project_id")
if not project_id:
    st.info("请先在首页上传或选择项目。")
    st.stop()

sample_diff = """diff --git a/app/services/order_service.py b/app/services/order_service.py
--- a/app/services/order_service.py
+++ b/app/services/order_service.py
@@ -1,2 +1,3 @@
+validate_coupon(order)
"""

diff_text = st.text_area("粘贴 git diff", value="", placeholder=sample_diff, height=220)

if st.button("生成增量学习建议", type="primary", disabled=not diff_text.strip()):
    try:
        response = requests.post(
            f"{API_URL}/api/projects/{project_id}/incremental-learning",
            json={"diff": diff_text},
            timeout=60,
        )
        response.raise_for_status()
        st.session_state["incremental_learning_result"] = response.json()
    except requests.RequestException as exc:
        st.error(f"生成增量学习建议失败：{exc}")
        st.stop()

payload = st.session_state.get("incremental_learning_result")
if not payload:
    st.info("粘贴一次 git diff 后生成增量学习建议。")
    st.stop()

st.subheader(payload["title"])
metrics = st.columns(3)
metrics[0].metric("风险", _risk_label(payload["risk_level"]))
metrics[1].metric("推荐课程", len(payload["recommended_lessons"]))
metrics[2].metric("源码检查点", len(payload["source_checkpoints"]))
st.write(payload["change_summary"])

lesson_tab, source_tab, practice_tab, question_tab = st.tabs(["复习课程", "源码检查", "练习任务", "追问清单"])

with lesson_tab:
    if payload["recommended_lessons"]:
        for lesson in payload["recommended_lessons"]:
            with st.container(border=True):
                cols = st.columns([4, 2, 1])
                cols[0].markdown(f"**{lesson['order_index']}. {lesson['title']}**")
                cols[1].write("；".join(lesson["matched_files"]))
                if cols[2].button("复习", key=f"incremental-lesson-{lesson['lesson_id']}"):
                    st.session_state["lesson_id"] = lesson["lesson_id"]
                    st.switch_page("pages/4_Lesson_Quiz.py")
                st.caption(lesson["reason"])
    else:
        st.info("当前 diff 没有命中学习路线课程。")

with source_tab:
    for index, checkpoint in enumerate(payload["source_checkpoints"]):
        with st.container(border=True):
            cols = st.columns([4, 5, 1])
            cols[0].code(checkpoint["file"])
            cols[1].write(checkpoint["checkpoint"])
            if cols[2].button("源码", key=f"incremental-source-{index}"):
                st.session_state["source_file_path"] = checkpoint["file"]
                st.session_state["source_line"] = 1
                st.switch_page("pages/9_Source_Browser.py")

with practice_tab:
    for task in payload["practice_tasks"]:
        with st.container(border=True):
            st.markdown(f"**{task['title']}**")
            st.write(task["objective"])
            st.caption(task["acceptance"])

with question_tab:
    st.caption("下一步")
    for step in payload["next_steps"]:
        st.write(f"- {step}")
    st.caption("可以继续追问")
    for question in payload["questions_to_ask"]:
        st.write(f"- {question}")
