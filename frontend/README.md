# DOCTool frontend

Next.js App Router, React, TypeScript, Tailwind, and Lucide. The interface uses an ink, teal, and sage palette across the landing page, authentication, document library, conversations, AI studio, and chat.

```bash
npm ci
npm run dev
```

Open http://localhost:3000. Start the FastAPI backend on port 8000 and PostgreSQL using the root README instructions. `NEXT_PUBLIC_API_URL` defaults to `/api`, so browser requests use the frontend origin. Next.js forwards them to `BACKEND_URL` (default `http://127.0.0.1:8000`). Set these values in `.env.local` before building when using a different API address.

## Routes

| Route | Purpose |
| --- | --- |
| `/` | Public landing page |
| `/login` | Sign in; `?mode=signup` opens registration |
| `/drive` | Workspace overview and document library |
| `/drive?view=documents` | Library without overview sections |
| `/conversations` | Search saved chats |
| `/agents` | Choose a workflow and source document |
| `/chat/[sessionId]` | Chat, agent mode, model settings, source reader, and export |

The session provider protects workspace routes; the backend independently enforces ownership. AI studio workflows prepare an editable prompt. Chat settings use the server's enabled model list from `/api/capabilities`. Stop aborts the browser stream, while already-started server/provider work may continue. Markdown is rendered without raw HTML, including tables and code blocks.

## Validation and builds

```bash
npm run lint
npx tsc --noEmit
npm run build
```

The Dockerfile creates a production standalone server running as an unprivileged user. Docker builds use `/api` for the browser and `http://backend:8000` for the server proxy. Both are Docker build arguments (`NEXT_PUBLIC_API_URL` and `BACKEND_URL`); changing either requires rebuilding the frontend. This works on EC2 without embedding the server IP or exposing backend port 8000 to browsers.

From your EC2 project folder (for example, `doc tool`), apply the updated source and rebuild:

```bash
docker compose up -d --build frontend
```

For a deployment without Docker, use `NEXT_PUBLIC_API_URL=/api` and `BACKEND_URL=http://127.0.0.1:8000` in `frontend/.env.local`, then run `npm run build` and restart the frontend process. Existing `.env.local` files must have their old localhost API URL replaced before building.

See [the root README](../README.md#product-workspace-update) for file formats, upload limits, parser behavior, and backend tests.
