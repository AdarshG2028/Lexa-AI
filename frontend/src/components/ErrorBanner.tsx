import { Clock } from "lucide-react";

import type { ErrorSummary } from "@/lib/api";
import { formatWait } from "@/lib/format";

/**
 * A rate limit is a "wait and try again", not a fault, so it is shown as one:
 * neutral, with a clock, rather than in the colour reserved for things that
 * are actually broken.
 */
export function ErrorBanner({
  error,
  className = "",
}: {
  error: ErrorSummary;
  className?: string;
}) {
  if (error.isRateLimited) {
    return (
      <div
        className={`flex items-start gap-3 rounded-xl border border-border bg-secondary px-5 py-3 text-sm ${className}`}
      >
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
    );
  }

  return (
    <p
      className={`rounded-xl border border-destructive/40 bg-destructive/10 px-5 py-3 text-sm text-destructive ${className}`}
    >
      {error.message}
    </p>
  );
}
