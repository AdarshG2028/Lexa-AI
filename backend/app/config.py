from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

SttProviderName = Literal["groq", "mock"]
LlmProviderName = Literal["groq", "mock"]
TtsProviderName = Literal["groq", "deepgram", "mock"]
GrammarProviderName = Literal["groq", "mock"]
VocabularyProviderName = Literal["groq", "mock"]
PronunciationProviderName = Literal["wav2vec2", "mock", "off"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    stt_provider: SttProviderName = "mock"
    llm_provider: LlmProviderName = "mock"
    tts_provider: TtsProviderName = "mock"

    grammar_provider: GrammarProviderName = "mock"
    vocabulary_provider: VocabularyProviderName = "mock"
    pronunciation_provider: PronunciationProviderName = "mock"

    # Ordered comma-separated names tried when tts_provider fails, e.g. "groq,mock".
    tts_fallback_providers: str = ""

    groq_api_key: str = ""
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_stt_model: str = "whisper-large-v3-turbo"
    groq_llm_model: str = "openai/gpt-oss-120b"
    # Falls back to groq_llm_model when blank.
    groq_grammar_model: str = ""
    groq_vocabulary_model: str = ""
    groq_tts_model: str = "canopylabs/orpheus-v1-english"
    groq_tts_voice: str = "troy"
    groq_tts_format: str = "wav"

    deepgram_api_key: str = ""
    deepgram_base_url: str = "https://api.deepgram.com"
    deepgram_tts_model: str = "aura-2-thalia-en"

    # Phoneme model. Emits IPA directly, so no espeak backend is required.
    pronunciation_model: str = "facebook/wav2vec2-lv-60-espeak-cv-ft"
    # 0 leaves torch to decide. Setting it to the core count roughly doubles
    # throughput on a small machine.
    pronunciation_torch_threads: int = 0

    # How much evidence a phoneme pattern needs before a learner is told about
    # it. The defaults suit a full 5-8 minute conversation; lower them for
    # short test clips, accepting more false positives.
    pronunciation_min_occurrences: int = 3
    pronunciation_min_confidence: float = 0.55
    pronunciation_min_distinct_words: int = 2

    provider_connect_timeout: float = 10.0
    provider_read_timeout: float = 90.0

    # How much of the conversation the model is shown on each turn.
    conversation_history_turns: int = 12
    conversation_history_max_chars: int = 8000

    # A session with no activity for this long can no longer accept turns.
    session_idle_timeout_minutes: float = 30.0

    max_upload_bytes: int = 25_000_000
    max_audio_seconds: float = 300.0

    # "database" persists conversations; "memory" keeps them only until restart.
    session_store: Literal["database", "memory"] = "database"
    database_url: str = "sqlite+aiosqlite:///./data/voice_ai.db"

    storage_provider: Literal["local"] = "local"
    storage_local_path: str = "data/audio"

    # Browser origins permitted to call this API. A browser refuses a
    # cross-origin request unless the server names the origin explicitly, so
    # the frontend dev server has to appear here to reach the backend at all.
    cors_allowed_origins: str = (
        "http://localhost:8080,http://127.0.0.1:8080,http://localhost:8081,http://127.0.0.1:8081,http://localhost:5173,http://127.0.0.1:5173"
    )

    # A regex for origins that cannot be listed in advance. Vercel gives every
    # preview deployment its own subdomain, so a fixed list never matches them.
    # Blank disables it; the exact list above is always honoured.
    cors_allowed_origin_regex: str = ""

    # Per-IP request limits, counted over a sliding one-minute window. The two
    # tight ones cover the calls that spend provider quota; everything else
    # shares the general limit. 0 turns a limit off.
    rate_limit_enabled: bool = True
    rate_limit_turns_per_minute: int = 20
    rate_limit_analysis_per_minute: int = 10
    rate_limit_general_per_minute: int = 120
    # How many reverse proxies sit in front of this app. Behind Render the
    # socket peer is always the proxy, so without this every user would share
    # one limit. 0 trusts the socket address, which is right when run directly.
    trusted_proxy_hops: int = 0

    log_level: str = "INFO"

    @property
    def tts_chain(self) -> list[str]:
        """The TTS provider order: the primary followed by any fallbacks,
        with duplicates removed so a name is never tried twice."""
        names = [self.tts_provider]
        for name in self.tts_fallback_providers.split(","):
            cleaned = name.strip()
            if cleaned and cleaned not in names:
                names.append(cleaned)
        return names

    @property
    def cors_origins(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.cors_allowed_origins.split(",")
            if origin.strip()
        ]

    @property
    def uses_groq(self) -> bool:
        return "groq" in {
            self.stt_provider, self.llm_provider, self.grammar_provider,
            self.vocabulary_provider, *self.tts_chain,
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
