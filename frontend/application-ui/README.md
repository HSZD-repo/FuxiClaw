# FuxiClaw Application UI

Standalone web UI for FuxiClaw, mirroring the design of the reference
`frontend/web/` client but running entirely on **mock data** — no backend is
required.

> This app lives under `frontend/application-ui/` and does **not** touch:
> - `src/openharness/` (Python core)
> - `ohmo/` (Python personal agent)
> - `frontend/terminal/` (existing React+Ink TUI)
> - `autopilot-dashboard/` (existing Vite dashboard)

## Quick start

```bash
cd frontend/application-ui
npm install
npm run dev
```

Open <http://localhost:5173> in a browser.

## What ships

- React 18 + Vite 6 + TypeScript (strict)
- Tailwind v4 with a semantic color token palette matching the reference design
- Radix UI primitives + shadcn-style wrappers (`components/ui/*`)
- react-markdown + remark-gfm + rehype-highlight for assistant Markdown
- CodeMirror 6 (Monokai) for the Artifact preview panel
- react-resizable-panels for the Chat / Artifact split
- **All backend calls are stubbed out.** WebSocket, session REST, file upload,
  settings PATCH — they all return mock fixtures from `src/lib/mockData.ts`.

## Turning it into a real client later

The WebSocket/REST contracts are preserved in `src/types/protocol.ts` and
`src/store/sessionReducer.ts`. To connect a real FuxiClaw backend:

1. Replace `src/hooks/useWebSocket.ts` with a real `new WebSocket(...)` impl
   (the reference version lives at `frontend/web/src/hooks/useWebSocket.ts`
   in the sibling project).
2. Replace `src/hooks/useSessionManager.ts` and `useFileUpload.ts` with real
   `fetch("/api/...")` calls.
3. Add a `server.proxy` block to `vite.config.ts` pointing `/ws` and `/api` at
   the FuxiClaw backend port (typically `http://127.0.0.1:8765`).

No component file needs to change — the mock layer is isolated to the hooks
and `lib/mockData.ts`.
