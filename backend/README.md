# Virtual Character Life System Backend

Mock backend for the MVP virtual character chat and image generation system.

## Start

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

API docs:

```txt
http://127.0.0.1:8000/docs
```

SQLite database:

```txt
backend/data/app.db
```

The backend supports both mock mode and external LLM / ComfyUI mode.

## External LLM / ComfyUI

Edit `.env`:

```txt
LLM_ENABLED=true
LLM_BASE_URL=https://1876c14363b64cf88315a21f7d6fc383--8000.ap-shanghai2.cloudstudio.club/v1
LLM_MODEL=
LLM_API_KEY=
LLM_TIMEOUT=60

COMFYUI_ENABLED=true
COMFYUI_BASE_URL=https://1876c14363b64cf88315a21f7d6fc383--8188.ap-shanghai2.cloudstudio.club
COMFYUI_TIMEOUT=300
```

When `LLM_MODEL` is empty, the backend uses the first model returned by `/v1/models`.
Set `LLM_ENABLED=false` or `COMFYUI_ENABLED=false` to return to mock mode.

Health checks:

```bash
curl http://127.0.0.1:8000/api/admin/system/llm-health
curl http://127.0.0.1:8000/api/admin/system/comfyui-health
```

## Quick test flow

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/api/user/characters/default
curl -X POST http://127.0.0.1:8000/api/user/chat-sessions -H "Content-Type: application/json" -d "{}"
```

Use the returned `sessionId`:

```bash
curl -X POST http://127.0.0.1:8000/api/user/chat-sessions/{sessionId}/messages -H "Content-Type: application/json" -d "{\"content\":\"please generate a photo\"}"
curl http://127.0.0.1:8000/api/user/image-tasks/{taskId}
```
