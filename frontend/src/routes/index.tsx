import { createFileRoute, Link } from "@tanstack/react-router";
import {
  ArrowRight,
  ArrowUpRight,
  AudioLines,
  FileVideo,
  Mic,
  SpellCheck,
  Waves,
} from "lucide-react";

import { SPOKEN_LANGUAGES } from "@/lib/languages";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Lexa — Practice speaking with an AI that listens" },
      {
        name: "description",
        content:
          "Have a real voice conversation with Lexa, then get grammar corrections and pronunciation coaching from the transcript.",
      },
      { property: "og:title", content: "Lexa — Practice speaking with an AI that listens" },
      {
        property: "og:description",
        content: "Voice conversations with instant grammar and phonetic feedback.",
      },
    ],
  }),
  component: Landing,
});

const steps = [
  {
    n: "01",
    icon: Mic,
    title: "Speak freely",
    body: "Start a call and talk about anything. Lexa listens with speech-to-text and answers out loud.",
  },
  {
    n: "02",
    icon: SpellCheck,
    title: "Grammar review",
    body: "Every sentence you said is re-read line by line, with cleaner alternatives and the rule behind them.",
  },
  {
    n: "03",
    icon: AudioLines,
    title: "Phonetic coaching",
    body: "Tricky sounds are flagged with IPA, a model pronunciation to replay, and drills to repeat.",
  },
];

const preview = [
  { label: "Fluency", value: "82" },
  { label: "Grammar", value: "71" },
  { label: "Vocabulary", value: "88" },
];

function Landing() {
  return (
    <main className="relative min-h-screen overflow-hidden">
      <div className="halo pointer-events-none absolute inset-x-0 -top-40 h-[720px]" />

      <header className="relative mx-auto flex w-full max-w-6xl items-center justify-between px-6 py-7">
        <Link to="/" className="flex items-center gap-2">
          <Waves className="size-5 text-accent" />
          <span className="text-lg tracking-tight">Lexa</span>
        </Link>
        <nav className="flex items-center gap-3 text-sm">
          <Link
            to="/insights"
            className="rounded-lg px-3 py-2 text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
          >
            Sample report
          </Link>
          <Link
            to="/video"
            className="rounded-lg px-3 py-2 text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
          >
            Upload video
          </Link>
          <Link
            to="/conversation"
            className="rounded-lg bg-primary px-4 py-2 font-medium text-primary-foreground transition-opacity hover:opacity-90"
          >
            Start talking
          </Link>
        </nav>
      </header>

      <section className="relative mx-auto grid w-full max-w-6xl gap-16 px-6 pt-14 pb-24 lg:grid-cols-[1.1fr_0.9fr] lg:items-center">
        <div>
          <span className="inline-flex items-center gap-2 rounded-full border border-border px-3 py-1 font-mono text-[11px] tracking-wide text-muted-foreground uppercase">
            <span className="size-1.5 rounded-full bg-accent" />
            Voice-first language coach
          </span>
          <h1 className="mt-6 text-5xl leading-[1.05] sm:text-6xl lg:text-7xl">
            Talk it out.
            <br />
            Then see <span className="text-accent">what to fix.</span>
          </h1>
          <p className="mt-6 max-w-xl text-lg leading-relaxed text-muted-foreground">
            Lexa is an AI you actually speak with. When you hang up, you get a report of the grammar
            you slipped on and the sounds that gave you away — with audio you can replay.
          </p>
          <div className="mt-9 flex flex-wrap items-center gap-3">
            <Link
              to="/conversation"
              className="glow inline-flex items-center gap-2 rounded-lg bg-primary px-6 py-3 font-medium text-primary-foreground transition-transform hover:-translate-y-0.5"
            >
              <Mic className="size-4" /> Start a conversation
            </Link>
            <Link
              to="/insights"
              className="inline-flex items-center gap-2 rounded-lg border border-border px-6 py-3 font-medium transition-colors hover:bg-secondary"
            >
              See a sample report <ArrowRight className="size-4" />
            </Link>
          </div>

          <div className="mt-10 flex flex-wrap items-center gap-x-8 gap-y-3 border-t border-border pt-6">
            {preview.map((p) => (
              <div key={p.label} className="flex items-baseline gap-2">
                <span className="font-mono text-2xl tabular-nums text-foreground">{p.value}</span>
                <span className="font-mono text-[11px] tracking-wide text-muted-foreground uppercase">
                  {p.label}
                </span>
              </div>
            ))}
            <span className="font-mono text-[11px] tracking-wide text-muted-foreground uppercase">
              sample scores, from a real report
            </span>
          </div>
        </div>

        <div className="surface glow relative overflow-hidden rounded-2xl p-8">
          <div className="waveform-static absolute inset-x-0 top-0 h-10 opacity-70" />
          <div className="flex items-center gap-2 font-mono text-xs tracking-wide text-muted-foreground uppercase">
            <span className="relative inline-flex size-2">
              <span className="pulse-ring absolute inset-0 rounded-full border border-accent/60" />
              <span className="size-2 rounded-full bg-accent" />
            </span>
            Live session · 04:12
          </div>
          <div className="mt-6 space-y-4">
            <Bubble side="them" text="So, where did you travel last summer?" />
            <Bubble side="me" text="I go to Kerala with my cousins, it was very peaceful." />
            <Bubble side="them" text="Nice — what did you like most about it?" />
          </div>
          <div className="mt-7 rounded-xl border border-accent/30 bg-accent/[0.06] p-4">
            <p className="font-mono text-[11px] tracking-wide text-accent uppercase">
              Caught for your report
            </p>
            <p className="mt-2 text-sm">
              <span className="line-through opacity-60">I go to Kerala</span> →{" "}
              <span className="text-accent">I went to Kerala</span>{" "}
              <span className="text-muted-foreground">· past simple</span>
            </p>
            <p className="mt-1 font-mono text-xs text-muted-foreground">
              "peaceful" — /ˈpiːs.fəl/, hold the long ee.
            </p>
          </div>
        </div>
      </section>

      <section className="relative mx-auto w-full max-w-6xl px-6 pb-28">
        <div className="flex items-baseline justify-between gap-4">
          <h2 className="text-3xl sm:text-4xl">How a session works</h2>
          <span className="hidden font-mono text-xs tracking-wide text-muted-foreground uppercase sm:inline">
            three steps, one conversation
          </span>
        </div>
        <div className="mt-10 grid gap-px overflow-hidden rounded-2xl border border-border bg-border md:grid-cols-3">
          {steps.map((s) => (
            <article
              key={s.title}
              className="surface flex flex-col gap-5 rounded-none border-0 p-7"
            >
              <div className="flex items-center justify-between">
                <s.icon className="size-6 text-accent" />
                <span className="font-mono text-xs text-muted-foreground">{s.n}</span>
              </div>
              <div>
                <h3 className="text-2xl">{s.title}</h3>
                <p className="mt-3 text-sm leading-relaxed text-muted-foreground">{s.body}</p>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="relative mx-auto w-full max-w-6xl px-6 pb-28">
        <div className="surface flex flex-col items-start justify-between gap-6 rounded-2xl p-8 sm:flex-row sm:items-center sm:p-10">
          <div className="flex items-start gap-4">
            <div className="surface flex size-12 shrink-0 items-center justify-center rounded-xl">
              <FileVideo className="size-6 text-accent" />
            </div>
            <div>
              <span className="font-mono text-[11px] tracking-wide text-muted-foreground uppercase">
                Already recorded?
              </span>
              <h2 className="mt-2 text-3xl">Upload a video instead</h2>
              <p className="mt-2 max-w-xl text-sm leading-relaxed text-muted-foreground">
                Have an English clip under five minutes? Upload it and get the same grammar, word
                choice and fluency report — no call needed.
              </p>
            </div>
          </div>
          <Link
            to="/video"
            className="inline-flex shrink-0 items-center gap-2 rounded-lg border border-border px-6 py-3 font-medium transition-colors hover:bg-secondary"
          >
            Upload a video <ArrowRight className="size-4" />
          </Link>
        </div>
      </section>

      <section className="relative mx-auto w-full max-w-6xl px-6 pb-28">
        <div className="surface rounded-2xl p-8 sm:p-10">
          <div className="grid gap-8 lg:grid-cols-[1fr_1.1fr] lg:items-center">
            <div>
              <span className="font-mono text-[11px] tracking-wide text-muted-foreground uppercase">
                Not comfortable in English yet?
              </span>
              <h2 className="mt-3 text-3xl sm:text-4xl">Start in your own language</h2>
              <p className="mt-4 max-w-md text-sm leading-relaxed text-muted-foreground">
                Talk the way you normally would. Lexa answers in simple English, and when you finish
                you get the English for the everyday words and phrases you reached for.
              </p>
            </div>
            <ul className="grid grid-cols-2 gap-3">
              {SPOKEN_LANGUAGES.map((language) => (
                <li key={language.code}>
                  <Link
                    to="/conversation"
                    search={{ lang: language.code }}
                    className="group flex h-full flex-col gap-1 rounded-xl border border-border px-5 py-4 transition-colors hover:bg-secondary"
                  >
                    <span lang={language.code} className="text-2xl leading-tight">
                      {language.nativeName}
                    </span>
                    <span className="flex items-center justify-between font-mono text-xs tracking-wide text-muted-foreground uppercase">
                      {language.name}
                      <ArrowRight className="size-3.5 transition-transform group-hover:translate-x-0.5" />
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      <footer className="relative border-t border-border">
        <div className="mx-auto flex w-full max-w-6xl flex-col gap-2 px-6 py-8 text-sm text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
          <span className="font-mono text-xs tracking-wide uppercase">
            Lexa · speak, stumble, improve.
          </span>
          <Link
            to="/conversation"
            className="inline-flex items-center gap-1 transition-colors hover:text-foreground"
          >
            Start talking <ArrowUpRight className="size-3.5" />
          </Link>
        </div>
      </footer>
    </main>
  );
}

function Bubble({ side, text }: { side: "me" | "them"; text: string }) {
  const me = side === "me";
  return (
    <div className={me ? "flex justify-end" : "flex justify-start"}>
      <p
        className={
          me
            ? "max-w-[85%] rounded-xl rounded-br-sm bg-secondary px-4 py-3 text-sm"
            : "max-w-[85%] rounded-xl rounded-bl-sm border border-border px-4 py-3 text-sm text-muted-foreground"
        }
      >
        {text}
      </p>
    </div>
  );
}
