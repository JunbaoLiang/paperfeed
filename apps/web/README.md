# PaperFeed · Web (apps/web)

Next.js (App Router) frontend for the single-user arXiv recommendation system.
Pages: 信息流 `/`, 收藏 `/saved`, 统计 `/stats`, 冷启动引导 `/onboarding`.

## How it talks to the backend

The browser never calls the FastAPI service directly and never sees the API
token. All requests go through Next.js Route Handlers which proxy to the
backend and inject `Authorization: Bearer $PAPERFEED_API_TOKEN` server-side:

| Route handler        | Backend endpoint            |
| -------------------- | --------------------------- |
| `GET /api/feed`      | `GET {API}/feed?n=20`       |
| `POST /api/feedback` | `POST {API}/feedback`       |
| `GET /api/saved`     | `GET {API}/saved`           |
| `GET /api/stats`     | `GET {API}/stats`           |
| `POST /api/seed-profile` | `POST {API}/admin/seed-profile` |

`/api/feedback` accepts a single event object or a JSON array, and parses the
body as JSON even when `navigator.sendBeacon` delivers it as `text/plain`.

Event tracking (spec §10) lives in `lib/tracker.ts` + `lib/useImpressionTracking.ts`:
`visible` (≥50% visible for ≥1s), `dwell` (abstract expanded → collapsed/off-screen,
max once per impression), `click_abstract` / `click_pdf` / `save` / `dismiss`.
Events buffer in memory and flush as a JSON array every 5s, immediately for
save/dismiss, and via `sendBeacon` on `visibilitychange→hidden` / `pagehide`.

## Local development

```bash
cp .env.local.example .env.local   # then edit values
npm install
npm run dev                        # http://localhost:3000
```

`PAPERFEED_API_URL` must point at a running FastAPI service (`services/api`,
default `http://localhost:8000`) and `PAPERFEED_API_TOKEN` must match the
backend's `API_TOKEN` — otherwise every page shows its error/empty state.

```bash
npm run build   # production build (must pass before deploying)
npm run lint
```

## Deploying to Vercel

1. Import the repo in Vercel and set **Root Directory** to `apps/web`.
2. In Project → Settings → Environment Variables add:
   - `PAPERFEED_API_URL` — public URL of the FastAPI service
     (e.g. the Hugging Face Space URL)
   - `PAPERFEED_API_TOKEN` — same token the backend was deployed with
3. Deploy. No other configuration is required; the route handlers run as
   serverless functions and keep the token server-side.
