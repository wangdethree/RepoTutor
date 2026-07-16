from __future__ import annotations

import os

import requests
import streamlit as st


API_URL = os.getenv("REPO_TUTOR_API_URL", "http://localhost:8000")


def _mastery_label(level: str) -> str:
    return {
        "MASTERED": "已掌握",
        "PARTIAL": "部分掌握",
        "NEEDS_REVIEW": "需复习",
    }.get(level, level)


st.set_page_config(page_title="复习中心", page_icon="RT", layout="wide")
st.title("复习中心")

project_id = st.session_state.get("project_id")
if not project_id:
    st.info("请先在首页上传或选择项目。")
    st.stop()

try:
    response = requests.get(f"{API_URL}/api/projects/{project_id}/quiz-results", timeout=30)
    response.raise_for_status()
    results = response.json()["quiz_results"]
except requests.RequestException as exc:
    st.error(f"读取测验记录失败：{exc}")
    st.stop()

if not results:
    st.info("当前项目还没有测验记录。完成一次课程测验后，这里会生成复习材料。")
    st.stop()

weak_results = [result for result in results if result["score"] < 80]
metrics = st.columns(4)
metrics[0].metric("测验次数", len(results))
metrics[1].metric("待复习", len(weak_results))
metrics[2].metric("最高分", max(result["score"] for result in results))
metrics[3].metric("最近得分", results[0]["score"])

if weak_results:
    st.subheader("优先复习")
    for result in weak_results[:5]:
        with st.container(border=True):
            cols = st.columns([4, 1, 1])
            cols[0].markdown(f"**{result['lesson_order']}. {result['lesson_title']}**")
            cols[1].metric("得分", result["score"])
            cols[2].write(_mastery_label(result["mastery_level"]))
            if result["missing_points"]:
                st.warning("缺失点：" + "；".join(result["missing_points"]))
            if result["misconceptions"]:
                st.write("可能误区：" + "；".join(result["misconceptions"]))
            st.write("建议：" + result["recommended_action"])
            action_cols = st.columns(3)
            if action_cols[0].button("回到课程", key=f"review-lesson-{result['id']}"):
                st.session_state["lesson_id"] = result["lesson_id"]
                st.switch_page("pages/4_Lesson_Quiz.py")
            if action_cols[1].button("知识卡片", key=f"review-cards-{result['id']}"):
                st.session_state["lesson_id"] = result["lesson_id"]
                st.switch_page("pages/4_Lesson_Quiz.py")
            if result["score"] < 60 and action_cols[2].button("补充讲解", key=f"remedial-{result['id']}"):
                remediation_response = requests.post(
                    f"{API_URL}/api/quiz-results/{result['id']}/remediation",
                    timeout=60,
                )
                remediation_response.raise_for_status()
                st.session_state["lesson_id"] = result["lesson_id"]
                st.session_state[f"remediation_{result['lesson_id']}"] = remediation_response.json()
                st.switch_page("pages/4_Lesson_Quiz.py")

st.subheader("全部测验记录")
st.dataframe(
    [
        {
            "时间": result["created_at"],
            "课程": result["lesson_title"],
            "得分": result["score"],
            "掌握度": _mastery_label(result["mastery_level"]),
            "建议动作": result["recommended_action"],
        }
        for result in results
    ],
    use_container_width=True,
)
