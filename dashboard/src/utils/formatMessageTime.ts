/** Epoch-ms helpers shared by chat and memory history views. */

export function resolveMessageTimestampMs(raw: unknown): number {
  if (typeof raw === "number" && raw > 0) {
    return raw;
  }
  if (typeof raw === "string" && raw.trim()) {
    const parsed = Number(raw);
    if (Number.isFinite(parsed) && parsed > 0) {
      return parsed;
    }
  }
  return 0;
}

function ymdKey(d: Date, timeZone?: string): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(d);
}

function timeZoneOptions(
  timeZone?: string,
): Pick<Intl.DateTimeFormatOptions, "timeZone"> {
  return timeZone ? { timeZone } : {};
}

export function formatMessageTime(tsMs: number, timeZone?: string): string {
  if (!tsMs || tsMs <= 0) return "";
  const d = new Date(tsMs);
  const now = new Date();
  const tz = timeZoneOptions(timeZone);
  const hhmm = d.toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    ...tz,
  });
  if (ymdKey(d, timeZone) === ymdKey(now, timeZone)) {
    return hhmm;
  }
  const date = d.toLocaleDateString(undefined, {
    month: "2-digit",
    day: "2-digit",
    ...tz,
  });
  return `${date} ${hhmm}`;
}

/** Full datetime for thread lists; epoch seconds from the API. */
export function formatServerDateTime(
  epochSec: number,
  timeZone?: string,
): string {
  if (!epochSec) return "—";
  return new Date(epochSec * 1000).toLocaleString(undefined, {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    ...timeZoneOptions(timeZone),
  });
}
