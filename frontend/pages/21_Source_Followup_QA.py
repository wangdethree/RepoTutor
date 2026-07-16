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


def _open_source(file_path: str, line: int | None = None) -> None:
    st.session_state["source_file_path"] = file_path
    if line:
        st.session_state["source_line"] = line
    else:
        st.session_state.pop("source_line", None)
    st.switch_page("pages/9_Source_Browser.py")


def _load_source_files(project_id: str) -> list[dict]:
    try:
        response = requests.get(f"{API_URL}/api/projects/{project_id}/source-files", timeout=30)
        response.raise_for_status()
    except requests.RequestException:
        return []
    return response.json().get("files", [])


st.set_page_config(page_title="源码追问", page_icon="RT", layout="wide")
st.title("源码追问")

project_id = st.session_state.get("project_id")
if not project_id:
    st.info("请先在首页上传或选择项目。")
    st.stop()

source_files = _load_source_files(project_id)
sample_diff = """diff --git a/app/api/orders.py b/app/api/orders.py
--- a/app/api/orders.py
+++ b/app/api/orders.py
@@ -1,2 +1,3 @@
+include_coupon = True
"""

question = st.text_area(
    "追问内容",
    placeholder="例如：订单接口这次改动要重点看哪里？create_order 的调用链会影响哪些测试？",
    height=110,
)

left, right = st.columns(2)
with left:
    file_path = ""
    if source_files:
        options = {"不限定文件": ""}
        options.update({f"{file['path']} · {file['module_type']}": file["path"] for file in source_files})
        selected_label = st.selectbox("文件范围", list(options.keys()))
        file_path = options[selected_label]
    else:
        file_path = st.text_input("文件范围", placeholder="app/api/orders.py")
    symbol_name = st.text_input("函数或类", placeholder="create_order")

with right:
    diff_text = st.text_area("可选 git diff", value="", placeholder=sample_diff, height=170)

if st.button("生成源码追问", type="primary", disabled=not question.strip()):
    try:
        response = requests.post(
            f"{API_URL}/api/projects/{project_id}/contextual-qa",
            json={
                "question": question,
                "file_path": file_path,
                "symbol_name": symbol_name,
                "diff": diff_text,
            },
            timeout=60,
        )
        response.raise_for_status()
        st.session_state["contextual_qa_result"] = response.json()
    except requests.RequestException as exc:
        st.error(f"生成源码追问失败：{exc}")
        st.stop()

result = st.session_state.get("contextual_qa_result")
if not result:
    st.info("输入问题后生成源码追问；限定文件、函数或粘贴 diff 可以让回答更聚焦。")
    st.stop()

st.subheader("回答")
scope = result["scope"]
metrics = st.columns(5)
metrics[0].metric("相关文件", scope["matched_file_count"])
metrics[1].metric("相关符号", scope["matched_symbol_count"])
metrics[2].metric("引用", len(result["references"]))
metrics[3].metric("路由", len(result["related_routes"]))
metrics[4].metric("Diff", "已附加" if scope["diff_attached"] else "未附加")
st.write(result["answer"])

source_tab, route_tab, call_tab, lesson_tab, diff_tab = st.tabs(["源码范围", "相关路由", "调用链", "课程追问", "Diff 焦点"])

with source_tab:
    st.caption("相关文件")
    if result["related_files"]:
        for index, file in enumerate(result["related_files"]):
            with st.container(border=True):
                cols = st.columns([4, 1, 1, 1])
                cols[0].code(file["path"])
                cols[1].write(file["module_type"])
                cols[2].metric("重要度", file["importance_score"])
                if cols[3].button("源码", key=f"context-file-{index}"):
                    _open_source(file["path"])
                st.caption(file["reason"])
    else:
        st.info("没有命中具体文件。")

    st.caption("引用位置")
    for index, reference in enumerate(result["references"]):
        cols = st.columns([4, 1, 3, 1])
        cols[0].code(f"{reference['file']}:{reference['line']}")
        cols[1].write(reference["kind"])
        cols[2].write(reference["name"])
        if cols[3].button("查看", key=f"context-reference-{index}"):
            _open_source(reference["file"], reference["line"])

    st.caption("源码检查点")
    for index, checkpoint in enumerate(result["source_checkpoints"]):
        with st.container(border=True):
            cols = st.columns([4, 5, 1])
            cols[0].code(f"{checkpoint['file']}:{checkpoint['line']}")
            cols[1].write(checkpoint["checkpoint"])
            if cols[2].button("源码", key=f"context-checkpoint-{index}"):
                _open_source(checkpoint["file"], checkpoint["line"])

with route_tab:
    if result["related_routes"]:
        for index, route in enumerate(result["related_routes"]):
            cols = st.columns([2, 3, 4, 1])
            cols[0].write(f"{route['method']} {route['path']}")
            cols[1].write(route["handler"])
            cols[2].code(f"{route['file']}:{route['line']}")
            if cols[3].button("源码", key=f"context-route-{index}"):
                _open_source(route["file"], route["line"])
    else:
        st.info("当前追问没有命中 API 路由。")

with call_tab:
    if result["related_call_edges"]:
        st.dataframe(
            [
                {
                    "来源": f"{edge['source_file']}:{edge['call_line']}",
                    "调用方": edge["source_symbol"],
                    "目标": edge["target_symbol"],
                    "表达式": edge["call_expression"],
                    "置信度": edge["confidence"],
                }
                for edge in result["related_call_edges"]
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("当前追问没有命中函数级调用边。")

with lesson_tab:
    st.caption("相关课程")
    if result["related_lessons"]:
        for lesson in result["related_lessons"]:
            with st.container(border=True):
                cols = st.columns([4, 2, 1])
                cols[0].markdown(f"**{lesson['order_index']}. {lesson['title']}**")
                cols[1].write("；".join(lesson["matched_files"]) or lesson["reason"])
                if cols[2].button("复习", key=f"context-lesson-{lesson['lesson_id']}"):
                    st.session_state["lesson_id"] = lesson["lesson_id"]
                    st.switch_page("pages/4_Lesson_Quiz.py")
    else:
        st.info("当前追问没有命中学习路线课程。")

    st.caption("继续追问")
    for follow_up in result["follow_up_questions"]:
        st.write(f"- {follow_up}")

with diff_tab:
    diff_focus = result.get("diff_focus")
    if diff_focus:
        cols = st.columns(4)
        cols[0].metric("风险", _risk_label(diff_focus["risk_level"]))
        cols[1].metric("变更文件", len(diff_focus["changed_files"]))
        cols[2].metric("受影响文件", len(diff_focus["impacted_files"]))
        cols[3].metric("相关课程", diff_focus["related_lesson_count"])
        st.caption("变更文件")
        for path in diff_focus["changed_files"]:
            st.write(f"- {path}")
        st.caption("受影响文件")
        for path in diff_focus["impacted_files"]:
            st.write(f"- {path}")
        st.caption("建议")
        for item in diff_focus["recommendations"]:
            st.write(f"- {item}")
    else:
        st.info("本次追问未附加 diff。")
