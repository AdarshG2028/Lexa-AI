# Lexa — AI voice conversation and speech coach

Speak to an AI partner, then get feedback on grammar, vocabulary, fluency and
phoneme-level pronunciation.

| Folder | What it is |
|---|---|
| [`backend/`](backend/) | FastAPI service: speech-to-text, LLM, text-to-speech and the four analyses |
| [`frontend/`](frontend/) | TanStack Start / React app for the conversation and the report |

## Run both

```
# terminal 1
powershell -File backend/scripts/start-backend.ps1

# terminal 2
powershell -File frontend/start-frontend.ps1
```

Backend on http://localhost:8001 (Swagger at `/docs`), frontend on
http://localhost:8080. The backend needs a `backend/.env` — copy
`backend/.env.example` and add `GROQ_API_KEY`.

See each folder's README for details.
