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
    st.write(result["answer"])
    st.subheader("事实依据")
    for fact in result["facts"]:
        st.write(f"- {fact}")
    st.subheader("推断说明")
    for inference in result["inferences"]:
        st.write(f"- {inference}")
    st.subheader("引用位置")
    st.dataframe(result["references"], use_container_width=True)

