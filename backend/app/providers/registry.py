import logging

from app.config import Settings
from app.core.errors import ConfigError
from app.providers.base import (
    EnglishAlternativesProvider,
    GrammarAnalysisProvider,
    LLMProvider,
    PronunciationAnalysisProvider,
    SpeechToTextProvider,
    TextToSpeechProvider,
    VocabularyAnalysisProvider,
)
from app.providers.deepgram.client import DeepgramClient
from app.providers.deepgram.tts import DeepgramTextToSpeechProvider
from app.providers.fallback import FallbackTextToSpeechProvider
from app.providers.groq.alternatives import GroqEnglishAlternativesProvider
from app.providers.groq.client import GroqClient
from app.providers.groq.grammar import GroqGrammarAnalysisProvider
from app.providers.groq.llm import GroqLLMProvider
from app.providers.groq.stt import GroqSpeechToTextProvider
from app.providers.groq.tts import GroqTextToSpeechProvider
from app.providers.groq.vocabulary import GroqVocabularyAnalysisProvider
from app.providers.mock.alternatives import MockEnglishAlternativesProvider
from app.providers.mock.grammar import MockGrammarAnalysisProvider
from app.providers.mock.llm import MockLLMProvider
from app.providers.disabled import DisabledPronunciationProvider
from app.providers.mock.pronunciation import MockPronunciationAnalysisProvider
from app.providers.mock.stt import MockSpeechToTextProvider
from app.providers.mock.tts import MockTextToSpeechProvider
from app.providers.mock.vocabulary import MockVocabularyAnalysisProvider
from app.providers.routing import LanguageRoutingSpeechToTextProvider
from app.providers.sarvam.client import SarvamClient
from app.providers.sarvam.stt import SarvamSpeechToTextProvider

logger = logging.getLogger(__name__)


class ProviderRegistry:
    """Builds the configured provider implementations. This is the only place
    that knows which concrete adapter a provider name maps to."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._groq_client: GroqClient | None = None
        self._deepgram_client: DeepgramClient | None = None
        self._sarvam_client: SarvamClient | None = None
        # Held across requests: the weights cost seconds to load.
        self._pronunciation = None

    def _groq(self) -> GroqClient:
        if self._groq_client is None:
            self._groq_client = GroqClient(self._settings)
        return self._groq_client

    def _deepgram(self) -> DeepgramClient:
        if self._deepgram_client is None:
            self._deepgram_client = DeepgramClient(self._settings)
        return self._deepgram_client

    def _sarvam(self) -> SarvamClient:
        if self._sarvam_client is None:
            self._sarvam_client = SarvamClient(self._settings)
        return self._sarvam_client

    def _default_speech_to_text(self) -> SpeechToTextProvider:
        name = self._settings.stt_provider
        if name == "groq":
            return GroqSpeechToTextProvider(self._groq(), self._settings)
        if name == "mock":
            return MockSpeechToTextProvider()
        raise ConfigError(f"Unknown STT_PROVIDER: {name!r}")

    def speech_to_text(self) -> SpeechToTextProvider:
        """The default STT provider, with Sarvam serving the languages it was
        configured for.

        Sarvam is only wired in when a key is present. A missing key must not
        break conversations in Kannada, Tamil or Telugu: they keep working on
        the default provider, and the reason is logged at startup.
        """
        default = self._default_speech_to_text()
        codes = self._settings.sarvam_languages

        if self._settings.stt_provider == "mock" or not codes:
            return default

        if not self._settings.sarvam_api_key:
            logger.debug(
                "SARVAM_STT_LANGUAGES lists %s but SARVAM_API_KEY is empty; "
                "those languages will use %s.",
                ",".join(codes), self._settings.stt_provider,
            )
            return default

        sarvam = SarvamSpeechToTextProvider(self._sarvam(), self._settings)
        return LanguageRoutingSpeechToTextProvider(
            default, {code: sarvam for code in codes}
        )

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

    def alternatives(self) -> EnglishAlternativesProvider:
        name = self._settings.alternatives_provider
        if name == "groq":
            return GroqEnglishAlternativesProvider(self._groq(), self._settings)
        if name == "mock":
            return MockEnglishAlternativesProvider()
        raise ConfigError(f"Unknown ALTERNATIVES_PROVIDER: {name!r}")

    def pronunciation(self) -> PronunciationAnalysisProvider:
        """The wav2vec2 adapter is imported lazily so that a deployment
        without the pronunciation stack installed can still start."""
        name = self._settings.pronunciation_provider
        if name == "wav2vec2":
            from app.providers.wav2vec2.pronunciation import (
                Wav2Vec2PronunciationProvider,
            )

            if self._pronunciation is None:
                self._pronunciation = Wav2Vec2PronunciationProvider(self._settings)
            return self._pronunciation
        if name == "mock":
            return MockPronunciationAnalysisProvider()
        if name == "off":
            return DisabledPronunciationProvider()
        raise ConfigError(f"Unknown PRONUNCIATION_PROVIDER: {name!r}")

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
        if self._sarvam_client is not None:
            await self._sarvam_client.close()
            self._sarvam_client = None
