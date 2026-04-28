# Virtual Character Life System

前后端分离的虚拟角色聊天、生图与配置后台。当前版本以 FastAPI 后端、React 管理台/聊天页、Android WebView APK 为核心。

## 当前能力

- 用户聊天页：真实 LLM 或 Mock LLM 回复，按结构化决策触发异步 ImageTask。
- 生图链路：真实 ComfyUI 或 Mock 图片，生成结果保存为 GeneratedAsset。
- 管理后台：角色配置、生图预设、Workflow/NodeMapping 向导、模型连接、测试中心。
- 前端：Vite + React + TypeScript，响应式适配 Web、PC 浏览器和 Android WebView。
- 后端：FastAPI + SQLite + SQLModel，统一 `{ success, data, error, requestId }` 返回。

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

## LLM 与 ComfyUI

后台「模型连接」支持 OpenAI-compatible 接口：

```txt
baseUrl: https://your-llm.example/v1
model: your-model-id
apiKey: optional
timeout: 60
```

ChatGPT Plus/Codex 额度用于 Codex 开发工具，不作为本应用生产聊天 API 额度来源。生产调用请使用自定义 OpenAI-compatible 接口或官方 OpenAI API Key。

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

每个版本发布前请先备份：

```powershell
.\scripts\backup.ps1 -Version 0.3.0
```

## APK

Android WebView 工程位于 [mobile/android](./mobile/android)。推送 tag `v*` 会触发 GitHub Actions 构建 APK artifact。
