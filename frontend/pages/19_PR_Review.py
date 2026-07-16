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


def _check_status_label(value: str) -> str:
    return {
        "PASS": "通过",
        "NEEDS_CHECK": "需检查",
    }.get(value, value)


st.set_page_config(page_title="PR 讲解包", page_icon="RT", layout="wide")
st.title("PR 讲解包")

project_id = st.session_state.get("project_id")
if not project_id:
    st.info("请先在首页上传或选择项目。")
    st.stop()

sample_diff = """diff --git a/app/api/orders.py b/app/api/orders.py
--- a/app/api/orders.py
+++ b/app/api/orders.py
@@ -1,2 +1,3 @@
+include_coupon = True
"""

diff_text = st.text_area("粘贴 git diff", value="", placeholder=sample_diff, height=240)

if st.button("生成 PR 讲解包", type="primary", disabled=not diff_text.strip()):
    try:
        response = requests.post(
            f"{API_URL}/api/projects/{project_id}/pr-review",
            json={"diff": diff_text},
            timeout=60,
        )
        response.raise_for_status()
        st.session_state["pr_review_result"] = response.json()
        markdown_response = requests.post(
            f"{API_URL}/api/projects/{project_id}/pr-review.md",
            json={"diff": diff_text},
            timeout=60,
        )
        if markdown_response.status_code == 200:
            st.session_state["pr_review_markdown"] = markdown_response.text
    except requests.RequestException as exc:
        st.error(f"生成 PR 讲解包失败：{exc}")
        st.stop()

review = st.session_state.get("pr_review_result")
if not review:
    st.info("粘贴一次 git diff 后生成 PR 讲解包。系统只解析文本，不执行代码。")
    st.stop()

st.subheader(review["title"])
metrics = st.columns(4)
metrics[0].metric("风险", _risk_label(review["risk_level"]))
metrics[1].metric("新增行", review["line_stats"]["additions"])
metrics[2].metric("删除行", review["line_stats"]["deletions"])
metrics[3].metric("变更行", review["line_stats"]["total_changed_lines"])

if st.session_state.get("pr_review_markdown"):
    st.download_button(
        "下载 PR 讲解 Markdown",
        data=st.session_state["pr_review_markdown"],
        file_name=f"{project_id}-pr-review.md",
        mime="text/markdown",
    )

st.write(review["change_summary"])
st.warning(review["merge_advice"])

summary_tab, checklist_tab, test_tab, learning_tab, interview_tab = st.tabs(
    ["影响面", "评审清单", "测试计划", "学习影响", "面试说法"]
)

with summary_tab:
    surface = review["affected_surface"]
    st.caption("变更文件")
    for file_path in surface["changed_files"] or ["暂无"]:
        st.write(f"- {file_path}")
    st.caption("受影响文件")
    for file_path in surface["impacted_files"] or ["暂无"]:
        st.write(f"- {file_path}")
    st.caption("相关路由")
    for route in surface["routes"] or ["暂无"]:
        st.write(f"- {route}")

with checklist_tab:
    for item in review["review_checklist"]:
        with st.container(border=True):
            cols = st.columns([1, 3, 5])
            cols[0].write(_check_status_label(item["status"]))
            cols[1].markdown(f"**{item['title']}**")
            cols[2].write(item["action"])

with test_tab:
    for item in review["test_plan"]:
        st.write(f"- {item}")

with learning_tab:
    if review["learning_impacts"]:
        for lesson in review["learning_impacts"]:
            with st.container(border=True):
                cols = st.columns([4, 2, 1])
                cols[0].markdown(f"**{lesson['order_index']}. {lesson['title']}**")
                cols[1].write("；".join(lesson["matched_files"]))
                if cols[2].button("复习", key=f"pr-review-lesson-{lesson['lesson_id']}"):
                    st.session_state["lesson_id"] = lesson["lesson_id"]
                    st.switch_page("pages/4_Lesson_Quiz.py")
                st.caption(lesson["action"])
    else:
        st.info("当前 diff 没有命中学习路线课程。")

with interview_tab:
    for item in review["interview_talking_points"]:
        st.write(f"- {item}")
