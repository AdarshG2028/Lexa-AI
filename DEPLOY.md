# Deploying Lexa

Backend on Render (Docker), database on Neon (Postgres), frontend on Vercel.
All three have a free tier. Do the steps in this order: the frontend needs the
backend's URL, and the backend needs the frontend's.

Pronunciation analysis is switched off in this setup. The phoneme model needs
about 1.6 GB of RAM, more than a free instance has.

## 1. Database (Neon)

1. Create a project and copy the connection string. It looks like
   `postgresql://user:password@ep-xxx.neon.tech/neondb?sslmode=require`.
2. Paste it as-is into Render as `DATABASE_URL`. The app rewrites the scheme and
   the `sslmode` parameter for its async driver; nothing to edit by hand.

Tables are created on first start.

## 2. Backend (Render)

1. New → **Blueprint**, pick this repository. Render reads [`render.yaml`](render.yaml).
   To set it up by hand instead: a **Web Service**, runtime **Docker**,
   Dockerfile path `./backend/Dockerfile`, Docker context `./backend`,
   health check path `/health`.
2. Enter the values marked `sync: false`:

   | Variable | Value |
   |---|---|
   | `GROQ_API_KEY` | your Groq key |
   | `DATABASE_URL` | the Neon string from step 1 |
   | `CORS_ALLOWED_ORIGINS` | your Vercel URL, e.g. `https://lexa-ai.vercel.app` (fill in after step 3, then redeploy) |
   | `CORS_ALLOWED_ORIGIN_REGEX` | optional: `https://lexa-.*\.vercel\.app` to allow preview deployments |
   | `DEEPGRAM_API_KEY` | optional fallback voice |

3. When it is live, check `https://<your-service>.onrender.com/health`. It should
   return `"pronunciation":"off"`.

## 3. Frontend (Vercel)

1. Import the repository and set **Root Directory** to `frontend`.
2. Environment variables:

   | Variable | Value |
   |---|---|
   | `VITE_API_BASE_URL` | the Render URL, no trailing slash |
   | `NITRO_PRESET` | `vercel` |

   Leave `VITE_ENABLE_PRONUNCIATION` unset. Both `VITE_` variables are baked in at
   build time, so changing one means redeploying, not just editing it.
3. Deploy, then put the Vercel URL into Render's `CORS_ALLOWED_ORIGINS` and
   redeploy the backend.

## Things to know

- **The first request after a quiet period is slow** on Render's free tier while the
  instance wakes up. Open the app once before a demo.
- **Microphone access needs HTTPS**, which Vercel provides.
- **The API has no login.** Anyone with the URL can spend your Groq quota. Fine for
  a project demo; do not publish the URL widely.
- **Test on the production URL.** A preview deployment has a different origin and is
  blocked unless `CORS_ALLOWED_ORIGIN_REGEX` matches it.
- **Audio is not durable.** Replies live on the instance's disk and vanish on
  restart. That only matters for replaying old turns; sessions and reports are in
  Postgres.

## Turning pronunciation on

Needs a host with at least 2 GB of RAM: set `PRONUNCIATION_PROVIDER=wav2vec2`,
install with `uv sync --group pronunciation`, and set
`VITE_ENABLE_PRONUNCIATION=true` on the frontend.
