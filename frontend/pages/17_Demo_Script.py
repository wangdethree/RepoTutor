from __future__ import annotations

import os

import requests
import streamlit as st


API_URL = os.getenv("REPO_TUTOR_API_URL", "http://localhost:8000")


st.set_page_config(page_title="演示讲稿", page_icon="RT", layout="wide")
st.title("演示讲稿")

project_id = st.session_state.get("project_id")
if not project_id:
    st.info("请先在首页上传或选择项目。")
    st.stop()

try:
    response = requests.get(f"{API_URL}/api/projects/{project_id}/demo-script", timeout=30)
    response.raise_for_status()
    script = response.json()
except requests.RequestException as exc:
    st.error(f"读取演示讲稿失败：{exc}")
    st.stop()

st.subheader(script["title"])
metrics = st.columns(3)
metrics[0].metric("预计时长", f"{script['estimated_minutes']} 分钟")
metrics[1].metric("准备度", f"{script['readiness_score']}%")
metrics[2].metric("段落数", len(script["sections"]))

st.success(script["opening_sentence"])

for section in script["sections"]:
    with st.container(border=True):
        cols = st.columns([4, 1, 1])
        cols[0].markdown(f"**{section['title']}**")
        cols[1].metric("时长", f"{section['duration_minutes']} 分钟")
        if cols[2].button("打开", key=f"demo-script-{section['id']}"):
            st.switch_page(section["page"])

        st.caption("讲述要点")
        for point in section["talking_points"]:
            st.write(f"- {point}")

        st.caption("证据或补充")
        for item in section["evidence"]:
            st.write(f"- {item}")

st.info(script["closing_sentence"])
