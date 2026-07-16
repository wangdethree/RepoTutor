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


st.set_page_config(page_title="Diff 影响分析", page_icon="RT", layout="wide")
st.title("Diff 影响分析")

project_id = st.session_state.get("project_id")
if not project_id:
    st.info("请先在首页上传或选择项目。")
    st.stop()

sample_diff = """diff --git a/app/models/user.py b/app/models/user.py
--- a/app/models/user.py
+++ b/app/models/user.py
@@ -1,2 +1,3 @@
+email_verified = True
"""

diff_text = st.text_area("粘贴 git diff", value="", placeholder=sample_diff, height=240)

if st.button("分析影响范围", type="primary", disabled=not diff_text.strip()):
    try:
        response = requests.post(
            f"{API_URL}/api/projects/{project_id}/diff-impact",
            json={"diff": diff_text},
            timeout=60,
        )
        response.raise_for_status()
        st.session_state["diff_impact_result"] = response.json()
    except requests.RequestException as exc:
        st.error(f"影响分析失败：{exc}")
        st.stop()

result = st.session_state.get("diff_impact_result")
if not result:
    st.info("粘贴一次 git diff 后开始分析。系统只解析文本，不执行代码。")
    st.stop()

summary = result["summary"]
metrics = st.columns(5)
metrics[0].metric("变更文件", summary["changed_file_count"])
metrics[1].metric("已识别", summary["known_changed_file_count"])
metrics[2].metric("未知", summary["unknown_changed_file_count"])
metrics[3].metric("受影响文件", summary["impacted_file_count"])
metrics[4].metric("风险", _risk_label(summary["risk_level"]))

st.subheader("建议")
for item in result["recommendations"]:
    st.write(f"- {item}")

changed_tab, impacted_tab, route_tab, lesson_tab = st.tabs(["变更文件", "影响文件", "相关路由", "相关课程"])

with changed_tab:
    st.dataframe(
        [
            {
                "文件": item["path"],
                "已识别": "是" if item["known"] else "否",
                "模块": item["module_type"],
                "重要度": item["importance_score"],
                "被依赖": item["imported_by"],
            }
            for item in result["changed_files"]
        ],
        use_container_width=True,
        hide_index=True,
    )

with impacted_tab:
    st.dataframe(
        [
            {
                "文件": item["path"],
                "深度": item["depth"],
                "模块": item["module_type"],
                "重要度": item["importance_score"],
                "原因": item["reason"],
                "证据": item["evidence"],
            }
            for item in result["impacted_files"]
        ],
        use_container_width=True,
        hide_index=True,
    )
    if result["dependent_edges"]:
        st.caption("直接依赖边")
        st.dataframe(result["dependent_edges"], use_container_width=True, hide_index=True)

with route_tab:
    if result["related_routes"]:
        for index, route in enumerate(result["related_routes"]):
            cols = st.columns([2, 3, 4, 1])
            cols[0].write(f"{route['method']} {route['path']}")
            cols[1].write(route["handler"])
            cols[2].code(f"{route['file']}:{route['line']}")
            if cols[3].button("源码", key=f"diff-route-{index}"):
                st.session_state["source_file_path"] = route["file"]
                st.session_state["source_line"] = route["line"]
                st.switch_page("pages/9_Source_Browser.py")
    else:
        st.info("当前 diff 没有命中相关路由。")

with lesson_tab:
    if result["related_lessons"]:
        for lesson in result["related_lessons"]:
            with st.container(border=True):
                cols = st.columns([4, 2, 1])
                cols[0].markdown(f"**{lesson['order_index']}. {lesson['title']}**")
                cols[1].write("；".join(lesson["matched_files"]))
                if cols[2].button("复习", key=f"diff-lesson-{lesson['id']}"):
                    st.session_state["lesson_id"] = lesson["id"]
                    st.switch_page("pages/4_Lesson_Quiz.py")
    else:
        st.info("当前 diff 没有命中学习路线课程。")
