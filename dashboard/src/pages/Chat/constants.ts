/** Harness browser tools that activate the in-chat browser workspace. */
export const BROWSER_TOOL_NAMES = ["browser_use", "browser_control"] as const;

export const EMPTY_CHAT_SESSION_KEY = "__empty__";
export const PENDING_THREAD_ID = "__pending__";

export function isBrowserToolName(name: string | undefined): boolean {
  return (BROWSER_TOOL_NAMES as readonly string[]).includes(name ?? "");
}
