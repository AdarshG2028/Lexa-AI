/**
 * The only place that knows the backend exists.
 *
 * Every shape here mirrors a pydantic model in `app/models.py`. When the
 * backend changes a field, this file is the single place to follow it.
 */

const BASE_URL = (import.meta.env["VITE_API_BASE_URL"] ?? "http://localhost:8001").replace(
  /\/+$/,
  "",
);

export type Speaker = "user" | "assistant";

export type TurnResult = {
  session_id: string;
  turn_id: string;
  transcript: string;
  reply_text: string;
  audio_url: string;
  tts_provider: string;
  history_messages: number;
  timings_ms: Record<string, number>;
};

export type SessionSummary = {
  id: string;
  status: "active" | "completed" | "expired";
  started_at: string;
  duration_seconds: number;
  turn_count: number;
};

export type GrammarIssue = {
  id: string;
  turn_id: string | null;
  original: string;
  corrected: string;
  explanation: string;
  category: string;
  confidence: number;
};

export type GrammarAnalysis = {
  session_id: string;
  provider: string;
  sentences_analyzed: number;
  words_analyzed: number;
  grammar_score: number;
  issue_count: number;
  issues: GrammarIssue[];
};

export type VocabularyIssue = {
  id: string;
  type: string;
  text: string;
  occurrences: number;
  example: string;
  suggestions: string[];
  explanation: string;
  confidence: number;
};

export type VocabularyAnalysis = {
  session_id: string;
  provider: string;
  words_analyzed: number;
  unique_words: number;
  lexical_diversity: number;
  vocabulary_score: number;
  issue_count: number;
  issues: VocabularyIssue[];
};

export type FluencyFinding = {
  id: string;
  type: "filler" | "long_pause" | "repetition" | "restart";
  text: string;
  occurrences: number;
  detail: string;
};

export type FluencyAnalysis = {
  session_id: string;
  timed_words: number;
  analyzed_seconds: number;
  speaking_rate_wpm: number;
  articulation_rate_wpm: number;
  pause_count: number;
  long_pause_count: number;
  total_pause_seconds: number;
  filler_count: number;
  repetition_count: number;
  restart_count: number;
  /** null when the conversation had no timed speech to measure. */
  fluency_score: number | null;
  note: string;
  findings: FluencyFinding[];
};

export type PronunciationIssue = {
  id: string;
  expected_phoneme: string;
  detected_phoneme: string;
  occurrences: number;
  confidence: number;
  affected_words: string[];
  practice_words: string[];
  explanation: string;
};

export type PronunciationAnalysis = {
  session_id: string;
  provider: string;
  analyzed_seconds: number;
  words_analyzed: number;
  phonemes_analyzed: number;
  substitutions_found: number;
  /** null when there was no spoken audio to analyse. */
  pronunciation_score: number | null;
  note: string;
  issue_count: number;
  issues: PronunciationIssue[];
};

/** Carries the backend's own error code, so the UI can react to the cause
 *  rather than pattern-matching on a message string. */
export class ApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly details: unknown;

  constructor(code: string, message: string, status: number, details?: unknown) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
    this.details = details;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE_URL}${path}`, init);
  } catch {
    throw new ApiError(
      "NETWORK_ERROR",
      `Could not reach the backend at ${BASE_URL}. Is the API server running?`,
      0,
    );
  }

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const envelope = body?.error;
    throw new ApiError(
      envelope?.code ?? "HTTP_ERROR",
      envelope?.message ?? `Request failed with status ${response.status}.`,
      response.status,
      envelope?.details,
    );
  }

  return (await response.json()) as T;
}

export function startSession(): Promise<SessionSummary> {
  return request<SessionSummary>("/api/v1/sessions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
}

export function getSession(sessionId: string): Promise<SessionSummary> {
  return request<SessionSummary>(`/api/v1/sessions/${sessionId}`);
}

export function endSession(sessionId: string): Promise<SessionSummary> {
  return request<SessionSummary>(`/api/v1/sessions/${sessionId}/end`, {
    method: "POST",
  });
}

/**
 * The filename matters: the backend decides whether it can decode the upload
 * from the extension, so a browser blob must be named with one it accepts.
 */
export function sendAudioTurn(
  sessionId: string,
  blob: Blob,
  filename: string,
): Promise<TurnResult> {
  const form = new FormData();
  form.append("file", blob, filename);
  return request<TurnResult>(`/api/v1/sessions/${sessionId}/turns`, {
    method: "POST",
    body: form,
  });
}

export function sendTextTurn(sessionId: string, text: string): Promise<TurnResult> {
  return request<TurnResult>(`/api/v1/sessions/${sessionId}/turns/text`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
}

/** Returns an object URL the caller owns and must revoke. */
export async function fetchAudio(audioUrl: string): Promise<string> {
  const response = await fetch(`${BASE_URL}${audioUrl}`);
  if (!response.ok)
    throw new ApiError("AUDIO_ERROR", "Reply audio could not be loaded.", response.status);
  return URL.createObjectURL(await response.blob());
}

const analysis = (sessionId: string, kind: string) =>
  request(`/api/v1/sessions/${sessionId}/analysis/${kind}`, { method: "POST" });

export const runGrammar = (id: string) => analysis(id, "grammar") as Promise<GrammarAnalysis>;
export const runVocabulary = (id: string) =>
  analysis(id, "vocabulary") as Promise<VocabularyAnalysis>;
export const runFluency = (id: string) => analysis(id, "fluency") as Promise<FluencyAnalysis>;
export const runPronunciation = (id: string) =>
  analysis(id, "pronunciation") as Promise<PronunciationAnalysis>;

export { BASE_URL };
