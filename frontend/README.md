# Lexa

An AI conversational assistant you practice speaking with. Have a real voice
conversation, and when you hang up Lexa turns the transcript into a report of
your grammar and pronunciation improvements. Speech-to-text and text-to-speech
drive the call; this repository is the frontend — the landing page, the
conversation page, and the insights report.

## Running it against the backend

This app is now wired to the real API in `G:\Codes\Voice AI` — no scripted
demo data remains. Both halves must be running.

**1. Backend** (from `G:\Codes\Voice AI`):

```
uv run uvicorn app.main:app --port 8001
```

**2. Frontend** (from here):

```
bun install
bun run dev
```

Vite prefers port 8080 and falls back to the next free one. The port it prints
must appear in the backend's `CORS_ALLOWED_ORIGINS`, or the browser will block
every request; 8080, 8081 and 5173 are allowed out of the box.

`.env` holds the one setting that matters:

```
VITE_API_BASE_URL=http://localhost:8001
```

**3. Use it.** Open `/conversation`, allow microphone access, tap the mic, speak,
tap again to send. The transcript and Lexa's spoken reply come back from the
backend. "End & review" closes the session and opens the report.

### What the report runs

Fluency, grammar and vocabulary run automatically when the report opens.
Pronunciation sits behind its own button: it loads a 316M-parameter phoneme
model into the API server, which takes 60-100 seconds on the first run and holds
roughly 1.6 GB for the life of that process. That cost is deliberately visible
rather than hidden inside the page load.

### Microphone access needs a secure origin

Browsers only expose `getUserMedia` on HTTPS or on `localhost`. Opening the dev
server by LAN IP will show the text box but no working microphone.

---
## Stack

- [TanStack Start](https://tanstack.com/start) (React 19, SSR) with TanStack Router and Query
- [Vite](https://vite.dev) + [Tailwind CSS v4](https://tailwindcss.com)
- [shadcn/ui](https://ui.shadcn.com) components on Radix primitives
- [Nitro](https://nitro.build) for the production server build

## Getting started

Requires [Bun](https://bun.sh).

```sh
bun install
bun run dev
```

The dev server runs on [http://localhost:8080](http://localhost:8080).

## Scripts

| Command            | Description                                     |
| ------------------ | ----------------------------------------------- |
| `bun run dev`      | Start the dev server with HMR                   |
| `bun run build`    | Production build into `.output/`                |
| `bun run preview`  | Serve the production build locally              |
| `bun run lint`     | Lint with ESLint                                |
| `bun run format`   | Format with Prettier                            |

## Project layout

```
src/
  routes/       file-based routes (__root, index, conversation, insights)
  components/   shadcn/ui components
  lib/          error capture + SSR error page, utilities
  styles.css    design tokens and Tailwind theme
  server.ts     SSR entry with error handling
```

`bun run build` targets Cloudflare by default. Set `NITRO_PRESET` (for example
`NITRO_PRESET=vercel`) to build for another platform.
