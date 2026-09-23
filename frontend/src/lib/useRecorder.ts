import { useCallback, useEffect, useRef, useState } from "react";
import { MicVAD } from "@ricky0123/vad-web";

export type Recording = { blob: Blob; filename: string };

/**
 * Browsers disagree on what MediaRecorder can produce: Chrome and Firefox
 * give webm/opus, Safari gives mp4. Both are formats the backend accepts, so
 * the container is chosen here and the filename follows from it.
 */
function pickMimeType(): string {
  if (typeof MediaRecorder === "undefined") return "";
  const candidates = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg;codecs=opus"];
  return candidates.find((type) => MediaRecorder.isTypeSupported(type)) ?? "";
}

function extensionFor(mimeType: string): string {
  if (mimeType.includes("webm")) return "webm";
  if (mimeType.includes("mp4")) return "mp4";
  if (mimeType.includes("ogg")) return "ogg";
  return "webm";
}

// Pinned to the exact versions in bun.lock. The model and the WASM runtime
// are ~2-6 MB, too big to ship in the app bundle for a feature that is only
// ever a convenience on top of the manual mic button, so they load from a
// CDN instead of from this app's own server.
const VAD_PACKAGE_VERSION = "0.0.31";
const ORT_VERSION = "1.30.0";
const VAD_BASE_ASSET_PATH = `https://cdn.jsdelivr.net/npm/@ricky0123/vad-web@${VAD_PACKAGE_VERSION}/dist/`;
const ORT_WASM_BASE_PATH = `https://cdn.jsdelivr.net/npm/onnxruntime-web@${ORT_VERSION}/dist/`;

// How long a pause has to last before it is treated as "done talking" rather
// than a breath or a mid-sentence hesitation. Below the library's own
// default (1400ms) starts cutting people off; above it the app feels slow to
// notice you have stopped.
export const VAD_REDEMPTION_MS = 1400;
// Shorter than this and it is a misfire (a cough, a mic click), not a turn.
const VAD_MIN_SPEECH_MS = 400;
// The library's own default. Passed explicitly and reused in the frame
// handler below so the UI's idea of "gone quiet" can never drift from what
// actually ends the turn.
const VAD_NEGATIVE_SPEECH_THRESHOLD = 0.25;

export type VoiceActivityStatus =
  | "unavailable" // failed to load, or the browser cannot run it - manual stop is the only way to end a turn
  | "initializing" // model still loading for this turn
  | "listening" // ready, nothing said yet this turn
  | "speaking" // currently detected as speech
  | "ending"; // gone quiet after speech - counting down to an automatic stop

export type VoiceActivity = { status: VoiceActivityStatus; quietMs: number };

const IDLE_VOICE_ACTIVITY: VoiceActivity = { status: "unavailable", quietMs: 0 };

export function useRecorder(onAutoStop?: (recording: Recording) => void) {
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const vadRef = useRef<MicVAD | null>(null);
  const [recording, setRecording] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [voiceActivity, setVoiceActivity] = useState<VoiceActivity>(IDLE_VOICE_ACTIVITY);

  // Read via a ref so the caller never has to memoize this callback to keep
  // it fresh - a plain function passed on every render still works.
  const onAutoStopRef = useRef(onAutoStop);
  onAutoStopRef.current = onAutoStop;

  const release = useCallback(() => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    recorderRef.current = null;
    chunksRef.current = [];
    setVoiceActivity(IDLE_VOICE_ACTIVITY);

    const vad = vadRef.current;
    vadRef.current = null;
    if (vad) {
      // Never awaited: releasing the mic must not wait on VAD teardown, and
      // pauseStream is overridden to a no-op below, so this never touches
      // the tracks already stopped above.
      void vad.destroy().catch(() => {});
    }
  }, []);

  useEffect(() => release, [release]);

  /** Resolves once the recorder has flushed its last chunk; null if nothing
   *  was captured, which is what a mis-click produces. */
  const stop = useCallback((): Promise<Recording | null> => {
    return new Promise((resolve) => {
      const recorder = recorderRef.current;
      if (!recorder || recorder.state === "inactive") {
        setRecording(false);
        resolve(null);
        return;
      }

      recorder.onstop = () => {
        const mimeType = recorder.mimeType || "audio/webm";
        const blob = new Blob(chunksRef.current, { type: mimeType });
        release();
        setRecording(false);
        resolve(blob.size > 0 ? { blob, filename: `turn.${extensionFor(mimeType)}` } : null);
      };
      recorder.stop();
    });
  }, [release]);

  /**
   * Loads voice-activity detection for the stream just handed to
   * MediaRecorder and wires it to stop that same recording automatically.
   *
   * Failure here is never fatal: the manual mic button works whether or not
   * this succeeds, so every error is swallowed after marking the feature
   * unavailable for this turn.
   */
  const attachVoiceActivity = useCallback(
    async (stream: MediaStream) => {
      setVoiceActivity({ status: "initializing", quietMs: 0 });
      let hasSpokenThisTurn = false;
      let quietSince: number | null = null;

      try {
        const vad = await MicVAD.new({
          model: "legacy",
          baseAssetPath: VAD_BASE_ASSET_PATH,
          onnxWASMBasePath: ORT_WASM_BASE_PATH,
          redemptionMs: VAD_REDEMPTION_MS,
          minSpeechMs: VAD_MIN_SPEECH_MS,
          negativeSpeechThreshold: VAD_NEGATIVE_SPEECH_THRESHOLD,

          // This turn's MediaRecorder already owns the stream and its
          // lifecycle (see `release`); VAD only ever borrows it.
          getStream: async () => stream,
          pauseStream: async () => {},
          resumeStream: async () => stream,

          onSpeechStart: () => {
            hasSpokenThisTurn = true;
            quietSince = null;
            setVoiceActivity((v) =>
              v.status === "speaking" ? v : { status: "speaking", quietMs: 0 },
            );
          },
          onVADMisfire: () => {
            // Too short to count (a cough, a click) - back to waiting, not "ending".
            hasSpokenThisTurn = false;
            quietSince = null;
            setVoiceActivity({ status: "listening", quietMs: 0 });
          },
          onFrameProcessed: (probabilities) => {
            if (!hasSpokenThisTurn) return;
            if (probabilities.isSpeech >= VAD_NEGATIVE_SPEECH_THRESHOLD) {
              quietSince = null;
              setVoiceActivity((v) =>
                v.status === "speaking" ? v : { status: "speaking", quietMs: 0 },
              );
              return;
            }
            quietSince ??= performance.now();
            const quietMs = Math.min(performance.now() - quietSince, VAD_REDEMPTION_MS);
            setVoiceActivity({ status: "ending", quietMs });
          },
          onSpeechEnd: () => {
            // The Float32Array this carries is 16kHz mono PCM - not the webm
            // blob the backend needs, so it is intentionally unused. This is
            // only a trigger to stop the same MediaRecorder every other stop
            // path uses.
            void (async () => {
              const captured = await stop();
              if (captured) onAutoStopRef.current?.(captured);
            })();
          },
        });

        // The stream may already have been torn down (manual stop, or the
        // component unmounting) while the model was still loading.
        if (streamRef.current !== stream) {
          void vad.destroy().catch(() => {});
          return;
        }

        vadRef.current = vad;
        setVoiceActivity({ status: "listening", quietMs: 0 });
      } catch (cause) {
        console.warn("Voice activity detection unavailable; manual stop only.", cause);
        setVoiceActivity(IDLE_VOICE_ACTIVITY);
      }
    },
    [stop],
  );

  const start = useCallback(async (): Promise<boolean> => {
    setError(null);
    if (typeof navigator === "undefined" || !navigator.mediaDevices?.getUserMedia) {
      setError("This browser cannot record audio. Use the text box instead.");
      return false;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeType = pickMimeType();
      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);

      chunksRef.current = [];
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunksRef.current.push(event.data);
      };
      recorder.start();

      streamRef.current = stream;
      recorderRef.current = recorder;
      setRecording(true);
      // Deliberately not awaited: recording starts instantly on the manual
      // path regardless of how long the VAD model takes to load.
      void attachVoiceActivity(stream);
      return true;
    } catch (cause) {
      const name = cause instanceof DOMException ? cause.name : "";
      setError(
        name === "NotAllowedError"
          ? "Microphone access was denied. Allow it in the browser, or use the text box."
          : "No microphone was available. Use the text box instead.",
      );
      release();
      return false;
    }
  }, [release, attachVoiceActivity]);

  return { recording, error, start, stop, setError, voiceActivity };
}
