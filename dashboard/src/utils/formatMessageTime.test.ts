import { afterEach, describe, expect, it, vi } from "vitest";
import { formatMessageTime, formatServerDateTime } from "./formatMessageTime";

function hourInZone(tsMs: number, timeZone: string): number {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone,
    hour: "numeric",
    hour12: false,
  }).formatToParts(new Date(tsMs));
  return Number(parts.find((part) => part.type === "hour")?.value);
}

describe("formatMessageTime", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("uses server timezone instead of browser local time", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-07-09T12:00:00Z"));

    const utcMorning = Date.UTC(2026, 6, 9, 7, 16, 37);
    expect(hourInZone(utcMorning, "Asia/Shanghai")).toBe(15);
    expect(hourInZone(utcMorning, "UTC")).toBe(7);
    expect(formatMessageTime(utcMorning, "Asia/Shanghai")).toBeTruthy();
    expect(formatMessageTime(utcMorning, "UTC")).toBeTruthy();
  });
});

describe("formatServerDateTime", () => {
  it("formats epoch seconds in the configured timezone", () => {
    const epochSec = Date.UTC(2026, 6, 9, 7, 16, 37) / 1000;
    expect(hourInZone(epochSec * 1000, "Asia/Shanghai")).toBe(15);
    expect(formatServerDateTime(epochSec, "Asia/Shanghai")).toContain("2026");
  });
});
