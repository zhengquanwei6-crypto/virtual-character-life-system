# Frontend

Vite + React + TypeScript frontend for the chat app and admin console.

## Development

```bash
npm install
npm run dev
```

Open:

```txt
http://127.0.0.1:5173/index.html
http://127.0.0.1:5173/admin.html
```

The dev server proxies `/api`, `/health`, and `/generated` to `http://127.0.0.1:8000`.

## Build

```bash
npm run build
```

Production output is written to `frontend/dist`.
