# RepoTutor

RepoTutor 是一个面向 Python/FastAPI 项目的交互式 AI 代码导师。它会安全解压用户上传的 ZIP 仓库，通过 AST 静态分析建立项目事实库，然后生成架构图、学习路线、课程、测验和掌握度反馈。

## V1 已实现闭环

- ZIP 安全上传与隔离解压，默认不执行用户代码。
- 支持输入公开 GitHub 仓库 URL 导入，下载后继续复用 ZIP 安全解压和静态分析流程。
- 首页支持一键加载内置 FastAPI Shop Demo，快速进入完整演示状态。
- 首页会显示当前项目总览评分、下一步动作和仪表盘、学习路线、演示讲稿、报告导出入口。
- Python AST 分析文件、类、函数、导入关系、FastAPI 路由、SQLAlchemy 模型和 Pydantic Schema。
- 函数级调用关系解析，可生成从路由处理函数到 Service/Repository 的真实调用链。
- 可解释文件重要度评分与文件级依赖图。
- 提供结构化依赖图数据 API，前端可按模块类型、重要度、核心文件和关键词筛选节点与依赖边。
- 支持粘贴 git diff 做静态影响分析，定位受影响文件、相关路由和需复习课程。
- V2 增加 PR 讲解包，根据 diff 影响分析生成评审清单、测试计划、学习影响和面试复盘说法，并支持 Markdown 导出。
- V2 增量学习建议会把 diff 转成复习课程、源码检查点、练习任务和追问清单，并支持 Markdown 导出。
- Mermaid / PlantUML 架构图源码生成：分层架构、组件图、类图、ER 图、时序图、部署图、依赖图。
- 根据用户画像生成 5 到 10 节学习路线。
- 学习画像支持多目标选择，并兼容旧版单目标 `learning_goal` 数据。
- 生成引用真实文件、函数、类和行号的课程。
- 对课程输出做事实校验，拦截不存在的文件引用和越界行号。
- 课程生成支持可选 LLM 增强，Prompt 会注入受控源码片段，模型输出校验失败时自动回退到确定性课程。
- 项目问答支持可选 LLM 增强，回答必须保留事实依据、推断边界和真实源码引用。
- 记录 LLM 调用审计：Prompt、响应、状态、耗时和失败原因，方便排查幻觉与回退。
- 安全源码浏览：只允许查看静态分析确认过的项目文件，支持从课程跳转后返回学习上下文。
- 后端健康检查与能力清单，便于本地调试和部署探活。
- 生成测验、评分并更新课程状态、学习进度和知识点掌握度。
- 低分测验会生成补充讲解、源码复习步骤和二次测验，补齐动态补课闭环。
- 复习中心汇总测验历史、缺失点、误区、待完成动手任务、待掌握面试题，并可直接标记面试题掌握状态。
- 面试准备模块生成项目介绍、架构讲述、高频问答、风险提示和源码证据，支持记录高频问答掌握状态，面试准备度会同步进入 Markdown 导出。
- 生成 Markdown 学习报告，汇总项目事实、学习路线、课程进度、动手任务进度、架构图清单和演示讲稿。
- 单节课程支持导出 Markdown，包含目标、源码位置、调用链、讲解、动手任务、易错点和测验题。
- 单节课程自动生成知识卡片，用于围绕目标、源码锚点、调用链和测验关键词复习。
- 单节课程生成动手任务，把源码定位、调用链复述和改动影响演练转成检查清单。
- 动手任务支持完成状态记录，并可从目标文件和源码锚点一键跳转到源码浏览页。
- 学习进度页汇总项目级动手任务完成率、待完成任务和下一组练习入口。
- 项目仪表盘汇总分析、学习、练习、面试、演示和工程改进六个维度评分。
- 演示准备页汇总分析、架构图、学习路线、进度、练习、面试和报告导出闭环。
- 演示讲稿页把项目事实、学习闭环、演示准备度和后续优化计划整理成可复述的展示顺序。
- 项目改进建议页基于静态分析、学习进度、动手练习和测验记录生成 V1.2 优化任务，并提供可直接复述的面试说法。
- 项目改进建议会进入学习报告和面试材料导出，形成 V1.3 面试包装素材。
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

后端启动后可以做 HTTP 烟雾验证：

```bash
python3 scripts/smoke_http.py
```

如果要走一遍 demo 项目的进程内端到端闭环：

```bash
python3 scripts/e2e_demo_inprocess.py
```

`scripts/verify_offline.py` 会覆盖静态分析、架构图、学习路线、测验、补充讲解、演示准备、项目仪表盘、改进建议和演示讲稿导出。

如果要验证已启动后端的真实 HTTP 闭环：

```bash
python3 scripts/e2e_demo_http.py
```

## 离线验证

如果当前环境无法安装第三方依赖，可以先运行核心闭环验证：

```bash
python3 scripts/verify_offline.py
```

该脚本会验证 ZIP 安全、AST 分析、架构图、学习路线、项目问答、测验评分等不依赖 Web 框架的能力。

Agent 输出质量评测：

```bash
python3 scripts/evaluate_agents.py
```

该脚本会检查课程事实引用、源码上下文检索、项目问答引用、测验评分和 LangGraph 工作流轨迹，并把报告写入 `artifacts/reports/agent_eval.json`。

## Docker Compose

```bash
docker compose up --build
```

服务：

- FastAPI: `http://localhost:8000`
- Streamlit: `http://localhost:8501`

Docker Compose 会用 `/api/health` 检查后端健康状态，前端会等待后端 healthy 后再启动。

## CI 质量门槛

GitHub Actions 会在 `main` 分支推送和 Pull Request 时运行：

- `python -m pytest backend`
- `python scripts/verify_offline.py`
- `python scripts/evaluate_agents.py`
- `python scripts/e2e_demo_inprocess.py`

## 版本文档

- [V1.0.0 发布说明](docs/v1_release_notes.md)
- [后续路线图](docs/roadmap.md)

## 演示流程

1. 在 Streamlit 首页点击加载示例项目，或将 `demo_repositories/fastapi_shop` 压缩成 ZIP，也可以准备一个公开 GitHub 仓库地址。
2. 上传 ZIP、使用 GitHub URL 导入，或直接使用内置 FastAPI Shop Demo。
3. 选择 Python 水平、FastAPI 水平、学习目标和每天可用时间。
4. 点击开始分析。
5. 查看 Agent 运行记录，确认分析、架构图和学习路线节点已完成。
6. 进入项目概览、架构图、学习路线和课程测验页面，重点查看课程里的真实调用关系。
7. 配置模型接口后，可在 LLM 调用审计页面查看课程增强的提示词、响应和校验结果。
8. 进入源码浏览页面，按层级或关键词定位课程引用的文件。
9. 进入项目仪表盘和学习进度页面，查看总览评分、完成率、待复习课程和下一节推荐。
10. 如果测验低于 60 分，查看自动生成的补充讲解并完成二次测验。
11. 进入复习中心，查看测验历史、缺失点、误区、待练任务和待掌握面试题。
12. 进入面试准备页面，按项目介绍、架构讲述和高频问答准备项目讲解。
13. 进入报告导出页面，预览并下载项目学习报告或单节课程报告。
14. 进入演示准备页面，确认演示闭环是否已经达到可展示状态。
15. 进入项目改进建议页面，查看测试、接口契约、学习短板和面试包装的下一步任务。
16. 进入演示讲稿页面，按开场、架构、学习闭环、准备状态、后续优化和收尾顺序演练。
17. 下载项目报告或面试材料，把改进建议作为“后续优化计划”讲述素材。

## V2 变更理解流程

1. 在 Diff 影响分析页面粘贴 `git diff`，查看变更文件、受影响文件、相关路由和相关课程。
2. 在 PR 讲解包页面生成评审清单、测试计划、学习影响和面试复盘说法，并下载 Markdown。
3. 在增量学习页面把同一份 diff 转成复习课程、源码检查点、练习任务和追问清单。
4. 在报告导出页面的变更报告标签页，同时下载 PR 讲解包和增量学习建议。

## API 摘要

- `POST /api/projects/upload`
- `POST /api/projects/import-github`
- `POST /api/demo-projects/fastapi-shop`
- `GET /api/health`
- `GET /api/capabilities`
- `GET /api/projects`
- `GET /api/projects/{project_id}`
- `POST /api/projects/{project_id}/analyze`
- `GET /api/projects/{project_id}/analysis`
- `GET /api/projects/{project_id}/source-files`
- `GET /api/projects/{project_id}/source-files/{file_path}`
- `POST /api/projects/{project_id}/diagrams/generate`
- `GET /api/projects/{project_id}/diagrams`
- `GET /api/projects/{project_id}/diagrams/{diagram_id}/download`
- `GET /api/projects/{project_id}/dependency-graph`
- `POST /api/projects/{project_id}/diff-impact`
- `POST /api/projects/{project_id}/pr-review`
- `POST /api/projects/{project_id}/pr-review.md`
- `POST /api/projects/{project_id}/incremental-learning`
- `POST /api/projects/{project_id}/incremental-learning.md`
- `POST /api/projects/{project_id}/ask`
- `POST /api/projects/{project_id}/agent-runs/onboarding`
- `GET /api/projects/{project_id}/agent-runs`
- `GET /api/agent-runs/{run_id}`
- `GET /api/projects/{project_id}/llm-call-logs`
- `GET /api/llm-call-logs/{call_id}`
- `GET /api/settings/llm`
- `PUT /api/settings/llm`
- `POST /api/settings/llm/validate`
- `POST /api/projects/{project_id}/learning-plan`
- `GET /api/projects/{project_id}/learning-plan`
- `GET /api/projects/{project_id}/progress`
- `GET /api/projects/{project_id}/dashboard`
- `GET /api/projects/{project_id}/demo-readiness`
- `GET /api/projects/{project_id}/demo-script`
- `GET /api/projects/{project_id}/demo-script.md`
- `GET /api/projects/{project_id}/improvement-suggestions`
- `GET /api/projects/{project_id}/practice-progress`
- `GET /api/projects/{project_id}/quiz-results`
- `GET /api/projects/{project_id}/interview-kit`
- `GET /api/projects/{project_id}/interview-kit.md`
- `GET /api/projects/{project_id}/interview-readiness`
- `POST /api/projects/{project_id}/interview-questions/{question_id}/status`
- `GET /api/projects/{project_id}/reports/learning`
- `GET /api/projects/{project_id}/reports/learning.md`
- `GET /api/lessons/{lesson_id}`
- `GET /api/lessons/{lesson_id}/report.md`
- `GET /api/lessons/{lesson_id}/knowledge-cards`
- `GET /api/lessons/{lesson_id}/practice-tasks`
- `POST /api/lessons/{lesson_id}/practice-tasks/{task_id}/status`
- `POST /api/lessons/{lesson_id}/status`
- `POST /api/lessons/{lesson_id}/complete`
- `GET /api/lessons/{lesson_id}/quiz-results`
- `POST /api/quiz-results/{result_id}/remediation`
- `POST /api/lessons/{lesson_id}/quiz`
- `POST /api/quizzes/{quiz_id}/submit`
- `GET /api/projects/{project_id}/mastery`

## 安全边界

RepoTutor 只读取上传仓库的文本源码，不安装依赖、不导入上传项目、不运行测试、不执行任何用户代码。ZIP 解压会限制大小、文件数、单文件大小，并拦截路径穿越、软链接、`.env`、私钥、证书、`.git` 等敏感内容。GitHub URL 导入只支持公开仓库根地址，下载后仍然走同一套安全解压逻辑。
