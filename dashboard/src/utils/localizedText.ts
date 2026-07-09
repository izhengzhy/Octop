import type { UiLocale } from "./locale";

export interface LocalizedText {
  zh?: string;
  en?: string;
}

/** Pick the best string for the active UI locale, with cross-locale fallback. */
export function pickLocale(
  node: LocalizedText | undefined,
  locale: UiLocale,
): string {
  if (!node) return "";
  if (locale === "zh") return node.zh || node.en || "";
  return node.en || node.zh || "";
}
