import { createFileRoute, Link } from "@tanstack/react-router";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  Clock,
  FileVideo,
  Gauge,
  Loader2,
  RotateCcw,
  Sparkles,
  SpellCheck,
  Upload,
  Video,
  Waves,
} from "lucide-react";

import { ErrorBanner } from "@/components/ErrorBanner";
import {
  getVideoLimits,
  summarizeError,
  transcribeVideo,
  type ErrorSummary,
  type VideoTranscriptionResult,
  type VideoUploadLimits,
} from "@/lib/api";

export const Route = createFileRoute("/video")({
  head: () => ({
    meta: [
      { title: "Video review — upload a video | Lexa" },
      {
        name: "description",
        content:
          "Upload an English video under five minutes and get grammar, vocabulary and fluency feedback on how you speak.",
      },
      { property: "og:title", content: "Video review — Lexa" },
      {
        property: "og:description",
        content: "Turn an English video into a speech report.",
      },
    ],
  }),
  component: VideoReview,
});

// Used only until the server's real limits arrive. They match the backend
// defaults, so the page still validates sensibly if that request fails.
const DEFAULT_LIMITS: VideoUploadLimits = {
  max_seconds: 300,
  max_bytes: 200_000_000,
  formats: [".mp4", ".mov", ".m4v", ".webm", ".mkv", ".avi"],
};

const ACCEPT =
  "video/mp4,video/quicktime,video/webm,video/x-matroska,video/x-msvideo,.mp4,.mov,.m4v,.webm,.mkv,.avi";

type Phase = "idle" | "working" | "done";

function VideoReview() {
  const [limits, setLimits] = useState<VideoUploadLimits>(DEFAULT_LIMITS);
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [duration, setDuration] = useState<number | null>(null);
  const [previewNote, setPreviewNote] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [phase, setPhase] = useState<Phase>("idle");
  const [uploadPct, setUploadPct] = useState(0);
  const [result, setResult] = useState<VideoTranscriptionResult | null>(null);
  const [error, setError] = useState<ErrorSummary | null>(null);

  const inputRef = useRef<HTMLInputElement>(null);
  const resultRef = useRef<HTMLElement>(null);
  // A metadata probe outlives the selection that started it. This token lets
  // a late result be ignored rather than overwriting the next file's duration.
  const probeToken = useRef(0);

  useEffect(() => {
    let cancelled = false;
    getVideoLimits()
      .then((value) => {
        if (!cancelled) setLimits(value);
      })
      .catch(() => {
        // The defaults are the same values the server usually returns.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Object URLs are owned by the page; release one as soon as the next file
  // replaces it, and the last one when the page unmounts.
  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  const tooLong = duration !== null && duration > limits.max_seconds;
  const canAnalyze = file !== null && !tooLong && phase !== "working";

  const reset = useCallback(() => {
    probeToken.current += 1;
    setFile(null);
    setPreviewUrl(null);
    setDuration(null);
    setPreviewNote(null);
    setResult(null);
    setError(null);
    setPhase("idle");
    setUploadPct(0);
    if (inputRef.current) inputRef.current.value = "";
  }, []);

  const selectFile = useCallback(
    (candidate: File) => {
      setError(null);
      setResult(null);
      setPhase("idle");
      setUploadPct(0);
      setDuration(null);
      setPreviewNote(null);

      const dot = candidate.name.lastIndexOf(".");
      const extension = dot === -1 ? "" : candidate.name.slice(dot).toLowerCase();
      if (!limits.formats.includes(extension)) {
        setFile(null);
        setPreviewUrl(null);
        setError({
          message: `That file type is not supported. Choose ${limits.formats.join(", ")}.`,
          isRateLimited: false,
          retryAfterSeconds: null,
        });
        return;
      }

      if (candidate.size > limits.max_bytes) {
        setFile(null);
        setPreviewUrl(null);
        setError({
          message: `That video is ${formatBytes(candidate.size)}. The limit is ${formatBytes(limits.max_bytes)}.`,
          isRateLimited: false,
          retryAfterSeconds: null,
        });
        return;
      }

      setFile(candidate);
      setPreviewUrl(URL.createObjectURL(candidate));

      // Read the duration with a second object URL, so revoking it does not
      // break the preview element that is already on screen. Some containers
      // (notably MKV) do not play in every browser, which is why a failed
      // probe is a note rather than a rejection: the server can still read it.
      const token = ++probeToken.current;
      const probeUrl = URL.createObjectURL(candidate);
      const probe = document.createElement("video");
      probe.preload = "metadata";
      probe.muted = true;
      probe.onloadedmetadata = () => {
        URL.revokeObjectURL(probeUrl);
        if (probeToken.current !== token) return;
        const seconds = probe.duration;
        if (Number.isFinite(seconds) && seconds > 0) {
          setDuration(seconds);
        } else {
          setPreviewNote(
            "The browser could not read this file's duration. The server will still check it.",
          );
        }
      };
      probe.onerror = () => {
        URL.revokeObjectURL(probeUrl);
        if (probeToken.current !== token) return;
        setPreviewNote(
          "This format may not preview in your browser, but it can still be uploaded.",
        );
      };
      probe.src = probeUrl;
    },
    [limits],
  );

  const analyze = useCallback(async () => {
    if (!file || tooLong) return;

    setError(null);
    setResult(null);
    setPhase("working");
    setUploadPct(0);

    try {
      const value = await transcribeVideo(file, setUploadPct);
      setResult(value);
      setPhase("done");
      // The transcript card is below the fold on a laptop; bring it into
      // view once the upload finishes rather than making the result look
      // like it never arrived.
      requestAnimationFrame(() =>
        resultRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }),
      );
    } catch (cause) {
      setError(summarizeError(cause));
      setPhase("idle");
    }
  }, [file, tooLong]);

  const onDrop = useCallback(
    (event: React.DragEvent<HTMLDivElement>) => {
      event.preventDefault();
      setDragging(false);
      const candidate = event.dataTransfer.files[0];
      if (candidate) selectFile(candidate);
    },
    [selectFile],
  );

  return (
    <main className="relative min-h-screen overflow-hidden">
      <div className="halo pointer-events-none absolute inset-x-0 -top-52 h-[620px]" />

      <header className="relative mx-auto flex w-full max-w-5xl items-center justify-between px-6 py-6">
        <Link to="/" className="flex items-center gap-2">
          <Waves className="size-5 text-accent" />
          <span className="tracking-tight">Lexa</span>
        </Link>
        <Link
          to="/conversation"
          className="rounded-lg border border-border px-4 py-2 text-sm transition-colors hover:bg-secondary"
        >
          Start talking
        </Link>
      </header>

      <section className="relative mx-auto w-full max-w-5xl px-6 pb-16">
        <Link
          to="/"
          className="inline-flex items-center gap-2 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="size-4" /> Back home
        </Link>

        <div className="mt-6 flex flex-wrap items-center gap-3">
          <span className="inline-flex items-center gap-2 rounded-full border border-border px-3 py-1 font-mono text-[11px] tracking-wide text-muted-foreground uppercase">
            <Video className="size-3.5 text-accent" />
            Video review
          </span>
          <span className="font-mono text-[11px] tracking-wide text-muted-foreground uppercase">
            under {Math.round(limits.max_seconds / 60)} minutes
          </span>
        </div>

        <h1 className="mt-4 text-4xl leading-[1.08] sm:text-5xl">
          Upload a video.
          <br />
          Get an <span className="text-accent">English report.</span>
        </h1>
        <p className="mt-4 max-w-2xl text-muted-foreground">
          Already recorded yourself speaking English? Upload the clip and Lexa will transcribe it,
          then show the grammar, word choice and fluency you can improve.
        </p>

        <div className="mt-10 grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
          <div className="surface rounded-2xl p-6 sm:p-8">
            {!file ? (
              <>
                <div
                  onDragOver={(event) => {
                    event.preventDefault();
                    setDragging(true);
                  }}
                  onDragLeave={() => setDragging(false)}
                  onDrop={onDrop}
                  className={`flex min-h-64 flex-col items-center justify-center rounded-xl border border-dashed px-6 py-12 text-center transition-colors ${
                    dragging ? "border-accent bg-accent/[0.06]" : "border-border bg-background/40"
                  }`}
                >
                  <div className="surface flex size-14 items-center justify-center rounded-full">
                    <Upload className="size-6 text-accent" />
                  </div>
                  <h2 className="mt-5 text-2xl">Drop your video here</h2>
                  <p className="mt-2 max-w-sm text-sm leading-relaxed text-muted-foreground">
                    MP4, MOV, M4V, WebM, MKV or AVI. Under {Math.round(limits.max_seconds / 60)}{" "}
                    minutes and {formatBytes(limits.max_bytes)}.
                  </p>
                  <button
                    type="button"
                    onClick={() => inputRef.current?.click()}
                    className="mt-6 rounded-lg bg-primary px-6 py-3 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90"
                  >
                    Choose a video
                  </button>
                  <input
                    ref={inputRef}
                    type="file"
                    accept={ACCEPT}
                    className="hidden"
                    onChange={(event) => {
                      const candidate = event.currentTarget.files?.[0];
                      event.currentTarget.value = "";
                      if (candidate) selectFile(candidate);
                    }}
                  />
                </div>
                {error && <ErrorBanner error={error} className="mt-4" />}
              </>
            ) : (
              <div className="space-y-5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="flex min-w-0 items-center gap-3">
                    <div className="surface flex size-11 shrink-0 items-center justify-center rounded-xl">
                      <FileVideo className="size-5 text-accent" />
                    </div>
                    <div className="min-w-0">
                      <p className="truncate font-medium">{file.name}</p>
                      <p className="mt-0.5 text-xs text-muted-foreground">
                        {formatBytes(file.size)}
                        {duration !== null ? ` · ${formatDuration(duration)}` : ""}
                      </p>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={reset}
                    disabled={phase === "working"}
                    className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-xs text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground disabled:opacity-50"
                  >
                    <RotateCcw className="size-3.5" /> Change
                  </button>
                </div>

                {previewUrl && !previewNote && (
                  <video
                    src={previewUrl}
                    controls
                    className="max-h-72 w-full rounded-xl border border-border bg-black object-contain"
                  />
                )}
                {previewNote && (
                  <p className="rounded-xl bg-secondary px-4 py-3 text-sm text-muted-foreground">
                    {previewNote}
                  </p>
                )}

                {tooLong && (
                  <p className="rounded-xl border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive">
                    That clip is {formatDuration(duration ?? 0)}. Trim it to under{" "}
                    {formatDuration(limits.max_seconds)} and try again.
                  </p>
                )}
                {error && <ErrorBanner error={error} />}

                <button
                  type="button"
                  onClick={() => void analyze()}
                  disabled={!canAnalyze}
                  className="inline-flex items-center gap-2 rounded-lg bg-primary px-6 py-3 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-50"
                >
                  {phase === "working" ? (
                    <>
                      <Loader2 className="size-4 animate-spin" /> Working…
                    </>
                  ) : (
                    <>
                      <Sparkles className="size-4" /> Analyze my English
                    </>
                  )}
                </button>

                {phase === "working" && (
                  <div className="space-y-2">
                    <div className="h-2 overflow-hidden rounded-full bg-secondary">
                      <div
                        className={`h-full rounded-full bg-accent ${
                          uploadPct > 0 ? "transition-[width]" : "w-1/6 animate-pulse"
                        }`}
                        style={uploadPct > 0 ? { width: `${uploadPct}%` } : undefined}
                      />
                    </div>
                    <p className="text-sm text-muted-foreground">
                      {uploadPct > 0 && uploadPct < 100
                        ? `Uploading… ${uploadPct}%`
                        : "Upload complete. Extracting the audio and transcribing your speech…"}
                    </p>
                  </div>
                )}
              </div>
            )}
          </div>

          <aside className="surface rounded-2xl p-6 sm:p-8">
            <h2 className="text-2xl">What you&apos;ll get</h2>
            <ul className="mt-5 space-y-5 text-sm">
              <li className="flex gap-3">
                <SpellCheck className="mt-0.5 size-4 shrink-0 text-accent" />
                <div>
                  <p className="font-medium">Grammar corrections</p>
                  <p className="mt-1 leading-relaxed text-muted-foreground">
                    Each sentence you said, rewritten cleanly with the rule behind the change.
                  </p>
                </div>
              </li>
              <li className="flex gap-3">
                <Sparkles className="mt-0.5 size-4 shrink-0 text-accent" />
                <div>
                  <p className="font-medium">Word choice</p>
                  <p className="mt-1 leading-relaxed text-muted-foreground">
                    Repeated or basic words, with more precise alternatives to try.
                  </p>
                </div>
              </li>
              <li className="flex gap-3">
                <Gauge className="mt-0.5 size-4 shrink-0 text-accent" />
                <div>
                  <p className="font-medium">Fluency</p>
                  <p className="mt-1 leading-relaxed text-muted-foreground">
                    Speaking rate, pauses and filler words, measured from the audio timings.
                  </p>
                </div>
              </li>
            </ul>

            <div className="mt-7 rounded-xl border border-border bg-secondary/50 p-4 text-sm leading-relaxed text-muted-foreground">
              <p className="flex items-center gap-2 font-medium text-foreground">
                <Clock className="size-4 text-accent" /> A five-minute limit
              </p>
              <p className="mt-2">
                The server extracts the audio track and stores that, not the video. Your clip is not
                kept after it has been transcribed.
              </p>
            </div>
          </aside>
        </div>

        {result && (
          <section ref={resultRef} className="mt-10 scroll-mt-6">
            <div className="surface rounded-2xl p-6 sm:p-8">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <div className="flex size-10 items-center justify-center rounded-full bg-accent/10">
                    <Check className="size-5 text-accent" />
                  </div>
                  <div>
                    <h2 className="text-2xl">Transcript ready</h2>
                    <p className="text-sm text-muted-foreground">
                      {result.word_count} words · {formatDuration(result.duration_seconds)} of
                      speech
                    </p>
                  </div>
                </div>
                <span className="rounded-full border border-border px-3 py-1 font-mono text-[11px] tracking-wide text-muted-foreground uppercase">
                  English
                </span>
              </div>

              <div className="mt-5 max-h-80 overflow-y-auto rounded-xl border border-border bg-background/40 p-5 text-sm leading-relaxed whitespace-pre-wrap">
                {result.transcript}
              </div>

              <div className="mt-6 flex flex-wrap items-center gap-3">
                <Link
                  to="/insights"
                  search={{ session: result.session_id }}
                  className="inline-flex items-center gap-2 rounded-lg bg-primary px-6 py-3 text-sm font-medium text-primary-foreground transition-transform hover:-translate-y-0.5"
                >
                  View the full report <ArrowRight className="size-4" />
                </Link>
                <button
                  type="button"
                  onClick={reset}
                  className="inline-flex items-center gap-2 rounded-lg border border-border px-4 py-3 text-sm transition-colors hover:bg-secondary"
                >
                  <RotateCcw className="size-4" /> Analyze another
                </button>
              </div>
            </div>
          </section>
        )}
      </section>
    </main>
  );
}

function formatDuration(seconds: number): string {
  const total = Math.max(0, Math.round(seconds));
  const minutes = Math.floor(total / 60);
  const remainder = total % 60;
  return `${minutes}:${String(remainder).padStart(2, "0")}`;
}

function formatBytes(bytes: number): string {
  if (bytes >= 1_000_000_000) return `${(bytes / 1_000_000_000).toFixed(1)} GB`;
  return `${Math.round(bytes / 1_000_000)} MB`;
}
