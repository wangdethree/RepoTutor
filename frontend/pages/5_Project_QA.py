from __future__ import annotations

import os

import requests
import streamlit as st


API_URL = os.getenv("REPO_TUTOR_API_URL", "http://localhost:8000")

st.set_page_config(page_title="项目问答", page_icon="RT", layout="wide")
st.title("项目问答")

project_id = st.session_state.get("project_id")
if not project_id:
    st.info("请先在首页上传或选择项目。")
    st.stop()

question = st.text_area("围绕当前项目提问", placeholder="例如：登录流程经过哪些函数？JWT 过期时间在哪里配置？")

if st.button("提问", type="primary", disabled=not question.strip()):
    response = requests.post(
        f"{API_URL}/api/projects/{project_id}/ask",
        json={"question": question},
        timeout=60,
    )
    if response.status_code >= 400:
        st.error(response.text)
        st.stop()
    result = response.json()
    st.subheader("回答")
    cols = st.columns(3)
    cols[0].metric("生成模式", result.get("generation_mode", "deterministic"))
    cols[1].metric("事实校验", "通过" if result.get("fact_checked") else "未标记")
    cols[2].metric("引用数", len(result.get("references", [])))
    if result.get("llm_error"):
        st.warning(f"LLM 增强已回退：{result['llm_error']}")
    st.write(result["answer"])
    st.subheader("事实依据")
    for fact in result["facts"]:
        st.write(f"- {fact}")
    st.subheader("推断说明")
    for inference in result["inferences"]:
        st.write(f"- {inference}")
    st.subheader("引用位置")
    for index, reference in enumerate(result["references"]):
        cols = st.columns([3, 1, 2, 1])
        cols[0].code(f"{reference['file']}:{reference['line']}")
        cols[1].write(reference["kind"])
        cols[2].write(reference["name"])
        if cols[3].button("查看源码", key=f"qa-source-{index}"):
            st.session_state["source_file_path"] = reference["file"]
            st.session_state["source_line"] = reference["line"]
            st.switch_page("pages/9_Source_Browser.py")
