/**
 * The languages a learner can speak instead of English.
 *
 * Mirrors `backend/app/languages.py`. It lives here as well, rather than being
 * fetched, because the landing page offers these before any request to the
 * backend has been made - and a free-tier backend can take most of a minute to
 * wake, which is not a delay a language picker should inherit. The backend
 * validates the code, so a drift between the two fails loudly rather than
 * silently.
 */
export const SPOKEN_LANGUAGES = [
  { code: "hi", name: "Hindi", nativeName: "हिन्दी" },
  { code: "kn", name: "Kannada", nativeName: "ಕನ್ನಡ" },
  { code: "ta", name: "Tamil", nativeName: "தமிழ்" },
  { code: "te", name: "Telugu", nativeName: "తెలుగు" },
] as const;

export type SpokenLanguageCode = (typeof SPOKEN_LANGUAGES)[number]["code"];

export type SpokenLanguage = (typeof SPOKEN_LANGUAGES)[number];

export function findSpokenLanguage(code: unknown): SpokenLanguage | undefined {
  return SPOKEN_LANGUAGES.find((language) => language.code === code);
}
