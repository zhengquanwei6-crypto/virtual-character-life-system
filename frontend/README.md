# Virtual Character Chat Frontend

Minimal user-side chat MVP for the FastAPI mock backend.

## Start

Keep the backend running first:

```bash
cd D:\llmai\backend
uvicorn app.main:app --reload
```

Then serve this static frontend:

```bash
cd D:\llmai\frontend
python -m http.server 5173
```

Open:

```txt
http://127.0.0.1:5173
```

Pages:

```txt
http://127.0.0.1:5173/index.html
http://127.0.0.1:5173/admin.html
```

This MVP implements the user chat page and a minimal mock admin console.
