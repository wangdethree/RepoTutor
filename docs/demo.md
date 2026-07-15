# RepoTutor V1 演示脚本

## 准备 Demo ZIP

```bash
cd demo_repositories
zip -r fastapi_shop.zip fastapi_shop
```

## 启动服务

```bash
docker compose up --build
```

## 演示路径

1. 打开 `http://localhost:8501`。
2. 上传 `demo_repositories/fastapi_shop.zip`。
3. 选择学习画像并点击开始分析。
4. 查看项目概览中的技术栈、核心模块、路由和模型。
5. 查看架构图页面中的分层架构、组件图、类图、ER 图和核心业务时序图。
6. 打开学习路线，进入第一节课程，确认课程中的调用关系能从路由追到 Service/Repository。
7. 回答测验并查看掌握度反馈。
