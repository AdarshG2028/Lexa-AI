import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { Mic, MicOff, PhoneOff, Volume2, Waves } from "lucide-react";

export const Route = createFileRoute("/conversation")({
  head: () => ({
    meta: [
      { title: "Live session — Lexa" },
      {
        name: "description",
        content:
          "Speak with Lexa in real time. Your transcript is captured for grammar and pronunciation feedback.",
      },
      { property: "og:title", content: "Live session — Lexa" },
      { property: "og:description", content: "A live voice conversation with your AI speaking partner." },
    ],
  }),
  component: Conversation,
});

type Turn = { id: number; speaker: "lexa" | "you"; text: string };

const scripted: Turn[] = [
  { id: 1, speaker: "lexa", text: "Hey! Good to hear you. What did you get up to this weekend?" },
  { id: 2, speaker: "you", text: "I go to my friend house and we cook some pasta together." },
  { id: 3, speaker: "lexa", text: "That sounds cozy. Who is the better cook between you two?" },
  { id: 4, speaker: "you", text: "Definitely him. I am only good for cutting the vegetables." },
  { id: 5, speaker: "lexa", text: "Ha! Fair division of labour. Did you try anything new this time?" },
  { id: 6, speaker: "you", text: "Yes, we make a sauce with walnut. It was very much delicious." },
];

function Conversation() {
  const navigate = useNavigate();
  const [turns, setTurns] = useState<Turn[]>(() => scripted.slice(0, 1));
  const [muted, setMuted] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const feedRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const t = setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    if (turns.length >= scripted.length) return;
    const t = setTimeout(() => setTurns((prev) => scripted.slice(0, prev.length + 1)), 3200);
    return () => clearTimeout(t);
  }, [turns]);

  useEffect(() => {
    feedRef.current?.scrollTo({ top: feedRef.current.scrollHeight, behavior: "smooth" });
  }, [turns]);

  const lexaSpeaking = turns[turns.length - 1]?.speaker === "lexa";
  const clock = `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;

  return (
    <main className="relative flex min-h-screen flex-col overflow-hidden">
      <div className="halo pointer-events-none absolute inset-x-0 -top-52 h-[640px]" />

      <header className="relative mx-auto flex w-full max-w-4xl items-center justify-between px-6 py-6">
        <Link to="/" className="flex items-center gap-2">
          <Waves className="size-5 text-primary" />
          <span className="tracking-tight">Lexa</span>
        </Link>
        <span className="rounded-full border border-border px-3 py-1 font-mono text-xs text-muted-foreground">
          {clock}
        </span>
      </header>

      <section className="relative mx-auto flex w-full max-w-4xl flex-1 flex-col px-6 pb-40">
        <div className="flex flex-col items-center py-10">
          <div className="relative flex size-32 items-center justify-center">
            {lexaSpeaking && (
              <span className="pulse-ring absolute inset-0 rounded-full border border-primary/50" />
            )}
            <span className="surface flex size-32 items-center justify-center rounded-full">
              <Volume2 className="size-8 text-primary" />
            </span>
          </div>
          <p className="mt-5 text-sm text-muted-foreground">
            {lexaSpeaking ? "Lexa is speaking…" : muted ? "Microphone muted" : "Listening to you…"}
          </p>
          <div className="mt-4 flex h-8 items-end gap-1.5">
            {Array.from({ length: 9 }).map((_, i) => (
              <span
                key={i}
                className={`bar-bounce w-1.5 rounded-full ${lexaSpeaking ? "bg-primary" : "bg-accent"} ${muted ? "opacity-25" : ""}`}
                style={{ height: `${12 + ((i * 7) % 20)}px`, animationDelay: `${i * 0.09}s` }}
              />
            ))}
          </div>
        </div>

        <div ref={feedRef} className="max-h-[42vh] space-y-4 overflow-y-auto pr-1">
          {turns.map((t) => (
            <div key={t.id} className={t.speaker === "you" ? "flex justify-end" : "flex justify-start"}>
              <div
                className={
                  t.speaker === "you"
                    ? "max-w-[78%] rounded-3xl rounded-br-md bg-secondary px-5 py-3.5 text-sm leading-relaxed"
                    : "surface max-w-[78%] rounded-3xl rounded-bl-md px-5 py-3.5 text-sm leading-relaxed text-muted-foreground"
                }
              >
                <span className="mb-1 block text-[11px] tracking-wide uppercase opacity-60">
                  {t.speaker === "you" ? "You" : "Lexa"}
                </span>
                {t.text}
              </div>
            </div>
          ))}
        </div>
      </section>

      <div className="fixed inset-x-0 bottom-0">
        <div className="mx-auto flex w-full max-w-4xl items-center justify-center gap-4 px-6 pb-8">
          <div className="surface flex items-center gap-3 rounded-full px-4 py-3">
            <button
              onClick={() => setMuted((m) => !m)}
              aria-label={muted ? "Unmute microphone" : "Mute microphone"}
              className="flex size-12 items-center justify-center rounded-full bg-secondary transition-colors hover:bg-muted"
            >
              {muted ? <MicOff className="size-5" /> : <Mic className="size-5 text-accent" />}
            </button>
            <button
              onClick={() => navigate({ to: "/insights" })}
              className="flex items-center gap-2 rounded-full bg-destructive px-6 py-3 text-sm font-medium text-destructive-foreground transition-opacity hover:opacity-90"
            >
              <PhoneOff className="size-4" /> End & review
            </button>
          </div>
        </div>
      </div>
    </main>
  );
}
