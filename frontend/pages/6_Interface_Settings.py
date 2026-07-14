from __future__ import annotations

import os

import requests
import streamlit as st


API_URL = os.getenv("REPO_TUTOR_API_URL", "http://localhost:8000")

st.set_page_config(page_title="接口配置", page_icon="RT", layout="wide")
st.title("接口配置")

try:
    config_response = requests.get(f"{API_URL}/api/settings/llm", timeout=20)
    config_response.raise_for_status()
    config = config_response.json()
except requests.RequestException as exc:
    st.error(f"后端接口不可用：{exc}")
    st.stop()

left, right = st.columns(2)
left.metric("模型接口", "已配置" if config["api_key_configured"] else "未配置")
right.metric("当前模式", "LLM 增强" if config["api_key_configured"] else "确定性离线规则")

with st.form("llm_settings_form"):
    base_url = st.text_input("Base URL", value=config["base_url"])
    model = st.text_input("模型名称", value=config["model"])
    temperature = st.slider("Temperature", min_value=0.0, max_value=2.0, value=float(config["temperature"]), step=0.1)
    api_key = st.text_input(
        "API Key",
        value=config["api_key_masked"],
        type="password",
        help="留空或保留脱敏值不会覆盖已保存的 Key。",
    )
    clear_api_key = st.checkbox("清除已保存的 API Key")
    submitted = st.form_submit_button("保存配置", type="primary")

if submitted:
    payload = {
        "base_url": base_url,
        "model": model,
        "temperature": temperature,
        "api_key": api_key,
        "clear_api_key": clear_api_key,
    }
    response = requests.put(f"{API_URL}/api/settings/llm", json=payload, timeout=20)
    if response.status_code >= 400:
        st.error(response.text)
    else:
        st.success("配置已保存")
        st.rerun()

if st.button("检查配置"):
    response = requests.post(f"{API_URL}/api/settings/llm/validate", timeout=20)
    response.raise_for_status()
    result = response.json()
    if result["ok"]:
        st.success(result["message"])
    else:
        st.warning(result["message"])
        for problem in result["problems"]:
            st.write(f"- {problem}")

st.subheader("当前来源")
st.dataframe(
    [
        {"配置项": "API Key", "来源": config["api_key_source"], "值": config["api_key_masked"] or "未配置"},
        {"配置项": "Base URL", "来源": config["base_url_source"], "值": config["base_url"]},
        {"配置项": "Model", "来源": config["model_source"], "值": config["model"]},
        {"配置项": "Temperature", "来源": config["temperature_source"], "值": config["temperature"]},
    ],
    use_container_width=True,
)

