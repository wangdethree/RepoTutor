from __future__ import annotations

import os

import requests
import streamlit as st


API_URL = os.getenv("REPO_TUTOR_API_URL", "http://localhost:8000")


def _status_label(status: str) -> str:
    return {
        "NOT_STARTED": "未开始",
        "IN_PROGRESS": "学习中",
        "NEEDS_REVIEW": "需复习",
        "COMPLETED": "已完成",
    }.get(status, status)


def _open_source(file_path: str, line: int | None = None) -> None:
    st.session_state["source_file_path"] = file_path
    if line is None:
        st.session_state.pop("source_line", None)
    else:
        st.session_state["source_line"] = line
    st.switch_page("pages/9_Source_Browser.py")


def _render_remediation(remediation: dict, key_prefix: str) -> None:
    st.divider()
    st.header("补充讲解")
    st.warning(f"{remediation['title']}，触发分数：{remediation['trigger_score']}")

    st.subheader("薄弱点")
    for point in remediation["focus_points"]:
        st.write(f"- {point}")

    st.subheader("补充说明")
    for item in remediation["explanation"]:
        st.write(f"- {item}")

    st.subheader("复习步骤")
    for item in remediation["practice_steps"]:
        st.write(f"- {item}")

    st.subheader("补充源码证据")
    for index, location in enumerate(remediation["code_locations"]):
        cols = st.columns([3, 1, 2, 1])
        cols[0].code(f"{location['file']}:{location['line']}")
        cols[1].write(location["kind"])
        cols[2].write(location["name"])
        if cols[3].button("查看源码", key=f"{key_prefix}-remedial-source-{index}"):
            st.session_state["source_file_path"] = location["file"]
            st.session_state["source_line"] = location["line"]
            st.switch_page("pages/9_Source_Browser.py")

    if remediation.get("call_chains"):
        st.subheader("重新梳理调用链")
        for chain in remediation["call_chains"]:
            st.write(" -> ".join(step["symbol"] for step in chain["steps"]))

    st.subheader("二次测验")
    retry_quiz = remediation["retry_quiz"]
    retry_answers: dict[str, str] = {}
    for question in retry_quiz["questions"]:
        st.markdown(f"**{question['type']}**")
        retry_answers[question["id"]] = st.text_area(
            question["prompt"],
            key=f"{key_prefix}-{retry_quiz['id']}-{question['id']}",
        )
    if st.button("提交二次测验", type="primary", key=f"{key_prefix}-submit-retry"):
        retry_response = requests.post(
            f"{API_URL}/api/quizzes/{retry_quiz['id']}/submit",
            json=retry_answers,
            timeout=60,
        )
        retry_response.raise_for_status()
        retry_result = retry_response.json()
        st.metric("二次测验得分", retry_result["score"])
        st.write(retry_result["feedback"])
        if retry_result["score"] >= 80:
            st.success("二次测验已通过，本节会进入完成状态。")
        else:
            st.info("继续对照补充讲解和源码证据复习后再测一次。")


st.set_page_config(page_title="课程与测验", page_icon="RT", layout="wide")
st.title("课程与测验")

project_id = st.session_state.get("project_id")
lesson_id = st.session_state.get("lesson_id")
if not project_id:
    st.info("请先在首页上传或选择项目。")
    st.stop()

plan = requests.get(f"{API_URL}/api/projects/{project_id}/learning-plan", timeout=60).json()
lesson_options = {lesson["title"]: lesson["id"] for lesson in plan["lessons"]}
selected_title = st.selectbox(
    "选择课程",
    list(lesson_options.keys()),
    index=list(lesson_options.values()).index(lesson_id) if lesson_id in lesson_options.values() else 0,
)
lesson_id = lesson_options[selected_title]
st.session_state["lesson_id"] = lesson_id
remediation_key = f"remediation_{lesson_id}"

lesson = requests.post(f"{API_URL}/api/lessons/{lesson_id}/generate", timeout=60).json()
if lesson.get("status") == "NOT_STARTED":
    status_response = requests.post(f"{API_URL}/api/lessons/{lesson_id}/status", json={"status": "IN_PROGRESS"}, timeout=20)
    if status_response.status_code == 200:
        lesson = status_response.json()

st.header(lesson["title"])
status_cols = st.columns(4)
status_cols[0].metric("课程状态", _status_label(lesson.get("status", "NOT_STARTED")))
status_cols[1].metric("最近得分", lesson.get("last_score", "-"))
status_cols[2].metric("掌握度", lesson.get("mastery_level", "-") or "-")
report_response = requests.get(f"{API_URL}/api/lessons/{lesson_id}/report.md", timeout=30)
if report_response.status_code == 200:
    status_cols[3].download_button(
        "下载课程",
        data=report_response.text,
        file_name=f"{lesson_id}-lesson-report.md",
        mime="text/markdown",
    )
else:
    status_cols[3].button("下载课程", disabled=True)

if st.button("标记完成"):
    complete_response = requests.post(f"{API_URL}/api/lessons/{lesson_id}/complete", timeout=20)
    complete_response.raise_for_status()
    st.success("课程已标记完成")
    st.rerun()

st.subheader("为什么要学")
st.write(lesson["why"])
st.subheader("学习目标")
st.write("；".join(lesson["objectives"]))
st.subheader("核心代码位置")
for index, location in enumerate(lesson["core_code_locations"]):
    cols = st.columns([3, 1, 2, 1])
    cols[0].code(f"{location['file']}:{location['line']}")
    cols[1].write(location["kind"])
    cols[2].write(location["name"])
    if cols[3].button("查看源码", key=f"lesson-source-{index}"):
        st.session_state["source_file_path"] = location["file"]
        st.session_state["source_line"] = location["line"]
        st.switch_page("pages/9_Source_Browser.py")
if lesson.get("call_chains"):
    st.subheader("调用关系")
    for chain in lesson["call_chains"]:
        with st.container(border=True):
            st.markdown(f"**{chain['title']}**")
            st.write(" -> ".join(step["symbol"] for step in chain["steps"]))
            for edge_index, edge in enumerate(chain["edges"]):
                cols = st.columns([3, 4, 1])
                cols[0].code(f"{edge['file']}:{edge['line']}")
                cols[1].write(edge["expression"])
                if cols[2].button("查看源码", key=f"call-chain-{chain['id']}-{edge_index}"):
                    st.session_state["source_file_path"] = edge["file"]
                    st.session_state["source_line"] = edge["line"]
                    st.switch_page("pages/9_Source_Browser.py")
st.subheader("关键讲解")
for point in lesson["explanation"]:
    st.write(f"- {point}")
st.subheader("设计原因")
st.write(lesson["design_reason"])
st.subheader("容易出错的地方")
for pitfall in lesson["pitfalls"]:
    st.write(f"- {pitfall}")
st.subheader("本节总结")
st.write(lesson["summary"])

cards_response = requests.get(f"{API_URL}/api/lessons/{lesson_id}/knowledge-cards", timeout=30)
if cards_response.status_code == 200:
    cards_payload = cards_response.json()
    st.subheader("知识卡片")
    st.caption(f"共 {cards_payload['card_count']} 张，建议先遮住答案口头复述。")
    for card in cards_payload["cards"]:
        with st.expander(f"{card['category']} · {card['front']}"):
            st.write(card["back"])
            st.caption(card["review_prompt"])
            if card.get("references"):
                st.write("源码引用")
                for ref_index, reference in enumerate(card["references"][:3]):
                    cols = st.columns([3, 1, 2, 1])
                    cols[0].code(f"{reference['file']}:{reference['line']}")
                    cols[1].write(reference.get("kind", "source"))
                    cols[2].write(reference.get("name", "源码位置"))
                    if cols[3].button("查看", key=f"card-ref-{card['id']}-{ref_index}"):
                        st.session_state["source_file_path"] = reference["file"]
                        st.session_state["source_line"] = reference["line"]
                        st.switch_page("pages/9_Source_Browser.py")

tasks_response = requests.get(f"{API_URL}/api/lessons/{lesson_id}/practice-tasks", timeout=30)
if tasks_response.status_code == 200:
    tasks_payload = tasks_response.json()
    st.subheader("动手任务")
    task_cols = st.columns(3)
    task_cols[0].metric("任务数", tasks_payload["task_count"])
    task_cols[1].metric("已完成", tasks_payload["completed_task_count"])
    task_cols[2].metric("完成率", f"{tasks_payload['completion_rate']}%")
    st.caption("建议按顺序完成，每个任务完成后手动标记。")
    for task in tasks_payload["tasks"]:
        with st.container(border=True):
            cols = st.columns([4, 1])
            title_prefix = "[已完成] " if task.get("completed") else ""
            cols[0].markdown(f"**{title_prefix}{task['title']}**")
            cols[1].metric("预计", f"{task['estimated_minutes']} 分钟")
            st.write(task["objective"])
            if task.get("target_files"):
                st.write("目标文件")
                for file_index, file_path in enumerate(task["target_files"][:5]):
                    file_cols = st.columns([4, 1])
                    file_cols[0].code(file_path)
                    if file_cols[1].button("打开", key=f"practice-target-{task['id']}-{file_index}"):
                        _open_source(file_path)
            if task.get("references"):
                st.write("源码锚点")
                for ref_index, reference in enumerate(task["references"][:5]):
                    cols = st.columns([3, 1, 2, 1])
                    cols[0].code(f"{reference['file']}:{reference['line']}")
                    cols[1].write(reference.get("kind", "source"))
                    cols[2].write(reference.get("name", "源码位置"))
                    if cols[3].button("查看", key=f"practice-ref-{task['id']}-{ref_index}"):
                        _open_source(reference["file"], reference["line"])
            st.write("步骤")
            for step in task["steps"]:
                st.write(f"- {step}")
            st.write("验收检查")
            for check in task["acceptance_checks"]:
                st.write(f"- {check}")
            if task.get("expected_path"):
                st.code(task["expected_path"])
            if task.get("keyword_hint"):
                st.caption("关键词提示：" + "；".join(task["keyword_hint"]))
            if task.get("risk_notes"):
                st.warning("；".join(task["risk_notes"]))
            next_completed = not task.get("completed", False)
            action_label = "取消完成" if task.get("completed") else "标记完成"
            if st.button(action_label, key=f"practice-task-status-{task['id']}"):
                status_response = requests.post(
                    f"{API_URL}/api/lessons/{lesson_id}/practice-tasks/{task['id']}/status",
                    json={"completed": next_completed},
                    timeout=30,
                )
                status_response.raise_for_status()
                st.rerun()

st.divider()
st.header("测验")
quiz = requests.post(f"{API_URL}/api/lessons/{lesson_id}/quiz", timeout=60).json()
answers: dict[str, str] = {}
for question in quiz["questions"]:
    st.markdown(f"**{question['type']}**")
    answers[question["id"]] = st.text_area(question["prompt"], key=question["id"])

if st.button("提交测验", type="primary"):
    result = requests.post(f"{API_URL}/api/quizzes/{quiz['id']}/submit", json=answers, timeout=60).json()
    st.metric("得分", result["score"])
    st.write(result["feedback"])
    st.write("推荐动作：" + result["recommended_action"])
    if result["missing_points"]:
        st.warning("缺失点：" + "；".join(result["missing_points"]))
    if result["score"] >= 80:
        st.success("本节已自动标记完成。")
    elif result["score"] >= 60:
        st.info("本节保持学习中，建议补齐缺失点后再测一次。")
    else:
        st.warning("本节已标记为需复习。")
        remediation_response = requests.post(f"{API_URL}/api/quiz-results/{result['id']}/remediation", timeout=60)
        remediation_response.raise_for_status()
        st.session_state[remediation_key] = remediation_response.json()

if st.session_state.get(remediation_key):
    _render_remediation(st.session_state[remediation_key], remediation_key)
