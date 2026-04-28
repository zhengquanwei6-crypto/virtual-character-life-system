# Virtual Character Life System

前后端分离的虚拟角色聊天、生图与配置后台。当前版本以 FastAPI、SQLite、React/Vite 和 Android WebView 为核心，支持 Mock fallback 与真实 LLM/ComfyUI 接入。

## 当前能力

- 用户聊天页：角色对话、结构化 LLM 决策、异步 ImageTask 轮询、生成图片展示与失败提示。
- 管理后台：密码登录、角色配置、生图预设、Workflow/NodeMapping 向导、用户聊天 LLM 配置、测试中心。
- v0.5.0 新增：后台 AI 助手、AI 任务草稿/应用、角色模板、ComfyUI 资源中心、类型化 Workflow 解析与 NodeMapping 校验。
- 后端统一返回 `{ success, data, error, requestId }`。

## 本地启动

后端：

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

前端：

```bash
cd frontend
npm install
npm run dev
```

访问：

```txt
http://127.0.0.1:5173/index.html
http://127.0.0.1:5173/admin.html
http://127.0.0.1:8000/docs
```

本地默认管理员密码来自 `ADMIN_PASSWORD`，未配置时为 `admin123456`。生产部署必须修改。

## v0.5.0 管理后台

- “AI 助手”：独立后台 AI 配置，可用于角色生成、角色/视觉提示词优化、生图预设建议和 Workflow 诊断。
- “资源中心”：读取 ComfyUI `/system_stats`、`/queue`、`/object_info`、`/models/*`、`/embeddings`，失败时显示缓存。
- “Workflow”：确定性解析节点、连接关系、输入类型、资源依赖，并生成可解释 NodeMapping 草稿。
- “生图”：checkpoint、sampler、scheduler 优先从资源缓存下拉选择，避免手动输入错误。

## 部署

VPS Docker Compose：

```bash
cd /opt/virtual-character-life-system/current
docker compose -f deploy/vps/docker-compose.yml up -d --build
```

默认 Web 端口：

```txt
http://96.30.199.85:8090/index.html
http://96.30.199.85:8090/admin.html
```

每个版本发布前先备份：

```bash
bash /opt/virtual-character-life-system/current/deploy/vps/backup.sh v0.5.0-predeploy
```

## APK

Android WebView 工程位于 [mobile/android](./mobile/android)。推送 `v*` tag 会触发 GitHub Actions 构建 APK artifact。
