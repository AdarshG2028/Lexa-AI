from app.core.errors import FeatureDisabledError
from app.models import PhonemeSubstitution, ProviderCheck, PronunciationSample


class DisabledPronunciationProvider:
    """Stands in when pronunciation analysis is switched off.

    Declining is the honest behaviour for a deployment that cannot run the
    phoneme model. The mock would answer with plausible findings it invented
    from spelling, and a learner cannot tell those from real ones.
    """

    name = "off"

    async def analyze(
        self, samples: list[PronunciationSample]
    ) -> list[PhonemeSubstitution]:
        raise FeatureDisabledError(
            "Pronunciation analysis is not enabled on this server."
        )

    async def check(self) -> ProviderCheck:
        return ProviderCheck(provider=self.name, note="disabled")
