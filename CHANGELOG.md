# Changelog

## 0.3.0 - 2026-04-28

- 前端迁移到 Vite + React + TypeScript，统一用户聊天页与管理员后台入口。
- 重做 Web、PC、移动端响应式 UI，修复中文乱码，补充加载态、错误态、图片生成进度和移动端输入体验。
- 后台简化常用配置，把 Workflow、NodeMapping、LoRA、Seed、Prompt 细项等收纳到高级设置。
- 新增后台 LLM 配置 API，支持 OpenAI-compatible baseUrl、model、apiKey、timeout、模型拉取和测试。
- LLM 后台能力聚焦角色卡生成、角色定义辅助和 Workflow 分析辅助；不可用时保留 Mock/启发式 fallback。
- 部署改为前端 Docker 构建产物服务，适配 React 生产构建。

## 0.2.1 - 2026-04-28

- VPS 部署端口改为 `8090`，避免覆盖服务器已有 80 端口服务。
- APK 默认 Web 地址同步为 `http://96.30.199.85:8090/index.html`。

## 0.2.0 - 2026-04-28

- 接入用户聊天页真实 LLM + ComfyUI 图文链路。
- 增加生产部署配置、版本接口、数据备份脚本。
- 增加 PWA 与 Android WebView APK 构建工程。
- 优化用户端移动端 UI 与状态展示。

## 0.1.0 - 2026-04-28

- FastAPI + SQLModel MVP。
- 静态用户聊天页与管理员后台。
- Mock API、真实 LLM/ComfyUI 配置与健康检查。
