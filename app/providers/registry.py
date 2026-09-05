from app.config import Settings
from app.core.errors import ConfigError
from app.providers.base import (
    GrammarAnalysisProvider,
    LLMProvider,
    SpeechToTextProvider,
    TextToSpeechProvider,
    VocabularyAnalysisProvider,
)
from app.providers.deepgram.client import DeepgramClient
from app.providers.deepgram.tts import DeepgramTextToSpeechProvider
from app.providers.fallback import FallbackTextToSpeechProvider
from app.providers.groq.client import GroqClient
from app.providers.groq.grammar import GroqGrammarAnalysisProvider
from app.providers.groq.llm import GroqLLMProvider
from app.providers.groq.stt import GroqSpeechToTextProvider
from app.providers.groq.tts import GroqTextToSpeechProvider
from app.providers.groq.vocabulary import GroqVocabularyAnalysisProvider
from app.providers.mock.grammar import MockGrammarAnalysisProvider
from app.providers.mock.llm import MockLLMProvider
from app.providers.mock.stt import MockSpeechToTextProvider
from app.providers.mock.tts import MockTextToSpeechProvider
from app.providers.mock.vocabulary import MockVocabularyAnalysisProvider


class ProviderRegistry:
    """Builds the configured provider implementations. This is the only place
    that knows which concrete adapter a provider name maps to."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._groq_client: GroqClient | None = None
        self._deepgram_client: DeepgramClient | None = None

    def _groq(self) -> GroqClient:
        if self._groq_client is None:
            self._groq_client = GroqClient(self._settings)
        return self._groq_client

    def _deepgram(self) -> DeepgramClient:
        if self._deepgram_client is None:
            self._deepgram_client = DeepgramClient(self._settings)
        return self._deepgram_client

    def speech_to_text(self) -> SpeechToTextProvider:
        name = self._settings.stt_provider
        if name == "groq":
            return GroqSpeechToTextProvider(self._groq(), self._settings)
        if name == "mock":
            return MockSpeechToTextProvider()
        raise ConfigError(f"Unknown STT_PROVIDER: {name!r}")

    def llm(self) -> LLMProvider:
        name = self._settings.llm_provider
        if name == "groq":
            return GroqLLMProvider(self._groq(), self._settings)
        if name == "mock":
            return MockLLMProvider()
        raise ConfigError(f"Unknown LLM_PROVIDER: {name!r}")

    def grammar(self) -> GrammarAnalysisProvider:
        name = self._settings.grammar_provider
        if name == "groq":
            return GroqGrammarAnalysisProvider(self._groq(), self._settings)
        if name == "mock":
            return MockGrammarAnalysisProvider()
        raise ConfigError(f"Unknown GRAMMAR_PROVIDER: {name!r}")

    def vocabulary(self) -> VocabularyAnalysisProvider:
        name = self._settings.vocabulary_provider
        if name == "groq":
            return GroqVocabularyAnalysisProvider(self._groq(), self._settings)
        if name == "mock":
            return MockVocabularyAnalysisProvider()
        raise ConfigError(f"Unknown VOCABULARY_PROVIDER: {name!r}")

    def _one_text_to_speech(self, name: str) -> TextToSpeechProvider:
        if name == "groq":
            return GroqTextToSpeechProvider(self._groq(), self._settings)
        if name == "deepgram":
            return DeepgramTextToSpeechProvider(self._deepgram(), self._settings)
        if name == "mock":
            return MockTextToSpeechProvider()
        raise ConfigError(f"Unknown TTS provider: {name!r}")

    def text_to_speech(self) -> TextToSpeechProvider:
        """Builds the primary provider, wrapped in a fallback chain when
        TTS_FALLBACK_PROVIDERS names any alternatives.

        A provider whose credentials are missing is skipped rather than
        allowed to break the chain, so an unconfigured fallback is harmless.
        """
        chain: list[TextToSpeechProvider] = []
        for index, name in enumerate(self._settings.tts_chain):
            try:
                chain.append(self._one_text_to_speech(name))
            except ConfigError:
                if index == 0:
                    raise
                continue

        if len(chain) == 1:
            return chain[0]
        return FallbackTextToSpeechProvider(chain)

    async def close(self) -> None:
        if self._groq_client is not None:
            await self._groq_client.close()
            self._groq_client = None
        if self._deepgram_client is not None:
            await self._deepgram_client.close()
            self._deepgram_client = None
