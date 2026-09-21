# AI Voice Conversation & Speech Coach — Backend

A backend for an application where a user has a natural 5–8 minute spoken
conversation with an AI, and afterwards receives an analysis of how they
communicate: grammar, vocabulary, fluency, and phoneme-level pronunciation.

This repository contains the **backend and AI pipeline only**. There is no
frontend; a future web or mobile client will consume these APIs.

**Current status: Phase 7 complete.** You can hold a multi-turn spoken
conversation, the AI remembers what was said earlier, the whole conversation is
persisted and retrievable as a transcript, and the backend analyses the user's
grammar, vocabulary, fluency and phoneme-level pronunciation afterwards.

---

## Architecture

Four layers, with dependencies pointing in one direction only:

```
API layer          FastAPI routers — HTTP parsing and serialization only
    |  Depends()
Service layer      ConversationService — orchestrates a turn
    |  Protocols
Provider adapters  groq/, deepgram/ and mock/ — the only provider-aware code
Persistence        SessionRepository (SQLite), AudioStorage (local disk)
```

One conversational turn:

```
POST audio -> validate -> normalize to 16 kHz mono WAV -> store
           -> SpeechToTextProvider  -> transcript
           -> build_messages(session history + this message)
           -> LLMProvider           -> reply text
           -> TextToSpeechProvider  -> reply audio -> store
           -> JSON { transcript, reply_text, audio_url, timings_ms }
```

### Conversation context

`app/conversation/history.py` turns a session's stored turns into the message
list sent to the model. A 5-8 minute conversation can run to dozens of
exchanges, and replaying all of them on every turn would grow both cost and
latency without bound, so two limits apply:

- `CONVERSATION_HISTORY_TURNS` - only the most recent N exchanges are considered.
- `CONVERSATION_HISTORY_MAX_CHARS` - the oldest of those are dropped until the
  history fits the budget.

Trimming always removes a **complete exchange**, never half of one, so the
model is never shown a reply whose question has gone missing. Each turn
response reports `history_messages`, the number of messages actually sent, so
the context window is observable rather than guesswork.

### Session lifecycle

```
active ──POST /end──> completed
   └────idle > SESSION_IDLE_TIMEOUT_MINUTES────> expired
```

Only an `active` session accepts new turns; a completed one returns
`SESSION_NOT_ACTIVE` and an expired one returns `SESSION_EXPIRED`. Idleness is
measured from the last turn, not from session start, so a long conversation
never times out mid-flow. Ending a session is idempotent.

A finished or expired session stays fully readable — the transcript is the
input to every later analysis phase, so ending a conversation must never make
it inaccessible.

### Provider independence

The application depends on three `typing.Protocol` interfaces in
`app/providers/base.py`:

| Interface | Groq implementation | Offline implementation |
|---|---|---|
| `SpeechToTextProvider` | `GroqSpeechToTextProvider` | `MockSpeechToTextProvider` |
| `GrammarAnalysisProvider` | `GroqGrammarAnalysisProvider` | `MockGrammarAnalysisProvider` (rule-based) |
| `VocabularyAnalysisProvider` | `GroqVocabularyAnalysisProvider` | `MockVocabularyAnalysisProvider` (thesaurus) |
| `LLMProvider` | `GroqLLMProvider` | `MockLLMProvider` |
| `TextToSpeechProvider` | `GroqTextToSpeechProvider`, `DeepgramTextToSpeechProvider` | `MockTextToSpeechProvider` |

`app/providers/registry.py` is the single place that maps a configured provider
name to a class. Groq's HTTP responses are converted into application models
(`Transcription`, `ChatReply`, `SynthesizedSpeech`) inside the adapters, so no
`httpx` object and no Groq-shaped JSON reaches the service layer. Swapping to
OpenAI or a local Whisper means adding an adapter and a registry line — no
business logic changes.

The mock providers are not only for tests. Setting the providers to `mock` runs
the entire pipeline offline and deterministically, which proves the abstraction
holds and gives you a working demo when there is no network.

### TTS fallback chain

Text-to-speech is the leg most likely to fail in a demo: free tiers run out,
and vendors rate limit. `TTS_FALLBACK_PROVIDERS` names an ordered list tried
when the primary fails, so a conversation degrades to a lesser voice rather
than ending. Every turn response reports the `tts_provider` that actually
served the audio, so a downgrade is never silent.

```
TTS_PROVIDER=groq
TTS_FALLBACK_PROVIDERS=deepgram,mock
```

A provider with no credentials configured is dropped from the chain rather
than breaking it, so listing a fallback you have not signed up for is safe.

**Measured TTS latency** for one identical sentence (~3.6-3.9 s of audio),
non-streaming REST, from a machine in India:

| Provider | Time to complete audio |
|---|---|
| Groq `canopylabs/orpheus-v1-english` | ~920 ms |
| Deepgram `aura-2-thalia-en` | ~2780 ms |

Deepgram publishes a much lower figure, but that is *time to first byte* on its
streaming endpoint. This backend requests a complete audio file over REST, so
the whole synthesis is on the critical path and the streaming advantage does
not apply. Groq is therefore the default, with Deepgram as the first fallback:
its far larger free credit makes it a good safety net when a Groq quota or
model-access limit is hit. If WebSocket streaming is added later, this
comparison should be re-run — the ranking may well reverse.

### Persistence

Conversations are stored in a relational database through SQLAlchemy. The
domain models in `app/models.py` stay independent of the ORM: `app/db/models.py`
holds the tables, and `SqlSessionRepository` maps between them. Nothing above
the repository knows a database exists.

```
sessions          id, user_id, status, started_at, last_activity_at, ended_at
turns             id, session_id, index, created_at, speaker, transcript,
                  assistant_response, and the audio reference columns
turns.words       word timings as JSON, the basis of fluency analysis
speech_analyses   one row per conversation, one nullable section per analysis
grammar_issues    child rows
vocabulary_issues child rows
fluency_findings  child rows, queryable so Phase 9 can track recurring fillers
pronunciation_issues  child rows, indexed on phoneme for cross-session tracking
```

A conversation has **one** analysis record made of independent sections.
Saving grammar leaves vocabulary untouched and the other way round, so the two
endpoints can be run in either order. Fluency and pronunciation add their own
sections to that same row.

Audio itself is **not** stored in the database. The rows hold the object key,
format, duration and size; the bytes live behind `AudioStorage`, which writes
to local disk today and can become object storage without touching the schema.

`SESSION_STORE=memory` switches back to the in-memory store, which is useful
for throwaway experiments. Both implementations are verified against the same
contract test suite in `tests/test_session_repositories.py`, so the swap is
provably behaviour-preserving.

Tables are created at startup if missing, which covers the new tables that
later analysis phases will add. It does not alter existing columns — a real
migration tool belongs here if the schema ever changes destructively.

**SQLite stores no timezone**, so a `UtcDateTime` type decorator normalises
datetimes on write and restores UTC on read. Without it the session idle check
would compare a naive datetime against an aware one and crash.

### Transcripts

`GET /api/v1/sessions/{id}/transcript` returns the complete conversation. A
stored turn holds one exchange, so each turn is flattened into up to two
entries in speaking order — which is the shape the analysis phases need.

Add `?format=text` for a plain-text version. A real one, recorded against
Groq and read back after restarting the server:

```
You: Hi, my name is Adarsh and I am from Kerala.
AI: Hi Adarsh! Nice to meet you. How's life in Kerala - any favorite spots?
You: I want to improve my English speaking.
AI: That's a great goal! What kind of situations do you usually practice in?
You: Hello, I go to college yesterday and it was very good. The teacher
     explained the lesson very good, so I am thinking about it.
AI: Sounds like a rewarding day! What was the lesson about?
```

The transcript is available at any time, including after the session has ended
or expired.

### Grammar analysis

After a conversation, `POST /api/v1/sessions/{id}/analysis/grammar` assesses
what the **user** said. The assistant's replies are never analysed.

The provider finds mistakes; **scoring stays in the application** and is
deterministic, so the same conversation always scores the same and the number
can be explained without appealing to a model's opinion. The score is the
proportion of sentences that contained a mistake:

```
score = 100 - min(1, sum(worst confidence per flawed sentence) / sentences) * 100
```

Issues are grouped by their sentence, so a sentence with three errors is still
one flawed sentence rather than three - otherwise a single bad sentence can
sink the whole score. Each flawed sentence costs the confidence of its
strongest finding, so an uncertain guess hurts less than a definite error.

A conversation with nothing to analyse scores 100, not 0 — no evidence of
mistakes is not evidence of bad grammar.

Findings are filtered before they reach the user. No-op "corrections",
anything below 0.4 confidence and duplicates are dropped, and the list is
capped. A coach that invents mistakes is worse than one that misses a few.

Turns are split into sentences before analysis, so a finding quotes one
sentence rather than a whole spoken paragraph. Models do not reliably respect
that instruction, so it is also enforced afterwards: a finding is dropped when
it restates a mistake already reported against a narrower quote, or when it
merely re-reports two findings already made under a different label.

**The transcript is never rewritten.** Each issue carries its own copy of the
original text, and a test asserts the stored transcript is byte-identical
before and after analysis.

The offline provider is genuinely rule-based rather than a stub — regular
expressions for past-tense markers, adjective-for-adverb, subject-verb
agreement and articles before vowels. It finds real mistakes with no API key,
which keeps the demo working and the tests deterministic.

Analysis runs synchronously: a conversation's worth of text is one provider
call. When audio models arrive in Phase 7, this is the endpoint that moves
behind a background job.

### Vocabulary analysis

`POST /api/v1/sessions/{id}/analysis/vocabulary` reports repeated words and
phrases, over-used basic words, and expressions that are grammatical but sound
unnatural.

**Counting happens in code, not in the model.** "You said 'very good' four
times" is arithmetic, and a language model asked to count will sometimes get
it wrong. So `app/analysis/vocabulary.py` measures the counts and the provider
is asked only for the part that needs language sense: which word would have
been better. Counts returned by the model are ignored entirely, and there is a
test that proves a miscounting model cannot change the number shown.

Detection details that matter in practice:

- The repetition threshold **scales with conversation length**. Saying
  "college" three times in eighty words is a habit; in eight hundred it is
  just the topic.
- Phrases are **trimmed to the words that carry meaning**, so a learner is
  told about `very good` rather than `was very good`.
- A phrase hides a word only when it accounts for every use of it -
  `very good` x3 does not explain `good` x7.

**Lexical diversity is reported but deliberately not scored.** Type-token
ratio falls as any text gets longer, so scoring it would penalise a learner
for talking more, which is the opposite of what this app wants.

The score charges only *excess* repetition - using a word up to its threshold
is normal speech. When excess reaches 15% of everything said, the score is
zero.

### Fluency analysis

`POST /api/v1/sessions/{id}/analysis/fluency` measures **how** the user spoke
rather than what they said: speaking rate, pauses, filler words, immediate
repetitions and false starts.

**This phase has no provider and never calls a language model.** Speaking rate
and pause length are measurements, not opinions - a model asked for them would
be guessing at numbers this code reads directly from the audio timings.

It works because transcription requests word-level timestamps:

```
STT -> verbose_json + timestamp_granularities=word
    -> [{word, start, end}, ...] stored on the turn
    -> gaps between words are pauses, words per second is rate
```

Timings are **stored on the turn**, not recomputed. Fluency runs after the
conversation, and re-transcribing later would spend another provider call on
data already in hand.

Details worth knowing:

- A gap of 0.5 s counts as a pause, 1.0 s as a long one.
- **Silence between turns is not blamed on the user** - that gap is the AI
  speaking. Time is summed per turn, never across them.
- Speaking rate and *articulation* rate are both reported. Articulation rate
  excludes pause time, so it answers "how fast when actually talking".
- The comfortable band is 110-160 WPM; outside it the score falls.
- One false start trips two overlapping word pairs ("I want to, I want to"),
  and is counted once.

The score has four equally weighted parts - rate, pauses, fillers,
disfluencies - each capped at 25 points, so no single habit can sink the score
alone and the arithmetic stays explainable.

**A text-only conversation returns `fluency_score: null`** with a note, rather
than a fabricated number. Fluency cannot be measured from typed text, and
guessing would be worse than saying so.

Measured against three generated samples:

| sample | score | WPM | long pauses | fillers | repetitions | restarts |
|---|---|---|---|---|---|---|
| `clean.wav` | 100 | 158.9 | 0 | 0 | 0 | 0 |
| `hesitant.wav` | 19 | 83.9 | 3 | 7 | 1 | 1 |

### Phoneme-level pronunciation

`POST /api/v1/sessions/{id}/analysis/pronunciation` compares the sounds the
speaker produced against the sounds their words require.

This is the one part of the system that **runs a model on our own hardware**
rather than calling an API. Everything else is a network request; this is a
316M-parameter wav2vec2 CTC model doing acoustic analysis locally.

```
transcript --g2p_en--> expected phonemes (ARPAbet -> IPA), tagged by word
audio      --wav2vec2--> detected phonemes (IPA) + per-phoneme confidence
                  |
          Needleman-Wunsch alignment
                  |
          substitutions, e.g. /θ/ -> /t/ in "think"
                  |
          aggregate across the whole conversation
                  |
          strict filtering -> a small number of trustworthy claims
```

Global alignment is used rather than index-by-index comparison: a learner who
drops or inserts one sound would otherwise throw every later phoneme out of
step and produce a cascade of false errors.

**No espeak or phonemizer is needed.** The tokenizer is loaded with
`do_phonemize=False`, which skips the backend that would otherwise require a
native espeak-ng install - the reason this works unchanged on Windows and in a
slim container.

#### Not inventing errors

Phoneme feedback on accented speech produces false positives very easily, so
four filters sit between the model and the learner:

1. **Notation folding.** CMUdict writes /ʌ/ where the model hears /ɐ/, /ɚ/
   where it hears /ɜː/, and marks vowel length the model omits. Those are
   transcription differences, not mispronunciations, and are folded together
   before anything is compared.
2. **Reduced vowels in function words are not judged.** Nobody says "and" with
   the vowel the dictionary gives it. Consonants in those words *are* still
   assessed, otherwise almost all evidence for /ð/ would vanish.
3. **A pattern must recur** at least 3 times with mean confidence >= 0.55.
4. **A pattern must appear in at least 2 different words.** One recogniser
   slip repeated on a single word is not a pronunciation habit.

Findings are worded as *"this may be worth practising"*, never as an
accusation.

#### Measured behaviour

Two recordings of the same sentences, one pronounced correctly and one with
/θ/ and /ð/ deliberately replaced by /t/ and /d/:

| audio | score | raw substitutions | reported to learner |
|---|---|---|---|
| correct | **100/100** | 6 | **0** |
| mispronounced | **69/100** | 18 | **1** - `/θ/ -> /t/` x6 in "three, thank" |

Eighteen raw mismatches became one trustworthy claim, and correct speech
produced no findings at all.

#### Performance

Warm inference runs at roughly **1.35x realtime** on 4 CPU threads, so three
minutes of speech takes about two minutes. Loading the weights costs a further
60-100 seconds on the first call only, which is why the provider is held for
the life of the process.

Set `PRONUNCIATION_TORCH_THREADS` to your core count; the default leaves torch
using half of them.

#### Installing it

The ML stack is **not** a base dependency - the conversation API never loads a
model and should not carry ~500 MB of wheels:

```bash
uv sync --group pronunciation
```

`PRONUNCIATION_PROVIDER=mock` needs none of it and is spelling-based, for
exercising the aggregation and reporting offline. It cannot hear anything and
is not a substitute for the model.

Set `HF_HOME=./data/models` to keep ~1.9 GB of weights off the system drive.

### Project layout

```
app/
  main.py                       app factory, exception handlers, startup checks
  config.py                     centralized settings from environment
  models.py                     Session, Turn, and provider-neutral DTOs
  api/deps.py                   dependency injection wiring
  api/routes/                   conversation.py, health.py
  conversation/history.py       trims session turns into LLM messages
  conversation/prompts.py       the conversation-partner system prompt
  conversation/transcript.py    flattens turns into a speaker transcript
  analysis/grammar.py           collects user speech, scores, filters
  analysis/vocabulary.py        counts repetition, scores, thresholds
  analysis/fluency.py           rate, pauses, fillers - no model involved
  analysis/phonemes.py          ARPAbet->IPA, alignment, notation folding
  analysis/g2p.py               expected phonemes (lazy nltk import)
  analysis/pronunciation.py     aggregation and the strictness rules
  providers/wav2vec2/           the local phoneme model
  analysis/sql.py               analysis persistence
  db/models.py                  SQLAlchemy tables + UTC datetime handling
  db/engine.py                  engine, session factory, table creation
  services/conversation_service.py   the turn orchestration
  providers/base.py             the three provider interfaces
  providers/groq/               client.py + stt.py, llm.py, tts.py
  providers/deepgram/           client.py + tts.py
  providers/fallback.py         TTS chain: degrade rather than fail
  providers/mock/               offline implementations
  audio/processing.py           ffmpeg validation and normalization
  sessions/                     repository interface, in-memory and SQL stores
  storage/                      storage interface + local disk store
scripts/make_sample.py          generates a test audio file
tests/
```

---

## Setup

Requires Python 3.12+, [uv](https://docs.astral.sh/uv/), and **ffmpeg**
(`ffmpeg` and `ffprobe` must be on `PATH`).

```bash
uv sync
cp .env.example .env
```

Then edit `.env`.

### Environment variables

| Variable | Purpose |
|---|---|
| `STT_PROVIDER`, `LLM_PROVIDER` | `groq` or `mock` |
| `TTS_PROVIDER` | `groq`, `deepgram` or `mock` |
| `GRAMMAR_PROVIDER` | `groq` or `mock` (offline, rule-based) |
| `VOCABULARY_PROVIDER` | `groq` or `mock` (offline, thesaurus) |
| `PRONUNCIATION_PROVIDER` | `wav2vec2` (local model) or `mock` |
| `PRONUNCIATION_MODEL` | Defaults to `facebook/wav2vec2-lv-60-espeak-cv-ft` |
| `PRONUNCIATION_TORCH_THREADS` | 0 lets torch decide; your core count is faster |
| `HF_HOME` | Where model weights are cached |
| `GROQ_VOCABULARY_MODEL` | Blank uses `GROQ_LLM_MODEL` |
| `GROQ_GRAMMAR_MODEL` | Blank uses `GROQ_LLM_MODEL` |
| `TTS_FALLBACK_PROVIDERS` | Ordered fallbacks, e.g. `groq,mock` |
| `DEEPGRAM_API_KEY`, `DEEPGRAM_TTS_MODEL` | Deepgram credentials and voice |
| `GROQ_API_KEY` | Groq API key. Never commit this. |
| `GROQ_BASE_URL` | Defaults to Groq's OpenAI-compatible endpoint |
| `GROQ_STT_MODEL` | e.g. `whisper-large-v3-turbo` |
| `GROQ_LLM_MODEL` | e.g. `openai/gpt-oss-120b` |
| `GROQ_TTS_MODEL`, `GROQ_TTS_VOICE` | **A matched pair** — voice names are not portable between TTS models |
| `PROVIDER_CONNECT_TIMEOUT`, `PROVIDER_READ_TIMEOUT` | Seconds. The read timeout must be generous; Whisper on a long clip exceeds httpx's 5s default. |
| `CONVERSATION_HISTORY_TURNS`, `CONVERSATION_HISTORY_MAX_CHARS` | How much conversation the model sees each turn |
| `SESSION_IDLE_TIMEOUT_MINUTES` | Idle time after which a session stops accepting turns |
| `MAX_UPLOAD_BYTES`, `MAX_AUDIO_SECONDS` | Upload limits |
| `SESSION_STORE` | `database` or `memory` |
| `DATABASE_URL` | Defaults to `sqlite+aiosqlite:///./data/voice_ai.db` |
| `STORAGE_LOCAL_PATH` | Where audio is written |

Model IDs change over time. List the currently valid ones with:

```bash
curl -H "Authorization: Bearer $GROQ_API_KEY" https://api.groq.com/openai/v1/models
```

If a configured model ID has been retired, the API returns a `CONFIG_ERROR`
that names this command, and `GET /health/providers` reports the provider as
not `ok` before you ever send a turn.

**Groq TTS requires one-time terms acceptance** in the Groq console before
first use. Until then, synthesis returns a `CONFIG_ERROR` quoting the
provider's own instructions and link, and the conversation still works with
`TTS_PROVIDER=mock`.

Model availability differs per account. On the account this was developed
against, no Llama chat models were offered — hence the `openai/gpt-oss-120b`
default. Always check `/models` rather than trusting a documentation page.

---

## Running

```bash
uv run uvicorn app.main:app --reload --port 8000
```

Interactive API docs: <http://127.0.0.1:8000/docs>

`--reload` can miss several edits made in quick succession, leaving the server
running stale code. If behaviour does not match the source, restart it without
`--reload` before concluding anything is broken.

To run with no API key and no network, set all three providers to `mock`.

## Testing

```bash
uv run pytest
```

The suite is fully offline. Provider dependencies are replaced via
`app.dependency_overrides` in `tests/conftest.py`, and the Groq adapter tests
use a mocked HTTP transport (`respx`), so no test makes a network call.

---

## API

Base path `/api/v1`. All errors share one envelope:

```json
{ "error": { "code": "SESSION_NOT_FOUND", "message": "...", "details": {} } }
```

Codes: `INVALID_AUDIO`, `UNSUPPORTED_AUDIO_FORMAT`, `AUDIO_TOO_LARGE`,
`SESSION_NOT_FOUND`, `SESSION_NOT_ACTIVE`, `SESSION_EXPIRED`,
`TURN_NOT_FOUND`, `PROVIDER_UNAVAILABLE`,
`PROVIDER_TIMEOUT`, `PROVIDER_BAD_RESPONSE`, `CONFIG_ERROR`, `STORAGE_ERROR`,
`ANALYSIS_NOT_FOUND`, `VALIDATION_ERROR`, `INTERNAL_ERROR`.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Liveness, ffmpeg presence, configured providers |
| `GET` | `/health/providers` | Checks each provider is reachable and its configured model still exists |
| `POST` | `/api/v1/sessions` | Start a session |
| `GET` | `/api/v1/sessions/{id}` | Session state and turns so far |
| `POST` | `/api/v1/sessions/{id}/turns` | Multipart audio in, reply out |
| `POST` | `/api/v1/sessions/{id}/turns/text` | Text in, voice out |
| `GET` | `/api/v1/sessions/{id}/transcript` | Complete transcript (`?format=text` for plain text) |
| `GET` | `/api/v1/sessions/{id}/turns/{turn_id}/audio` | Reply audio bytes |
| `GET` | `/api/v1/sessions/{id}/turns/{turn_id}/audio/user` | The user's own audio, 16 kHz mono WAV |
| `POST` | `/api/v1/sessions/{id}/end` | Mark the session completed (idempotent) |
| `POST` | `/api/v1/sessions/{id}/analysis/grammar` | Run grammar analysis and store it |
| `GET` | `/api/v1/sessions/{id}/analysis/grammar` | The stored grammar analysis |
| `POST` | `/api/v1/sessions/{id}/analysis/vocabulary` | Run vocabulary analysis and store it |
| `GET` | `/api/v1/sessions/{id}/analysis/vocabulary` | The stored vocabulary analysis |
| `POST` | `/api/v1/sessions/{id}/analysis/fluency` | Run fluency analysis and store it |
| `GET` | `/api/v1/sessions/{id}/analysis/fluency` | The stored fluency analysis |
| `POST` | `/api/v1/sessions/{id}/analysis/pronunciation` | Run phoneme analysis (slow) |
| `GET` | `/api/v1/sessions/{id}/analysis/pronunciation` | The stored pronunciation analysis |

Supported upload formats: `flac, mp3, mp4, mpeg, mpga, m4a, ogg, wav, webm`.

### Example

Generate a test audio file, since there is no frontend to record one:

```bash
uv run python scripts/make_sample.py
```

That uses the configured TTS provider. To produce test audio with no API
key and no network at all, Windows can synthesize speech locally:

```powershell
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.SetOutputToWaveFile("samples/user_turn.wav")
$s.Speak("Hello, I go to college yesterday and it was very good.")
$s.Dispose()
```

Then:

```bash
# 1. Start a session
curl -s -X POST http://127.0.0.1:8000/api/v1/sessions

# 2. Send audio, substituting the id from step 1
curl -s -X POST http://127.0.0.1:8000/api/v1/sessions/SESSION_ID/turns \
     -F "file=@samples/user_turn.wav"

# 3. Download the AI's spoken reply
curl -s http://127.0.0.1:8000/api/v1/sessions/SESSION_ID/turns/TURN_ID/audio \
     -o reply.wav
```

A real turn response, recorded end to end against Groq with
`whisper-large-v3-turbo`, `openai/gpt-oss-120b` and
`canopylabs/orpheus-v1-english`:

```json
{
  "session_id": "e4defe66...",
  "turn_id": "478390a2...",
  "transcript": "Hello, I go to college yesterday and it was very good. The teacher explained the lesson very good, so I am thinking about it.",
  "reply_text": "That sounds great! What was the lesson about?",
  "audio_url": "/api/v1/sessions/e4defe66.../turns/478390a2.../audio",
  "tts_provider": "groq",
  "timings_ms": { "stt": 518, "llm": 748, "tts": 702, "total": 1968 }
}
```

Note that the reply is short, ends with a follow-up question, and does not
correct the user's grammar — the tense error and the repeated "very good" are
left alone on purpose. Correction is the job of the later analysis phases.

### A real multi-turn conversation

Recorded against Groq (`whisper-large-v3-turbo`, `openai/gpt-oss-120b`,
`canopylabs/orpheus-v1-english`). `ctx` is the `history_messages` field:

```
TURN 1  ctx=2
  me : Hi! My name is Adarsh and I study computer science in Kerala.
  ai : Nice to meet you, Adarsh! How are you finding computer science
       classes in Kerala? Is there a particular project you're excited about?

TURN 2  ctx=4
  me : My favourite subject is machine learning.
  ai : Machine learning is such a fascinating field! Are you working on any
       models or datasets at the moment, or just exploring the concepts?

TURN 3  ctx=6
  me : Do you remember what my name is and what I like studying?
  ai : Absolutely, Adarsh - you're studying computer science in Kerala, and
       your favorite subject is machine learning. What sparked your interest?
```

Note that when the same session is given audio containing "I go to college
yesterday" and "very good" twice, the reply still does not correct either
mistake. That is the system prompt working as intended: correction belongs to
the analysis phases, not the conversation.

### A real grammar report

From `scripts/demo.py` against Groq:

```
grammar score      59/100
sentences analysed 7      words analysed 83      issues found 4

  1. [tense] confidence 0.96
     was : I go to college yesterday and it was very good.
     fix : I went to college yesterday and it was very good.
     why : Use past tense 'went' for an action that happened yesterday.

  2. [word_form] confidence 0.95
     was : The teacher explained the lesson very good, so I am thinking about it.
     fix : The teacher explained the lesson very well, so I am thinking about it.
     why : Use the adverb 'well' to modify the verb 'explained'.

  3. [subject_verb_agreement] confidence 0.94
     was : My friend he go to the same college and we ate a apple together.
     fix : My friend goes to the same college and we ate a apple together.
     why : Subject-verb agreement: 'he go' should be 'goes'.

  4. [articles] confidence 0.94
     was : My friend he go to the same college and we ate a apple together.
     fix : My friend goes to the same college and we ate an apple together.
     why : Use 'an' before a vowel sound: 'an apple'.
```

### Trying it in one command

`scripts/demo.py` runs a scripted conversation containing deliberate mistakes,
ends the session, prints the transcript and then the grammar report:

```bash
uv run python scripts/demo.py
uv run python scripts/demo.py --audio samples/user_turn.wav
```

### Demonstration script

A 45-60 second walkthrough, with the server running:

1. *"This is the backend for a speech coach. There's no frontend yet - I'm
   driving it entirely through its API."* Open `/docs`.
2. *"First, a health check showing which AI providers are wired in."*
   `GET /health/providers`.
3. *"I start a conversation session."* `POST /api/v1/sessions`.
4. *"I tell it my name and what I study."* Two text turns.
5. *"Now I ask whether it remembers."* Third turn - point at the reply. *"It
   recalls both facts, because the backend replays the session's earlier
   exchanges to the model on every turn. `history_messages` shows exactly how
   much context was sent."*
6. *"And this all works with speech too."* Post the audio file, then download
   and play the reply.
7. *"Notice it never corrected my grammar, even though I said 'I go to college
   yesterday'. That's deliberate - correction is the next phase."*
8. *"When I end the session, it stops accepting turns but stays readable."*
   `POST /end`, then a refused turn.
9. *"Now the point of the project: the backend analyses how I spoke."*
   `POST /analysis/grammar` - walk through one issue: the original sentence,
   the correction, the category and why. *"The score is computed by my code,
   not asked of the model, so it is deterministic and I can explain it."*

---

## Implementation phases

| Phase | Scope | Status |
|---|---|---|
| 1 | Audio in, AI voice out | **Complete** |
| 2 | Contextual multi-turn conversation | **Complete** |
| 3 | Database persistence and transcripts | **Complete** |
| 4 | Grammar analysis | **Complete** |
| 5 | Vocabulary analysis | **Complete** |
| 6 | Fluency analysis | **Complete** |
| 7 | Phoneme-level pronunciation | **Complete** |
| 8 | Unified speech analysis report | Not started |
| 9 | Cross-session progress tracking | Not started |

### Known for Phase 8

Grammar and vocabulary run independently and can both flag the same span. A
wrong preposition such as "discuss about" is legitimately a grammar error and
an unnatural expression, so it currently appears in both reports. The unified
report in Phase 8 needs to deduplicate across sections rather than either
section suppressing the other.

### Deferred, deliberately

- **Persistence.** Sessions live in memory and are lost on restart. The
  `SessionRepository` interface exists so Phase 3 swaps the implementation
  rather than rewriting the service.
- **All analysis.** Phases 4–9.
- **Authentication**, object storage, background workers and queues.
- **Streaming.** A REST round trip means the full utterance must arrive before
  transcription starts, so expect roughly 2–4 seconds per turn. Genuinely
  conversational latency needs WebSocket streaming with incremental STT and
  chunked TTS playback. That is a known limitation, not an oversight.

User audio *is* retained as normalized 16 kHz mono WAV from Phase 1 onward,
because Phases 6 and 7 analyse the audio itself, and discarded audio cannot be
recovered.
