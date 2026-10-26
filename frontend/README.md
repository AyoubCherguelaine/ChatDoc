# DOCTool frontend

Next.js App Router, React, TypeScript, Tailwind, and Lucide. The interface uses an ink, teal, and sage palette across the landing page, authentication, document library, conversations, AI studio, and chat.

```bash
npm ci
npm run dev
```

Open http://localhost:3000. Start the FastAPI backend on port 8000 and PostgreSQL using the root README instructions. `NEXT_PUBLIC_API_URL` defaults to `http://localhost:8000/api`; set it in `.env.local` when using a different API address.

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

The Dockerfile creates a production standalone server running as an unprivileged user. Supply `NEXT_PUBLIC_API_URL` as a Docker build argument to change the browser-facing API address. The root compose file uses localhost:8000 for local development.

See [the root README](../README.md#product-workspace-update) for file formats, upload limits, parser behavior, and backend tests.
