# Virtual Character Life System

前后端分离的虚拟角色聊天与生图 MVP。

当前能力：

- 用户聊天页：真实 LLM 回复，按 LLM 决策触发真实 ComfyUI 生图。
- 管理员后台：角色配置、生图预设、WorkflowTemplate、NodeMapping、健康检查与测试模块。
- 后端：FastAPI + SQLite + SQLModel。
- 前端：无构建依赖的静态 HTML/CSS/JS。

## 目录

```txt
backend/   FastAPI 后端
frontend/  静态前端
```

## 后端启动

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

访问：

```txt
http://127.0.0.1:8000/docs
```

## 前端启动

```bash
cd frontend
python -m http.server 5173
```

访问：

```txt
http://127.0.0.1:5173/index.html
http://127.0.0.1:5173/admin.html
```

## 环境变量

复制示例文件：

```bash
cp backend/.env.example backend/.env
```

Mock 模式：

```txt
LLM_ENABLED=false
COMFYUI_ENABLED=false
```

真实外链模式需要配置：

```txt
LLM_ENABLED=true
LLM_BASE_URL=...
LLM_MODEL=
LLM_API_KEY=

COMFYUI_ENABLED=true
COMFYUI_BASE_URL=...
```

注意：`backend/.env`、SQLite 数据库、生成图片和日志不会提交到 Git。

