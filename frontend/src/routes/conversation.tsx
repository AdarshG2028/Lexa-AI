import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useCallback, useEffect, useRef, useState } from "react";
import { Clock, Loader2, Mic, PhoneOff, Send, Square, Volume2, Waves } from "lucide-react";

import {
  endSession,
  fetchAudio,
  sendAudioTurn,
  sendTextTurn,
  startSession,
  summarizeError,
  type ErrorSummary,
  type TurnResult,
} from "@/lib/api";
import { formatWait } from "@/lib/format";
import { useRecorder, VAD_REDEMPTION_MS } from "@/lib/useRecorder";

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
      {
        property: "og:description",
        content: "A live voice conversation with your AI speaking partner.",
      },
    ],
  }),
  component: Conversation,
});

type Turn = { id: string; speaker: "lexa" | "you"; text: string };
type Status = "starting" | "idle" | "recording" | "thinking" | "speaking" | "failed";

function Conversation() {
  const navigate = useNavigate();

  const [sessionId, setSessionId] = useState<string | null>(null);
  const [status, setStatus] = useState<Status>("starting");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [error, setError] = useState<ErrorSummary | null>(null);
  const [draft, setDraft] = useState("");
  const [seconds, setSeconds] = useState(0);
  const [ending, setEnding] = useState(false);

  const feedRef = useRef<HTMLDivElement>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    let cancelled = false;
    startSession()
      .then((session) => {
        if (cancelled) return;
        setSessionId(session.id);
        setStatus("idle");
      })
      .catch((cause) => {
        if (cancelled) return;
        setError(summarizeError(cause));
        setStatus("failed");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (status === "starting" || status === "failed") return;
    const timer = setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => clearInterval(timer);
  }, [status]);

  useEffect(() => {
    feedRef.current?.scrollTo({ top: feedRef.current.scrollHeight, behavior: "smooth" });
  }, [turns, status]);

  useEffect(() => {
    return () => {
      audioRef.current?.pause();
      audioRef.current = null;
    };
  }, []);

  /** Plays the reply and resolves when it finishes, so the UI returns to
   *  listening only once Lexa has actually stopped talking. */
  const play = useCallback(async (audioUrl: string) => {
    const objectUrl = await fetchAudio(audioUrl);
    const audio = new Audio(objectUrl);
    audioRef.current = audio;
    setStatus("speaking");

    await new Promise<void>((resolve) => {
      const finish = () => {
        URL.revokeObjectURL(objectUrl);
        resolve();
      };
      audio.onended = finish;
      audio.onerror = finish;
      audio.play().catch(finish);
    });
  }, []);

  const submit = useCallback(
    async (send: () => Promise<TurnResult>) => {
      setError(null);
      setStatus("thinking");
      try {
        const result = await send();
        setTurns((prev) => [
          ...prev,
          { id: `${result.turn_id}-you`, speaker: "you", text: result.transcript },
          { id: result.turn_id, speaker: "lexa", text: result.reply_text },
        ]);
        await play(result.audio_url);
      } catch (cause) {
        setError(summarizeError(cause));
      } finally {
        setStatus("idle");
      }
    },
    [play],
  );

  // A plain function, not useCallback: useRecorder reads this through a ref
  // it refreshes every render, so it always sees the current sessionId
  // without needing to be memoized here.
  const recorder = useRecorder((captured) => {
    if (!sessionId) return;
    void submit(() => sendAudioTurn(sessionId, captured.blob, captured.filename));
  });

  const toggleRecording = useCallback(async () => {
    if (!sessionId) return;

    if (recorder.recording) {
      const captured = await recorder.stop();
      if (!captured) {
        setError({
          message: "Nothing was recorded. Speak, then tap again to send.",
          isRateLimited: false,
          retryAfterSeconds: null,
        });
        setStatus("idle");
        return;
      }
      await submit(() => sendAudioTurn(sessionId, captured.blob, captured.filename));
      return;
    }

    audioRef.current?.pause();
    if (await recorder.start()) setStatus("recording");
  }, [recorder, sessionId, submit]);

  const sendDraft = useCallback(async () => {
    const text = draft.trim();
    if (!sessionId || !text) return;
    setDraft("");
    await submit(() => sendTextTurn(sessionId, text));
  }, [draft, sessionId, submit]);

  const finish = useCallback(async () => {
    if (!sessionId) return;
    setEnding(true);
    if (recorder.recording) await recorder.stop();
    audioRef.current?.pause();
    try {
      await endSession(sessionId);
    } catch {
      // A session that cannot be closed can still be analysed; the report
      // matters more than the status flag.
    }
    navigate({ to: "/insights", search: { session: sessionId } });
  }, [navigate, recorder, sessionId]);

  const busy = status === "thinking" || status === "speaking";
  const hasTurns = turns.length > 0;
  const clock = `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;

  return (
    <main className="relative flex h-dvh flex-col overflow-hidden">
      <div className="halo pointer-events-none absolute inset-x-0 -top-52 h-[640px]" />

      <header className="relative mx-auto flex w-full max-w-4xl shrink-0 items-center justify-between px-6 py-6">
        <Link to="/" className="flex items-center gap-2">
          <Waves className="size-5 text-accent" />
          <span className="tracking-tight">Lexa</span>
        </Link>
        <span className="rounded-full border border-border px-3 py-1 font-mono text-xs tabular-nums text-muted-foreground">
          {clock}
        </span>
      </header>

      {/* Everything below the header fits in exactly what's left of the
          screen (min-h-0 is what lets a flex child shrink below its content
          size); only the feed scrolls, so the page itself never does -
          without this, a tall enough page scrolls as a whole and can carry
          the header and this section's own top off-screen with it. */}
      <section className="relative mx-auto flex w-full min-h-0 max-w-4xl flex-1 flex-col px-6">
        {/* This block is a big "waiting to listen" hero before anything has
            been said, where the room is free to give it. Once a real
            transcript exists the feed needs that room far more, so it
            collapses to a compact row instead of quietly shrinking the
            available chat height on any window that isn't tall to begin with -
            the previous fixed-size version was exactly what let a short
            browser window clip the first message under this block. */}
        <div
          className={`flex shrink-0 items-center justify-center gap-3 ${hasTurns ? "flex-row py-3" : "flex-col py-6"}`}
        >
          <div
            className={`relative flex shrink-0 items-center justify-center ${hasTurns ? "size-11" : "size-28"}`}
          >
            {status === "speaking" && (
              <span className="pulse-ring absolute inset-0 rounded-full border border-accent/50" />
            )}
            <span
              className={`surface flex items-center justify-center rounded-full ${hasTurns ? "size-11" : "size-28"}`}
            >
              {status === "thinking" ? (
                <Loader2
                  className={
                    hasTurns ? "size-4 animate-spin text-accent" : "size-8 animate-spin text-accent"
                  }
                />
              ) : (
                <Volume2 className={hasTurns ? "size-4 text-accent" : "size-8 text-accent"} />
              )}
            </span>
          </div>
          <div className={hasTurns ? "flex flex-col items-start" : "flex flex-col items-center"}>
            <p
              className={`font-mono text-xs tracking-wide text-muted-foreground uppercase ${hasTurns ? "" : "mt-4"}`}
            >
              {caption(status)}
            </p>
            {status === "recording" && recorder.voiceActivity.status === "ending" && (
              <p className="mt-1 font-mono text-[11px] text-accent">
                Sending in{" "}
                {Math.max(
                  1,
                  Math.ceil((VAD_REDEMPTION_MS - recorder.voiceActivity.quietMs) / 1000),
                )}
                s unless you keep talking…
              </p>
            )}
            {!hasTurns && (
              <div className="mt-4 flex h-8 items-end gap-1.5">
                {Array.from({ length: 9 }).map((_, i) => (
                  <span
                    key={i}
                    className={`bar-bounce w-1.5 rounded-full ${status === "speaking" ? "bg-accent" : "bg-muted-foreground"} ${status === "recording" || status === "speaking" ? "" : "opacity-25"}`}
                    style={{ height: `${12 + ((i * 7) % 20)}px`, animationDelay: `${i * 0.09}s` }}
                  />
                ))}
              </div>
            )}
          </div>
        </div>

        {recorder.error && (
          <div className="mb-4 shrink-0 rounded-xl border border-destructive/40 bg-destructive/10 px-5 py-3 text-sm text-destructive">
            {recorder.error}
          </div>
        )}
        {error &&
          (error.isRateLimited ? (
            <div className="mb-4 flex shrink-0 items-start gap-3 rounded-xl border border-border bg-secondary px-5 py-3 text-sm">
              <Clock className="mt-0.5 size-4 shrink-0 text-accent" />
              <span>
                {error.message}
                {error.retryAfterSeconds !== null && (
                  <span className="text-muted-foreground">
                    {" "}
                    You can try again in about {formatWait(error.retryAfterSeconds)}.
                  </span>
                )}
              </span>
            </div>
          ) : (
            <div className="mb-4 shrink-0 rounded-xl border border-destructive/40 bg-destructive/10 px-5 py-3 text-sm text-destructive">
              {error.message}
            </div>
          ))}

        <div ref={feedRef} className="min-h-0 flex-1 space-y-4 overflow-y-auto pr-1 pb-4">
          {turns.length === 0 && status !== "starting" && (
            <p className="py-8 text-center text-sm text-muted-foreground">
              Tap the microphone and say something to begin.
            </p>
          )}
          {turns.map((turn) => (
            <div
              key={turn.id}
              className={turn.speaker === "you" ? "flex justify-end" : "flex justify-start"}
            >
              <div
                className={
                  turn.speaker === "you"
                    ? "max-w-[78%] rounded-xl rounded-br-sm bg-secondary px-5 py-3.5 text-sm leading-relaxed"
                    : "surface max-w-[78%] rounded-xl rounded-bl-sm px-5 py-3.5 text-sm leading-relaxed text-muted-foreground"
                }
              >
                <span className="mb-1 block font-mono text-[11px] tracking-wide uppercase opacity-60">
                  {turn.speaker === "you" ? "You" : "Lexa"}
                </span>
                {turn.text}
              </div>
            </div>
          ))}
        </div>
      </section>

      <div className="relative shrink-0">
        <div className="mx-auto flex w-full max-w-4xl flex-col items-center gap-3 px-6 pb-6">
          <div className="surface flex w-full max-w-xl items-center gap-2 rounded-2xl px-2 py-2">
            <input
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") void sendDraft();
              }}
              disabled={!sessionId || busy || recorder.recording}
              placeholder="…or type a turn instead"
              className="flex-1 bg-transparent px-4 py-2 text-sm outline-none placeholder:text-muted-foreground disabled:opacity-50"
            />
            <button
              onClick={() => void sendDraft()}
              disabled={!sessionId || busy || !draft.trim()}
              aria-label="Send typed turn"
              className="flex size-9 items-center justify-center rounded-full bg-secondary transition-colors hover:bg-muted disabled:opacity-40"
            >
              <Send className="size-4" />
            </button>
          </div>

          <div className="surface flex items-center gap-3 rounded-2xl px-4 py-3">
            <button
              onClick={() => void toggleRecording()}
              disabled={!sessionId || busy}
              aria-label={recorder.recording ? "Stop recording and send" : "Start recording"}
              className={`relative flex size-12 items-center justify-center rounded-full transition-colors disabled:opacity-40 ${
                recorder.recording
                  ? "bg-destructive text-destructive-foreground"
                  : "bg-secondary hover:bg-muted"
              }`}
            >
              {recorder.voiceActivity.status === "ending" && (
                <span className="pulse-ring absolute inset-0 rounded-full border border-accent/70" />
              )}
              {recorder.recording ? (
                <Square className="size-5" />
              ) : (
                <Mic className="size-5 text-accent" />
              )}
            </button>
            <button
              onClick={() => void finish()}
              disabled={!sessionId || ending}
              className="flex items-center gap-2 rounded-lg bg-destructive px-6 py-3 text-sm font-medium text-destructive-foreground transition-opacity hover:opacity-90 disabled:opacity-50"
            >
              <PhoneOff className="size-4" /> {ending ? "Ending…" : "End & review"}
            </button>
          </div>
        </div>
      </div>
    </main>
  );
}

function caption(status: Status): string {
  switch (status) {
    case "starting":
      return "Starting your session…";
    case "recording":
      return "Recording — tap the square when you have finished.";
    case "thinking":
      return "Lexa is thinking…";
    case "speaking":
      return "Lexa is speaking…";
    case "failed":
      return "Could not start a session.";
    default:
      return "Tap the microphone to speak.";
  }
}
