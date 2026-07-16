from __future__ import annotations

import os

import requests
import streamlit as st


API_URL = os.getenv("REPO_TUTOR_API_URL", "http://localhost:8000")


def _filter_nodes(nodes: list[dict], module_types: list[str], min_importance: int, core_only: bool, keyword: str) -> list[dict]:
    keyword = keyword.strip().lower()
    filtered = []
    for node in nodes:
        if module_types and node["module_type"] not in module_types:
            continue
        if node["importance_score"] < min_importance:
            continue
        if core_only and not node["is_core"]:
            continue
        if keyword and keyword not in node["id"].lower():
            continue
        filtered.append(node)
    return filtered


def _filter_edges(edges: list[dict], visible_node_ids: set[str]) -> list[dict]:
    return [edge for edge in edges if edge["source"] in visible_node_ids and edge["target"] in visible_node_ids]

st.set_page_config(page_title="架构图", page_icon="RT", layout="wide")
st.title("项目架构图")

project_id = st.session_state.get("project_id")
if not project_id:
    st.info("请先在首页上传或选择项目。")
    st.stop()

payload = requests.get(f"{API_URL}/api/projects/{project_id}/diagrams", timeout=60).json()
diagrams = payload.get("diagrams", [])
if not diagrams:
    if st.button("生成架构图"):
        requests.post(f"{API_URL}/api/projects/{project_id}/diagrams/generate", timeout=120).raise_for_status()
        st.rerun()
    st.stop()

titles = {diagram["title"]: diagram for diagram in diagrams}
selected_title = st.selectbox("图类型", list(titles.keys()))
diagram = titles[selected_title]

diagram_tab, dependency_tab = st.tabs(["图源码", "依赖图数据"])

with diagram_tab:
    st.caption(diagram["description"])
    if diagram["format"] == "mermaid":
        st.code(diagram["source"], language="mermaid")
    else:
        st.code(diagram["source"], language="plantuml")

    st.download_button(
        "下载源码",
        data=diagram["source"],
        file_name=f"{diagram['id']}.{diagram['format']}",
        mime="text/plain",
    )

with dependency_tab:
    graph_response = requests.get(f"{API_URL}/api/projects/{project_id}/dependency-graph", timeout=60)
    if graph_response.status_code >= 400:
        st.error(graph_response.text)
        st.stop()
    graph = graph_response.json()
    summary = graph["summary"]
    metric_cols = st.columns(4)
    metric_cols[0].metric("文件节点", summary["node_count"])
    metric_cols[1].metric("依赖边", summary["edge_count"])
    metric_cols[2].metric("核心文件", summary["core_node_count"])
    metric_cols[3].metric("最高重要度", summary["max_importance_score"])

    filter_cols = st.columns([2, 1, 1, 2])
    selected_modules = filter_cols[0].multiselect("模块类型", summary["module_types"], default=summary["module_types"])
    min_importance = filter_cols[1].slider("最低重要度", 0, max(summary["max_importance_score"], 1), 0)
    core_only = filter_cols[2].checkbox("只看核心")
    keyword = filter_cols[3].text_input("文件关键词")

    filtered_nodes = _filter_nodes(graph["nodes"], selected_modules, min_importance, core_only, keyword)
    visible_node_ids = {node["id"] for node in filtered_nodes}
    filtered_edges = _filter_edges(graph["edges"], visible_node_ids)

    st.subheader("节点")
    st.dataframe(
        [
            {
                "文件": node["id"],
                "模块": node["module_type"],
                "重要度": node["importance_score"],
                "被依赖": node["imported_by"],
                "依赖数": node["imports_count"],
                "核心": "是" if node["is_core"] else "",
            }
            for node in filtered_nodes
        ],
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("依赖边")
    st.dataframe(
        [
            {
                "来源": edge["source"],
                "目标": edge["target"],
                "类型": edge["edge_type"],
                "置信度": edge["confidence"],
                "证据": edge["evidence"],
            }
            for edge in filtered_edges
        ],
        use_container_width=True,
        hide_index=True,
    )
