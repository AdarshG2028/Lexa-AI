# Lexa — AI voice conversation and speech coach

Speak to an AI partner, then get feedback on grammar, vocabulary, fluency and
phoneme-level pronunciation.

| Folder | What it is |
|---|---|
| [`backend/`](backend/) | FastAPI service: speech-to-text, LLM, text-to-speech and the four analyses |
| [`frontend/`](frontend/) | TanStack Start / React app for the conversation and the report |

## Run it

One entry point, `dev.ps1`, from the repo root:

```
.\dev.ps1                # backend and frontend, each in its own window
.\dev.ps1 backend        # backend only, in this window
.\dev.ps1 frontend       # frontend only, in this window
.\dev.ps1 status         # what is running
.\dev.ps1 stop           # stop both (only processes started from this repo)
```

The individual scripts also work on their own:
`backend/scripts/start-backend.ps1` and `frontend/start-frontend.ps1`.

Backend on http://localhost:8001 (Swagger at `/docs`), frontend on
http://localhost:8080. The backend needs a `backend/.env` — copy
`backend/.env.example` and add `GROQ_API_KEY`.

See each folder's README for details.
