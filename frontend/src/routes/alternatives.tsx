import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { ArrowLeft, ArrowRight, Loader2, Waves } from "lucide-react";

import { ErrorBanner } from "@/components/ErrorBanner";
import {
  runEnglishAlternatives,
  summarizeError,
  type EnglishAlternativesAnalysis,
  type ErrorSummary,
} from "@/lib/api";
import { findSpokenLanguage, type SpokenLanguageCode } from "@/lib/languages";

export const Route = createFileRoute("/alternatives")({
  validateSearch: (
    search: Record<string, unknown>,
  ): { session?: string | undefined; lang?: SpokenLanguageCode | undefined } => ({
    session: typeof search["session"] === "string" ? (search["session"] as string) : undefined,
    lang: findSpokenLanguage(search["lang"])?.code,
  }),
  head: () => ({
    meta: [
      { title: "English alternatives | Lexa" },
      {
        name: "description",
        content:
          "The English for the phrases and harder words you reached for in your own language.",
      },
    ],
  }),
  component: Alternatives,
});

function Alternatives() {
  const { session, lang } = Route.useSearch();
  const language = findSpokenLanguage(lang);

  const [analysis, setAnalysis] = useState<EnglishAlternativesAnalysis | null>(null);
  const [error, setError] = useState<ErrorSummary | null>(null);

  useEffect(() => {
    if (!session) return;
    let cancelled = false;

    runEnglishAlternatives(session)
      .then((result) => {
        if (!cancelled) setAnalysis(result);
      })
      .catch((cause) => {
        if (!cancelled) setError(summarizeError(cause));
      });

    return () => {
      cancelled = true;
    };
  }, [session]);

  const name = language?.name ?? "your language";

  if (!session) {
    return (
      <Shell>
        <section className="relative mx-auto w-full max-w-4xl px-6 pb-16">
          <h1 className="mt-6 text-4xl sm:text-5xl">No conversation to look at</h1>
          <p className="mt-3 max-w-2xl text-muted-foreground">
            This page is built from a conversation you have had. Start one and end it with “End
            &amp; review”.
          </p>
          <Link
            to="/"
            className="mt-8 inline-block rounded-lg bg-primary px-6 py-3 text-sm font-medium text-primary-foreground"
          >
            Choose a language
          </Link>
        </section>
      </Shell>
    );
  }

  return (
    <Shell>
      <section className="relative mx-auto w-full max-w-4xl px-6 pb-16">
        <Link
          to="/"
          className="inline-flex items-center gap-2 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="size-4" /> Back home
        </Link>
        <h1 className="mt-6 text-4xl sm:text-5xl">Say it in English</h1>
        <p className="mt-3 max-w-2xl text-muted-foreground">
          The phrases and harder words you reached for in {name}, with the English you could use
          next time. Everyday words are left out; you will already know those.
        </p>

        {!analysis && !error && (
          <p className="mt-6 inline-flex items-center gap-2 rounded-full bg-secondary px-4 py-2 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" /> Finding the English for what you said…
          </p>
        )}
        {error && <ErrorBanner error={error} className="mt-6" />}

        {analysis && analysis.items.length > 0 && (
          <ol className="mt-8 space-y-3">
            {analysis.items.map((item) => (
              <li key={item.id} className="surface rounded-2xl p-5 sm:p-6">
                <div className="grid items-center gap-3 sm:grid-cols-[1fr_auto_1fr] sm:gap-6">
                  <p lang={analysis.spoken_language} className="text-xl leading-snug">
                    {item.original}
                  </p>
                  <ArrowRight className="hidden size-5 text-muted-foreground sm:block" />
                  <p className="text-xl leading-snug text-accent">{item.english}</p>
                </div>
                <div className="mt-3 flex flex-wrap items-baseline gap-x-3 gap-y-1">
                  <span className="rounded-full bg-secondary px-3 py-1 font-mono text-[11px] tracking-wide text-muted-foreground uppercase">
                    {item.kind}
                  </span>
                  {item.example && (
                    <p className="text-sm text-muted-foreground">“{item.example}”</p>
                  )}
                </div>
              </li>
            ))}
          </ol>
        )}

        {analysis && analysis.items.length === 0 && (
          <div className="surface mt-8 rounded-2xl p-6">
            <p className="text-sm leading-relaxed text-muted-foreground">
              {analysis.note || "Nothing stood out this time."}
            </p>
          </div>
        )}

        {analysis && (
          <div className="mt-6 space-y-2 text-xs leading-relaxed text-muted-foreground">
            {analysis.items.length > 0 && analysis.note && <p>{analysis.note}</p>}
            <p>
              These come from what the app heard, and speech recognition can mis-hear a word. If one
              is not what you meant, ignore it.
            </p>
          </div>
        )}

        <div className="surface glow mt-12 flex flex-col items-center gap-4 rounded-2xl p-10 text-center">
          <h2 className="text-3xl">Keep practising</h2>
          <p className="max-w-md text-sm text-muted-foreground">
            The more you say, the more there is to learn from. Another conversation, or a different
            language.
          </p>
          <div className="flex flex-wrap justify-center gap-3">
            {language && (
              <Link
                to="/conversation"
                search={{ lang: language.code }}
                className="rounded-lg bg-primary px-6 py-3 text-sm font-medium text-primary-foreground transition-transform hover:-translate-y-0.5"
              >
                Another conversation in {language.name}
              </Link>
            )}
            <Link
              to="/"
              className="rounded-lg border border-border px-6 py-3 text-sm font-medium transition-colors hover:bg-secondary"
            >
              Choose a language
            </Link>
          </div>
        </div>
      </section>
    </Shell>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <main className="relative min-h-screen overflow-hidden">
      <div className="halo pointer-events-none absolute inset-x-0 -top-52 h-[620px]" />
      <header className="relative mx-auto flex w-full max-w-4xl items-center justify-between px-6 py-6">
        <Link to="/" className="flex items-center gap-2">
          <Waves className="size-5 text-accent" />
          <span className="tracking-tight">Lexa</span>
        </Link>
      </header>
      {children}
    </main>
  );
}
