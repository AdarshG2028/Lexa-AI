import { createFileRoute, Link } from "@tanstack/react-router";
import { AudioLines, ArrowLeft, Check, Play, SpellCheck, Waves } from "lucide-react";

export const Route = createFileRoute("/insights")({
  head: () => ({
    meta: [
      { title: "Session report — grammar & pronunciation | Lexa" },
      {
        name: "description",
        content:
          "Your Lexa session report: corrected sentences with the grammar rule behind each fix, plus phonetic drills for the sounds you missed.",
      },
      { property: "og:title", content: "Session report — grammar & pronunciation | Lexa" },
      {
        property: "og:description",
        content: "Grammar corrections and phonetic coaching from your latest voice session.",
      },
    ],
  }),
  component: Insights,
});

const grammar = [
  {
    said: "I go to my friend house and we cook some pasta together.",
    better: "I went to my friend's house and we cooked some pasta together.",
    rule: "Past simple + possessive 's",
    note: "You were describing the weekend, so both verbs move to the past. “friend's house” shows possession.",
  },
  {
    said: "I am only good for cutting the vegetables.",
    better: "I'm only good at chopping vegetables.",
    rule: "Collocation & article",
    note: "“Good at” is the natural pairing, and general foods drop the definite article.",
  },
  {
    said: "We make a sauce with walnut. It was very much delicious.",
    better: "We made a walnut sauce. It was really delicious.",
    rule: "Intensifier choice",
    note: "“Very much” doesn't intensify adjectives — use “really” or just “delicious”.",
  },
];

const phonetics = [
  {
    word: "walnut",
    ipa: "/ˈwɔːl.nʌt/",
    issue: "You said “wal-noot”. The second vowel is a short ʌ, not a long oo.",
    drill: "walnut · peanut · chestnut",
    score: 62,
  },
  {
    word: "vegetables",
    ipa: "/ˈvedʒ.tə.bəlz/",
    issue: "Four syllables became three-and-a-half — the middle e is swallowed by native speakers too, keep it light.",
    drill: "vege-ta-bles · comfortable · chocolate",
    score: 74,
  },
  {
    word: "delicious",
    ipa: "/dɪˈlɪʃ.əs/",
    issue: "Stress landed on the first syllable. Push the weight onto “-li-”.",
    drill: "deLIcious · suspicious · ambitious",
    score: 58,
  },
];

function Insights() {
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

      <section className="relative mx-auto w-full max-w-5xl px-6 pb-16">
        <Link
          to="/"
          className="inline-flex items-center gap-2 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="size-4" /> Back home
        </Link>
        <h1 className="mt-6 text-4xl sm:text-5xl">Your session report</h1>
        <p className="mt-3 max-w-2xl text-muted-foreground">
          6 minutes · 214 words spoken · 3 grammar patterns and 3 sounds worth practising.
        </p>

        <div className="mt-8 grid gap-4 sm:grid-cols-3">
          <Stat label="Fluency" value="82" caption="Few long pauses" />
          <Stat label="Grammar" value="71" caption="Tense slips in past events" />
          <Stat label="Pronunciation" value="65" caption="Vowel length & stress" />
        </div>
      </section>

      <section className="relative mx-auto w-full max-w-5xl px-6 pb-16">
        <div className="flex items-center gap-3">
          <SpellCheck className="size-5 text-primary" />
          <h2 className="text-3xl">Grammar improvements</h2>
        </div>
        <div className="mt-6 space-y-4">
          {grammar.map((g) => (
            <article key={g.said} className="surface rounded-3xl p-6">
              <span className="rounded-full bg-secondary px-3 py-1 text-xs text-muted-foreground">
                {g.rule}
              </span>
              <p className="mt-4 text-sm text-muted-foreground line-through decoration-destructive/60">
                {g.said}
              </p>
              <p className="mt-2 flex items-start gap-2 text-lg leading-snug">
                <Check className="mt-1.5 size-4 shrink-0 text-primary" />
                <span>{g.better}</span>
              </p>
              <p className="mt-3 text-sm leading-relaxed text-muted-foreground">{g.note}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="relative mx-auto w-full max-w-5xl px-6 pb-24">
        <div className="flex items-center gap-3">
          <AudioLines className="size-5 text-accent" />
          <h2 className="text-3xl">Phonetic improvements</h2>
        </div>
        <div className="mt-6 grid gap-4 md:grid-cols-3">
          {phonetics.map((p) => (
            <article key={p.word} className="surface flex flex-col rounded-3xl p-6">
              <div className="flex items-baseline justify-between">
                <h3 className="text-2xl">{p.word}</h3>
                <span className="font-mono text-xs text-accent">{p.ipa}</span>
              </div>
              <div className="mt-4 h-1.5 w-full rounded-full bg-secondary">
                <div className="h-full rounded-full bg-accent" style={{ width: `${p.score}%` }} />
              </div>
              <p className="mt-4 flex-1 text-sm leading-relaxed text-muted-foreground">{p.issue}</p>
              <p className="mt-4 rounded-2xl bg-secondary px-4 py-3 text-sm">{p.drill}</p>
              <button className="mt-4 inline-flex items-center justify-center gap-2 rounded-full bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90">
                <Play className="size-4" /> Hear it spoken
              </button>
            </article>
          ))}
        </div>

        <div className="surface glow mt-10 flex flex-col items-center gap-4 rounded-3xl p-10 text-center">
          <h2 className="text-3xl">Ready for round two?</h2>
          <p className="max-w-md text-sm text-muted-foreground">
            Lexa will steer the next chat toward past-tense storytelling so these fixes get practice.
          </p>
          <Link
            to="/conversation"
            className="rounded-full bg-primary px-6 py-3 text-sm font-medium text-primary-foreground transition-transform hover:-translate-y-0.5"
          >
            Start another conversation
          </Link>
        </div>
      </section>
    </main>
  );
}

function Stat({ label, value, caption }: { label: string; value: string; caption: string }) {
  return (
    <div className="surface rounded-3xl p-6">
      <p className="text-xs tracking-wide text-muted-foreground uppercase">{label}</p>
      <p className="mt-2 font-display text-4xl text-primary">{value}</p>
      <p className="mt-1 text-sm text-muted-foreground">{caption}</p>
    </div>
  );
}
