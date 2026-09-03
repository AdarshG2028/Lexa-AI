from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

SttProviderName = Literal["groq", "mock"]
LlmProviderName = Literal["groq", "mock"]
TtsProviderName = Literal["groq", "deepgram", "mock"]
GrammarProviderName = Literal["groq", "mock"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    stt_provider: SttProviderName = "mock"
    llm_provider: LlmProviderName = "mock"
    tts_provider: TtsProviderName = "mock"

    grammar_provider: GrammarProviderName = "mock"

    # Ordered comma-separated names tried when tts_provider fails, e.g. "groq,mock".
    tts_fallback_providers: str = ""

    groq_api_key: str = ""
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_stt_model: str = "whisper-large-v3-turbo"
    groq_llm_model: str = "openai/gpt-oss-120b"
    # Falls back to groq_llm_model when blank.
    groq_grammar_model: str = ""
    groq_tts_model: str = "canopylabs/orpheus-v1-english"
    groq_tts_voice: str = "troy"
    groq_tts_format: str = "wav"

    deepgram_api_key: str = ""
    deepgram_base_url: str = "https://api.deepgram.com"
    deepgram_tts_model: str = "aura-2-thalia-en"

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
    def uses_groq(self) -> bool:
        return "groq" in {
            self.stt_provider, self.llm_provider, self.grammar_provider,
            *self.tts_chain,
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
