from __future__ import annotations

import os

import requests
import streamlit as st


API_URL = os.getenv("REPO_TUTOR_API_URL", "http://localhost:8000")

st.set_page_config(page_title="面试准备", page_icon="RT", layout="wide")
st.title("面试准备")

project_id = st.session_state.get("project_id")
if not project_id:
    st.info("请先在首页上传或选择项目。")
    st.stop()

try:
    response = requests.get(f"{API_URL}/api/projects/{project_id}/interview-kit", timeout=30)
    response.raise_for_status()
    kit = response.json()
except requests.RequestException as exc:
    st.error(f"读取面试讲解包失败：{exc}")
    st.stop()

st.subheader(kit["title"])
st.success(kit["elevator_pitch"])

metrics = st.columns(3)
metrics[0].metric("高频问题", len(kit["questions"]))
metrics[1].metric("源码证据", len(kit["core_references"]))
metrics[2].metric("事实校验", "已通过" if kit["fact_checked"] else "未通过")

left, right = st.columns([1, 1])
with left:
    st.subheader("讲解路径")
    for index, item in enumerate(kit["architecture_story"], start=1):
        st.write(f"{index}. {item}")

    st.subheader("技术亮点")
    for item in kit["technical_highlights"]:
        st.write(f"- {item}")

with right:
    st.subheader("权衡与风险")
    for item in kit["tradeoffs"]:
        st.write(f"- {item}")
    for item in kit["risk_points"]:
        st.warning(item)

st.subheader("高频问答")
for question in kit["questions"]:
    with st.container(border=True):
        st.caption(question["category"])
        st.markdown(f"**{question['question']}**")
        for point in question["answer_points"]:
            st.write(f"- {point}")
        references = question.get("references", [])
        if references:
            st.write("源码证据")
            ref_cols = st.columns(min(3, len(references)))
            for index, reference in enumerate(references):
                column = ref_cols[index % len(ref_cols)]
                file_name = reference["file"].split("/")[-1]
                column.caption(f"{file_name}:{reference['line']}")
                if column.button("查看源码", key=f"{question['id']}-{index}", help=reference.get("name", "查看源码")):
                    st.session_state["source_file_path"] = reference["file"]
                    st.session_state["source_line"] = reference["line"]
                    st.switch_page("pages/9_Source_Browser.py")

st.subheader("收尾总结")
st.info(kit["closing_summary"])
