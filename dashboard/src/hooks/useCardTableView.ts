import { useState } from "react";
import { useIsMobile } from "./useIsMobile";

export type CardTableViewMode = "card" | "table";

/**
 * Shared card/table view toggle. On mobile, card view is always shown
 * (matches Tasks page behaviour) regardless of Segmented selection.
 */
export function useCardTableView(defaultMode: CardTableViewMode = "table") {
  const isMobile = useIsMobile();
  const [viewMode, setViewMode] = useState<CardTableViewMode>(defaultMode);
  const showCardView = isMobile || viewMode === "card";
  return { isMobile, viewMode, setViewMode, showCardView };
}
