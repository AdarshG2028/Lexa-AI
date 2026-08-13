# Lexa

An AI conversational assistant you practice speaking with. Have a real voice
conversation, and when you hang up Lexa turns the transcript into a report of
your grammar and pronunciation improvements. Speech-to-text and text-to-speech
drive the call; this repository is the frontend — the landing page, the
conversation page, and the insights report.

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
