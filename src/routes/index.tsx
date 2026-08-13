import { createFileRoute, Link } from "@tanstack/react-router";
import { Mic, Waves, SpellCheck, AudioLines, ArrowRight } from "lucide-react";

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
    icon: Mic,
    title: "Speak freely",
    body: "Start a call and talk about anything. Lexa listens with speech-to-text and answers out loud.",
  },
  {
    icon: SpellCheck,
    title: "Grammar review",
    body: "Every sentence you said is re-read line by line, with cleaner alternatives and the rule behind them.",
  },
  {
    icon: AudioLines,
    title: "Phonetic coaching",
    body: "Tricky sounds are flagged with IPA, a model pronunciation to replay, and drills to repeat.",
  },
];

function Landing() {
  return (
    <main className="relative min-h-screen overflow-hidden">
      <div className="halo pointer-events-none absolute inset-x-0 -top-40 h-[720px]" />

      <header className="relative mx-auto flex w-full max-w-6xl items-center justify-between px-6 py-7">
        <Link to="/" className="flex items-center gap-2">
          <Waves className="size-5 text-primary" />
          <span className="text-lg tracking-tight">Lexa</span>
        </Link>
        <nav className="flex items-center gap-6 text-sm text-muted-foreground">
          <Link to="/insights" className="transition-colors hover:text-foreground">
            Sample report
          </Link>
          <Link
            to="/conversation"
            className="rounded-full bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90"
          >
            Start talking
          </Link>
        </nav>
      </header>

      <section className="relative mx-auto grid w-full max-w-6xl gap-16 px-6 pt-14 pb-24 lg:grid-cols-[1.1fr_0.9fr] lg:items-center">
        <div>
          <span className="inline-flex items-center gap-2 rounded-full border border-border px-3 py-1 text-xs tracking-wide text-muted-foreground uppercase">
            Voice-first language coach
          </span>
          <h1 className="mt-6 text-5xl leading-[1.05] sm:text-6xl lg:text-7xl">
            Talk it out.
            <br />
            <em className="text-primary">Then see</em> what to fix.
          </h1>
          <p className="mt-6 max-w-xl text-lg leading-relaxed text-muted-foreground">
            Lexa is an AI you actually speak with. When you hang up, you get a report of the grammar
            you slipped on and the sounds that gave you away — with audio you can replay.
          </p>
          <div className="mt-9 flex flex-wrap items-center gap-3">
            <Link
              to="/conversation"
              className="glow inline-flex items-center gap-2 rounded-full bg-primary px-6 py-3 font-medium text-primary-foreground transition-transform hover:-translate-y-0.5"
            >
              <Mic className="size-4" /> Start a conversation
            </Link>
            <Link
              to="/insights"
              className="inline-flex items-center gap-2 rounded-full border border-border px-6 py-3 font-medium transition-colors hover:bg-secondary"
            >
              See a sample report <ArrowRight className="size-4" />
            </Link>
          </div>
          <p className="mt-5 text-sm text-muted-foreground">
            No script. No grading anxiety. Just a five-minute chat.
          </p>
        </div>

        <div className="surface glow relative rounded-3xl p-8">
          <div className="flex items-center gap-3 text-sm text-muted-foreground">
            <span className="size-2 rounded-full bg-accent" /> Live session · 04:12
          </div>
          <div className="mt-6 space-y-4">
            <Bubble side="them" text="So, where did you travel last summer?" />
            <Bubble side="me" text="I go to Kerala with my cousins, it was very peaceful." />
            <Bubble side="them" text="Nice — what did you like most about it?" />
          </div>
          <div className="mt-7 rounded-2xl border border-primary/30 bg-primary/10 p-4">
            <p className="text-xs tracking-wide text-primary uppercase">Caught for your report</p>
            <p className="mt-2 text-sm">
              <span className="line-through opacity-60">I go to Kerala</span> →{" "}
              <span className="text-primary">I went to Kerala</span> · past simple
            </p>
            <p className="mt-1 text-sm text-muted-foreground">
              “peaceful” — /ˈpiːs.fəl/, hold the long ee.
            </p>
          </div>
        </div>
      </section>

      <section className="relative mx-auto w-full max-w-6xl px-6 pb-28">
        <h2 className="text-3xl sm:text-4xl">How a session works</h2>
        <div className="mt-10 grid gap-5 md:grid-cols-3">
          {steps.map((s) => (
            <article key={s.title} className="surface rounded-3xl p-7">
              <s.icon className="size-6 text-primary" />
              <h3 className="mt-5 text-2xl">{s.title}</h3>
              <p className="mt-3 text-sm leading-relaxed text-muted-foreground">{s.body}</p>
            </article>
          ))}
        </div>
      </section>

      <footer className="relative border-t border-border">
        <div className="mx-auto flex w-full max-w-6xl flex-col gap-2 px-6 py-8 text-sm text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
          <span>Lexa · speak, stumble, improve.</span>
          <Link to="/conversation" className="transition-colors hover:text-foreground">
            Start talking →
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
            ? "max-w-[85%] rounded-2xl rounded-br-sm bg-secondary px-4 py-3 text-sm"
            : "max-w-[85%] rounded-2xl rounded-bl-sm border border-border px-4 py-3 text-sm text-muted-foreground"
        }
      >
        {text}
      </p>
    </div>
  );
}
