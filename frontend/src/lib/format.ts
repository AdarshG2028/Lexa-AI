/**
 * A provider's own quota can hand back a wait measured in seconds (a burst
 * limit) or in hours (a daily token cap resetting on a fixed schedule), so
 * this picks whichever unit reads naturally rather than always saying
 * "11496 seconds".
 */
export function formatWait(seconds: number): string {
  if (seconds < 60) return `${Math.max(1, Math.round(seconds))}s`;

  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m`;

  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  return remainingMinutes === 0 ? `${hours}h` : `${hours}h ${remainingMinutes}m`;
}
