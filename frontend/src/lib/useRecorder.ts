import { useCallback, useEffect, useRef, useState } from "react";

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

export function useRecorder() {
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const [recording, setRecording] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const release = useCallback(() => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    recorderRef.current = null;
    chunksRef.current = [];
  }, []);

  useEffect(() => release, [release]);

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
  }, [release]);

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

  return { recording, error, start, stop, setError };
}
