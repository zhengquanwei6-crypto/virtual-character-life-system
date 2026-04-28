# Changelog

## 0.4.0 - 2026-04-29

- 重做聊天页 UI/UX：移动端取消笨重顶部导航，改为紧凑角色头部、自然开场、快捷提示、固定安全区输入栏和图片预览。
- 优化消息体验：AI 思考中、图片生成中、失败重查、生成完成提示、消息入场动画与移动端无横向溢出。
- 重做管理员后台为配置工作台：中文导航、常用操作前置，角色、生图、模型、Workflow、测试中心分区更清晰。
- 将低频复杂项统一收纳到“高级设置”，包括 systemPrompt、安全提示词、LoRA、Workflow JSON、NodeMapping JSON 等。
- 新增管理员密码登录与 Bearer token 鉴权，公网部署后 `/api/admin/*` 不再裸露。
- 更新版本、PWA 缓存、APK 默认版本与部署环境示例到 `0.4.0`。

## 0.3.1 - 2026-04-29

- 优化移动端聊天页布局：顶部导航改为紧凑双 Tab，角色头部压缩为一行，长描述两行省略。
- 修复空状态与输入区在手机上横向裁切、发送按钮被挤出屏幕的问题。

## 0.3.0 - 2026-04-28

- 前端迁移到 Vite + React + TypeScript，统一用户聊天页与管理员后台入口。
- 重做 Web、PC、移动端响应式 UI，补充加载态、错误态、图片生成进度和移动端输入体验。
- 后台简化常用配置，将 Workflow、NodeMapping、LoRA、Seed、Prompt 细项等收纳到高级设置。
- 新增后台 LLM 配置 API，支持 OpenAI-compatible baseUrl、model、apiKey、timeout、模型拉取和测试。
- LLM 后台能力聚焦角色卡生成、角色定义辅助和 Workflow 分析辅助；不可用时保留 Mock fallback。
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
