# RepoTutor

RepoTutor 是一个面向 Python/FastAPI 项目的交互式 AI 代码导师。它会安全解压用户上传的 ZIP 仓库，通过 AST 静态分析建立项目事实库，然后生成架构图、学习路线、课程、测验和掌握度反馈。

## V1 已实现闭环

- ZIP 安全上传与隔离解压，默认不执行用户代码。
- Python AST 分析文件、类、函数、导入关系、FastAPI 路由、SQLAlchemy 模型和 Pydantic Schema。
- 可解释文件重要度评分与文件级依赖图。
- Mermaid / PlantUML 架构图源码生成：分层架构、组件图、类图、ER 图、时序图、部署图、依赖图。
- 根据用户画像生成 5 到 10 节学习路线。
- 生成引用真实文件、函数、类和行号的课程。
- 对课程输出做事实校验，拦截不存在的文件引用和越界行号。
- 课程生成支持可选 LLM 增强，模型输出校验失败时自动回退到确定性课程。
- 生成测验、评分并更新知识点掌握度。
- LangGraph 项目导入工作流：分析、架构图、学习画像、学习路线节点化编排，并记录 Agent 运行轨迹。
- FastAPI 后端、Streamlit 前端、SQLite 持久化、Docker Compose 和 pytest 测试。
- OpenAI 兼容 LLM 客户端预留，V1 默认用确定性规则保证离线可演示。

## 本地运行

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
```

另开一个终端：

```bash
streamlit run frontend/Home.py
```

默认 API 地址是 `http://localhost:8000`，也可以通过 `REPO_TUTOR_API_URL` 覆盖。

## 离线验证

如果当前环境无法安装第三方依赖，可以先运行核心闭环验证：

```bash
python3 scripts/verify_offline.py
```

该脚本会验证 ZIP 安全、AST 分析、架构图、学习路线、项目问答、测验评分等不依赖 Web 框架的能力。

## Docker Compose

```bash
docker compose up --build
```

服务：

- FastAPI: `http://localhost:8000`
- Streamlit: `http://localhost:8501`

## 演示流程

1. 将 `demo_repositories/fastapi_shop` 压缩成 ZIP。
2. 在 Streamlit 首页上传 ZIP。
3. 选择 Python 水平、FastAPI 水平、学习目标和每天可用时间。
4. 点击开始分析。
5. 查看 Agent 运行记录，确认分析、架构图和学习路线节点已完成。
6. 进入项目概览、架构图、学习路线和课程测验页面。

## API 摘要

- `POST /api/projects/upload`
- `GET /api/projects`
- `GET /api/projects/{project_id}`
- `POST /api/projects/{project_id}/analyze`
- `GET /api/projects/{project_id}/analysis`
- `POST /api/projects/{project_id}/diagrams/generate`
- `GET /api/projects/{project_id}/diagrams`
- `GET /api/projects/{project_id}/diagrams/{diagram_id}/download`
- `POST /api/projects/{project_id}/ask`
- `POST /api/projects/{project_id}/agent-runs/onboarding`
- `GET /api/projects/{project_id}/agent-runs`
- `GET /api/agent-runs/{run_id}`
- `GET /api/settings/llm`
- `PUT /api/settings/llm`
- `POST /api/settings/llm/validate`
- `POST /api/projects/{project_id}/learning-plan`
- `GET /api/projects/{project_id}/learning-plan`
- `GET /api/lessons/{lesson_id}`
- `POST /api/lessons/{lesson_id}/quiz`
- `POST /api/quizzes/{quiz_id}/submit`
- `GET /api/projects/{project_id}/mastery`

## 安全边界

RepoTutor 只读取上传仓库的文本源码，不安装依赖、不导入上传项目、不运行测试、不执行任何用户代码。ZIP 解压会限制大小、文件数、单文件大小，并拦截路径穿越、软链接、`.env`、私钥、证书、`.git` 等敏感内容。
