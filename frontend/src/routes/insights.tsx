import { createFileRoute, Link } from "@tanstack/react-router";
import { useCallback, useEffect, useState } from "react";
import {
  AudioLines,
  ArrowLeft,
  Check,
  Gauge,
  Loader2,
  SpellCheck,
  Sparkles,
  Waves,
} from "lucide-react";

import {
  ApiError,
  PRONUNCIATION_ENABLED,
  runFluency,
  runGrammar,
  runPronunciation,
  runVocabulary,
  type FluencyAnalysis,
  type GrammarAnalysis,
  type PronunciationAnalysis,
  type VocabularyAnalysis,
} from "@/lib/api";

export const Route = createFileRoute("/insights")({
  validateSearch: (search: Record<string, unknown>): { session?: string | undefined } => ({
    session: typeof search["session"] === "string" ? (search["session"] as string) : undefined,
  }),
  head: () => ({
    meta: [
      { title: "Session report — grammar, vocabulary & fluency | Lexa" },
      {
        name: "description",
        content:
          "Your Lexa session report: corrected sentences with the grammar rule behind each fix, plus phonetic drills for the sounds you missed.",
      },
      { property: "og:title", content: "Session report — grammar, vocabulary & fluency | Lexa" },
      {
        property: "og:description",
        content: "Grammar corrections and phonetic coaching from your latest voice session.",
      },
    ],
  }),
  component: Insights,
});

function Insights() {
  const { session } = Route.useSearch();

  const [grammar, setGrammar] = useState<GrammarAnalysis | null>(null);
  const [vocabulary, setVocabulary] = useState<VocabularyAnalysis | null>(null);
  const [fluency, setFluency] = useState<FluencyAnalysis | null>(null);
  const [pronunciation, setPronunciation] = useState<PronunciationAnalysis | null>(null);

  const [progress, setProgress] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pronRunning, setPronRunning] = useState(false);
  const [pronError, setPronError] = useState<string | null>(null);

  // Run in sequence rather than in parallel: each one is a provider call, and
  // a failure part-way through should leave the finished sections on screen.
  useEffect(() => {
    if (!session) return;
    let cancelled = false;

    (async () => {
      try {
        setProgress("Measuring fluency from your speech timings…");
        const fluencyResult = await runFluency(session);
        if (cancelled) return;
        setFluency(fluencyResult);

        setProgress("Checking grammar…");
        const grammarResult = await runGrammar(session);
        if (cancelled) return;
        setGrammar(grammarResult);

        setProgress("Reviewing word choice…");
        const vocabularyResult = await runVocabulary(session);
        if (cancelled) return;
        setVocabulary(vocabularyResult);
      } catch (cause) {
        if (!cancelled) setError(describe(cause));
      } finally {
        if (!cancelled) setProgress(null);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [session]);

  const analysePronunciation = useCallback(async () => {
    if (!session) return;
    setPronRunning(true);
    setPronError(null);
    try {
      setPronunciation(await runPronunciation(session));
    } catch (cause) {
      setPronError(describe(cause));
    } finally {
      setPronRunning(false);
    }
  }, [session]);

  if (!session) {
    return (
      <Shell>
        <section className="relative mx-auto w-full max-w-5xl px-6 pb-16">
          <h1 className="mt-6 text-4xl sm:text-5xl">No session to report on</h1>
          <p className="mt-3 max-w-2xl text-muted-foreground">
            Reports are generated from a conversation you have had. Start one and end it with “End
            &amp; review”.
          </p>
          <Link
            to="/conversation"
            className="mt-8 inline-block rounded-full bg-primary px-6 py-3 text-sm font-medium text-primary-foreground"
          >
            Start a conversation
          </Link>
        </section>
      </Shell>
    );
  }

  return (
    <Shell>
      <section className="relative mx-auto w-full max-w-5xl px-6 pb-16">
        <Link
          to="/"
          className="inline-flex items-center gap-2 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="size-4" /> Back home
        </Link>
        <h1 className="mt-6 text-4xl sm:text-5xl">Your session report</h1>
        <p className="mt-3 max-w-2xl text-muted-foreground">
          {fluency
            ? `${fluency.timed_words} words spoken over ${Math.round(fluency.analyzed_seconds)} seconds of speech.`
            : "Reading your conversation back…"}
        </p>

        {progress && (
          <p className="mt-4 inline-flex items-center gap-2 rounded-full bg-secondary px-4 py-2 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" /> {progress}
          </p>
        )}
        {error && (
          <p className="mt-4 rounded-2xl border border-destructive/40 bg-destructive/10 px-5 py-3 text-sm text-destructive">
            {error}
          </p>
        )}

        <div
          className={`mt-8 grid gap-4 sm:grid-cols-2 ${PRONUNCIATION_ENABLED ? "lg:grid-cols-4" : "lg:grid-cols-3"}`}
        >
          <Stat
            label="Fluency"
            value={fluency?.fluency_score ?? null}
            caption={
              fluency
                ? `${Math.round(fluency.speaking_rate_wpm)} wpm · ${fluency.pause_count} pauses`
                : "…"
            }
          />
          <Stat
            label="Grammar"
            value={grammar?.grammar_score ?? null}
            caption={grammar ? `${grammar.issue_count} patterns to fix` : "…"}
          />
          <Stat
            label="Vocabulary"
            value={vocabulary?.vocabulary_score ?? null}
            caption={
              vocabulary
                ? `${vocabulary.unique_words} unique words · ${vocabulary.lexical_diversity.toFixed(2)} diversity`
                : "…"
            }
          />
          {PRONUNCIATION_ENABLED && (
            <Stat
              label="Pronunciation"
              value={pronunciation?.pronunciation_score ?? null}
              caption={
                pronunciation ? `${pronunciation.issue_count} sounds flagged` : "Not run yet"
              }
            />
          )}
        </div>
      </section>

      {grammar && (
        <section className="relative mx-auto w-full max-w-5xl px-6 pb-16">
          <div className="flex items-center gap-3">
            <SpellCheck className="size-5 text-primary" />
            <h2 className="text-3xl">Grammar improvements</h2>
          </div>
          {grammar.issues.length === 0 ? (
            <p className="mt-6 text-muted-foreground">
              No grammar issues were found in what you said.
            </p>
          ) : (
            <div className="mt-6 space-y-4">
              {grammar.issues.map((issue) => (
                <article key={issue.id} className="surface rounded-3xl p-6">
                  <span className="rounded-full bg-secondary px-3 py-1 text-xs text-muted-foreground">
                    {readable(issue.category)}
                  </span>
                  <p className="mt-4 text-sm text-muted-foreground line-through decoration-destructive/60">
                    {issue.original}
                  </p>
                  <p className="mt-2 flex items-start gap-2 text-lg leading-snug">
                    <Check className="mt-1.5 size-4 shrink-0 text-primary" />
                    <span>{issue.corrected}</span>
                  </p>
                  <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                    {issue.explanation}
                  </p>
                </article>
              ))}
            </div>
          )}
        </section>
      )}

      {vocabulary && (
        <section className="relative mx-auto w-full max-w-5xl px-6 pb-16">
          <div className="flex items-center gap-3">
            <Sparkles className="size-5 text-accent" />
            <h2 className="text-3xl">Word choice</h2>
          </div>
          {vocabulary.issues.length === 0 ? (
            <p className="mt-6 text-muted-foreground">
              Nothing repetitive or overly basic stood out.
            </p>
          ) : (
            <div className="mt-6 grid gap-4 md:grid-cols-2">
              {vocabulary.issues.map((issue) => (
                <article key={issue.id} className="surface rounded-3xl p-6">
                  <div className="flex items-baseline justify-between gap-3">
                    <h3 className="text-2xl">{issue.text}</h3>
                    <span className="shrink-0 text-xs text-muted-foreground">
                      ×{issue.occurrences}
                    </span>
                  </div>
                  <span className="mt-3 inline-block rounded-full bg-secondary px-3 py-1 text-xs text-muted-foreground">
                    {readable(issue.type)}
                  </span>
                  <p className="mt-4 text-sm leading-relaxed text-muted-foreground">
                    “{issue.example}”
                  </p>
                  {issue.suggestions.length > 0 && (
                    <p className="mt-4 rounded-2xl bg-secondary px-4 py-3 text-sm">
                      Try: {issue.suggestions.join(" · ")}
                    </p>
                  )}
                  {issue.explanation && (
                    <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                      {issue.explanation}
                    </p>
                  )}
                </article>
              ))}
            </div>
          )}
        </section>
      )}

      {fluency && (
        <section className="relative mx-auto w-full max-w-5xl px-6 pb-16">
          <div className="flex items-center gap-3">
            <Gauge className="size-5 text-primary" />
            <h2 className="text-3xl">How you spoke</h2>
          </div>
          {fluency.note && <p className="mt-4 text-sm text-muted-foreground">{fluency.note}</p>}
          <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Metric label="Speaking rate" value={`${Math.round(fluency.speaking_rate_wpm)} wpm`} />
            <Metric
              label="Articulation rate"
              value={`${Math.round(fluency.articulation_rate_wpm)} wpm`}
            />
            <Metric
              label="Pauses"
              value={`${fluency.pause_count} (${fluency.long_pause_count} long)`}
            />
            <Metric label="Fillers" value={String(fluency.filler_count)} />
          </div>
          {fluency.findings.length > 0 && (
            <div className="mt-6 space-y-3">
              {fluency.findings.map((finding) => (
                <div
                  key={finding.id}
                  className="surface flex flex-wrap items-baseline gap-3 rounded-2xl px-5 py-4 text-sm"
                >
                  <span className="rounded-full bg-secondary px-3 py-1 text-xs text-muted-foreground">
                    {readable(finding.type)}
                  </span>
                  <span className="font-medium">{finding.text}</span>
                  <span className="text-muted-foreground">×{finding.occurrences}</span>
                  {finding.detail && (
                    <span className="text-muted-foreground">{finding.detail}</span>
                  )}
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      <section className="relative mx-auto w-full max-w-5xl px-6 pb-24">
        {PRONUNCIATION_ENABLED && (
          <>
            <div className="flex items-center gap-3">
              <AudioLines className="size-5 text-accent" />
              <h2 className="text-3xl">Phonetic improvements</h2>
            </div>

            {!pronunciation && (
              <div className="surface mt-6 rounded-3xl p-8">
                <p className="text-sm leading-relaxed text-muted-foreground">
                  Pronunciation is measured by running a phoneme model over your recorded audio. It
                  is by far the slowest step — expect 60–100 seconds on the first run while the
                  model loads, and roughly 1.5× the length of your speech after that. Everything
                  above is already complete, so run this only when you want it.
                </p>
                <button
                  onClick={() => void analysePronunciation()}
                  disabled={pronRunning}
                  className="mt-6 inline-flex items-center gap-2 rounded-full bg-primary px-6 py-3 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-60"
                >
                  {pronRunning ? (
                    <>
                      <Loader2 className="size-4 animate-spin" /> Listening to your phonemes…
                    </>
                  ) : (
                    <>
                      <AudioLines className="size-4" /> Analyse pronunciation
                    </>
                  )}
                </button>
                {pronError && (
                  <p className="mt-4 rounded-2xl border border-destructive/40 bg-destructive/10 px-5 py-3 text-sm text-destructive">
                    {pronError}
                  </p>
                )}
              </div>
            )}

            {pronunciation && (
              <>
                {pronunciation.note && (
                  <p className="mt-4 max-w-3xl text-sm leading-relaxed text-muted-foreground">
                    {pronunciation.note}
                  </p>
                )}
                {pronunciation.issues.length > 0 && (
                  <div className="mt-6 grid gap-4 md:grid-cols-3">
                    {pronunciation.issues.map((issue) => (
                      <article key={issue.id} className="surface flex flex-col rounded-3xl p-6">
                        <div className="flex items-baseline justify-between">
                          <h3 className="font-mono text-2xl">/{issue.expected_phoneme}/</h3>
                          <span className="font-mono text-xs text-accent">
                            heard /{issue.detected_phoneme}/
                          </span>
                        </div>
                        <div className="mt-4 h-1.5 w-full rounded-full bg-secondary">
                          <div
                            className="h-full rounded-full bg-accent"
                            style={{ width: `${Math.round(issue.confidence * 100)}%` }}
                          />
                        </div>
                        <p className="mt-2 text-xs text-muted-foreground">
                          {issue.occurrences} occurrences · {Math.round(issue.confidence * 100)}%
                          confidence
                        </p>
                        <p className="mt-4 flex-1 text-sm leading-relaxed text-muted-foreground">
                          Heard in: {issue.affected_words.join(", ")}
                        </p>
                        {issue.practice_words.length > 0 && (
                          <p className="mt-4 rounded-2xl bg-secondary px-4 py-3 text-sm">
                            {issue.practice_words.slice(0, 5).join(" · ")}
                          </p>
                        )}
                      </article>
                    ))}
                  </div>
                )}
              </>
            )}
          </>
        )}

        <div className="surface glow mt-10 flex flex-col items-center gap-4 rounded-3xl p-10 text-center">
          <h2 className="text-3xl">Ready for round two?</h2>
          <p className="max-w-md text-sm text-muted-foreground">
            Another conversation gives the analysis more to work with — short sessions rarely
            contain enough evidence to be sure about a pattern.
          </p>
          <Link
            to="/conversation"
            className="rounded-full bg-primary px-6 py-3 text-sm font-medium text-primary-foreground transition-transform hover:-translate-y-0.5"
          >
            Start another conversation
          </Link>
        </div>
      </section>
    </Shell>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <main className="relative min-h-screen overflow-hidden">
      <div className="halo pointer-events-none absolute inset-x-0 -top-52 h-[620px]" />
      <header className="relative mx-auto flex w-full max-w-5xl items-center justify-between px-6 py-6">
        <Link to="/" className="flex items-center gap-2">
          <Waves className="size-5 text-primary" />
          <span className="tracking-tight">Lexa</span>
        </Link>
        <Link
          to="/conversation"
          className="rounded-full border border-border px-4 py-2 text-sm transition-colors hover:bg-secondary"
        >
          New session
        </Link>
      </header>
      {children}
    </main>
  );
}

function Stat({ label, value, caption }: { label: string; value: number | null; caption: string }) {
  return (
    <div className="surface rounded-3xl p-6">
      <p className="text-xs tracking-wide text-muted-foreground uppercase">{label}</p>
      <p className="mt-2 font-display text-4xl text-primary">{value ?? "—"}</p>
      <p className="mt-1 text-sm text-muted-foreground">{caption}</p>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="surface rounded-2xl px-5 py-4">
      <p className="text-xs tracking-wide text-muted-foreground uppercase">{label}</p>
      <p className="mt-1 text-lg">{value}</p>
    </div>
  );
}

function readable(value: string): string {
  return value.replace(/_/g, " ");
}

function describe(cause: unknown): string {
  if (cause instanceof ApiError) return cause.message;
  return "The analysis could not be completed. Check the backend logs.";
}
