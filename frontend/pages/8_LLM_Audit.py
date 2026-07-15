from __future__ import annotations

import os

import requests
import streamlit as st


API_URL = os.getenv("REPO_TUTOR_API_URL", "http://localhost:8000")

st.set_page_config(page_title="LLM 调用审计", page_icon="RT", layout="wide")
st.title("LLM 调用审计")

project_id = st.session_state.get("project_id")
if not project_id:
    st.info("请先在首页上传或选择项目。")
    st.stop()

try:
    response = requests.get(f"{API_URL}/api/projects/{project_id}/llm-call-logs", timeout=30)
    response.raise_for_status()
    call_logs = response.json()["llm_call_logs"]
except requests.RequestException as exc:
    st.error(f"后端接口不可用：{exc}")
    st.stop()

if not call_logs:
    st.info("当前项目还没有 LLM 调用记录。配置模型接口并生成课程后，这里会显示调用审计。")
    st.stop()

st.dataframe(
    [
        {
            "时间": item["created_at"],
            "课程": item["lesson_id"] or "-",
            "模型": item["model"],
            "状态": item["status"],
            "耗时(ms)": item["latency_ms"],
            "错误": item["error"],
        }
        for item in call_logs
    ],
    use_container_width=True,
)

options = {
    f"{item['created_at']} · {item['lesson_id'] or '-'} · {item['status']} · {item['model']}": item["id"]
    for item in call_logs
}
selected_label = st.selectbox("选择调用记录", list(options.keys()))
call_id = options[selected_label]

try:
    detail_response = requests.get(f"{API_URL}/api/llm-call-logs/{call_id}", timeout=30)
    detail_response.raise_for_status()
    detail = detail_response.json()
except requests.RequestException as exc:
    st.error(f"读取调用详情失败：{exc}")
    st.stop()

cols = st.columns(5)
cols[0].metric("状态", detail["status"])
cols[1].metric("模型", detail["model"])
cols[2].metric("课程", detail["lesson_id"] or "-")
cols[3].metric("Provider", detail["provider"])
cols[4].metric("耗时", f"{detail['latency_ms']} ms")

st.caption(detail["base_url"])
if detail.get("error"):
    st.error(detail["error"])

prompt_tab, response_tab = st.tabs(["Prompt", "Response"])
with prompt_tab:
    st.json(detail["prompt"])
with response_tab:
    st.json(detail["response"])
