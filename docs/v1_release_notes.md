# RepoTutor V1.0.0 发布说明

发布日期：2026-07-15

## 发布结论

RepoTutor V1 已完成项目计划书中的主闭环，可以作为可演示、可验收版本交付。

V1 的边界是：面向 Python/FastAPI 仓库，通过安全上传、静态分析、架构图、学习路线、
课程、测验、掌握度和动态补课，帮助用户系统理解一个陌生项目。

## 核心闭环

```text
上传 FastAPI 项目 ZIP
  -> 安全检查与解压
  -> 扫描项目文件
  -> AST 分析代码结构
  -> 识别入口、路由、服务、仓储、模型和配置
  -> 构建项目依赖图与真实调用链
  -> 生成专业项目架构图
  -> 读取用户学习画像
  -> 生成个性化学习路线
  -> 生成课程和测验
  -> 分析用户回答
  -> 更新知识掌握度
  -> 推荐下一节或生成补充讲解与二次测验
```

## 已交付能力

- ZIP 安全上传、敏感文件过滤和隔离解压。
- Python AST 静态分析，提取文件、类、函数、导入、FastAPI 路由、SQLAlchemy 模型和
  Pydantic Schema。
- 函数级调用关系解析，从路由处理函数追踪到 Service 和 Repository。
- 文件重要度评分和文件级依赖图。
- 架构图生成：系统分层图、组件图、类图、ER 图、核心业务时序图、部署图、
  文件依赖图。
- 用户画像配置：Python 水平、FastAPI 水平、学习目标、每日学习时间。
- 个性化学习路线，生成 5 到 10 节课程。
- 单节课程生成，课程内容绑定真实文件、函数、类和行号。
- 课程输出事实校验，拦截不存在的源码引用。
- 项目问答，保留事实依据、推断边界和真实源码引用。
- 课程测验、评分、掌握度更新和学习进度追踪。
- 低分补充讲解、源码复习步骤和二次测验。
- 复习中心、学习报告、面试准备模块。
- LangGraph 导入工作流和 Agent 运行轨迹。
- LLM 可选增强、OpenAI 兼容接口配置、调用审计和确定性回退。
- FastAPI 后端、Streamlit 前端、SQLite 持久化、Docker Compose 和 GitHub Actions CI。

## 验收命令

```bash
python -m pytest backend
python3 scripts/verify_offline.py
python scripts/evaluate_agents.py
python scripts/e2e_demo_inprocess.py
```

V1 发布前最近一次验证结果：

- 后端测试：35 passed
- 离线验证：passed
- Agent 评测：9 passed
- 进程内端到端 Demo：passed

## 演示入口

- 本地前端：`http://localhost:8501`
- 本地后端：`http://localhost:8000`
- Demo 项目：`demo_repositories/fastapi_shop`
- 演示脚本：`docs/demo.md`

## V1 非目标

以下内容不属于 V1 交付范围，避免发布边界继续发散：

- 多语言项目分析。
- Django、Java/Spring 等框架支持。
- GitHub OAuth 或私有仓库导入。
- IDE 插件。
- 团队协作与多租户。
- 自动运行上传项目代码。
- 自动修改用户项目代码。
- 超大型仓库分析。
- 语音、视频课程或复杂权限系统。

## 已知限制

- V1 默认针对中小型 Python/FastAPI 项目。
- 调用链来自 AST 静态分析，无法覆盖所有运行时动态调用。
- LLM 增强是可选能力，默认离线规则保证可演示。
- 架构图以源码事实和保守推断为主，不追求企业级建模完整度。
- 课程评分采用关键词覆盖率，语义评分留给后续版本增强。
