/**
 * useAutoScroll — streaming chat scroll state machine.
 *
 * Three mutually exclusive scroll modes (stored in scrollModeRef):
 *
 *  "follow"  — default. While streaming, each new token scrolls to the bottom.
 *  "anchor"  — activated on send. The viewport is locked at the user bubble
 *              (ANCHOR_TOP_OFFSET from the container top). Content grows
 *              downward; no auto-scroll happens. A hint ↓ button is shown
 *              when content overflows below the viewport.
 *  "free"    — user scrolled up intentionally. No automatic movement at all.
 *              ↓ button is shown. Restored to "follow" when user reaches bottom.
 *
 * Programmatic scroll guard:
 *  Any scrollTo / scrollIntoView fires scroll events. We mark them as
 *  programmatic via isProgrammaticScrollRef so handleScroll ignores them.
 */

import { useCallback, useEffect, useRef, useState } from "react";

// ─── constants ────────────────────────────────────────────────────────────────

/** px from bottom — counts as "at the bottom" */
const AT_BOTTOM_THRESHOLD = 80;

/** px gap between container top and anchored user bubble */
const ANCHOR_TOP_OFFSET = 16;

/** ms to keep the programmatic-scroll guard alive (covers smooth-scroll animation) */
const PROGRAMMATIC_GUARD_MS = 700;

/** ms to wait after touchend before re-checking (iOS momentum settle) */
const MOMENTUM_SETTLE_MS = 200;

// ─── types ────────────────────────────────────────────────────────────────────

type ScrollMode = "follow" | "anchor" | "free";

export interface UseAutoScrollOptions {
  deps?: readonly unknown[];
  smooth?: boolean;
}

export interface UseAutoScrollReturn {
  containerRef: React.RefObject<HTMLDivElement>;
  endRef: React.RefObject<HTMLDivElement>;
  showScrollBtn: boolean;
  scrollToBottom: (instant?: boolean) => void;
  scrollToAnchor: (anchorEl: HTMLElement) => void;
}

// ─── helpers ──────────────────────────────────────────────────────────────────

/**
 * Returns the scrollTop that places `el` exactly `topOffset` px below
 * the top edge of `container`, using viewport coordinates so the result
 * is independent of offsetParent chains and CSS Modules class-name hashing.
 */
function calcAnchorScrollTop(
  el: HTMLElement,
  container: HTMLElement,
  topOffset: number,
): number {
  const elRect = el.getBoundingClientRect();
  const containerRect = container.getBoundingClientRect();
  return container.scrollTop + (elRect.top - containerRect.top) - topOffset;
}

// ─── hook ─────────────────────────────────────────────────────────────────────

export function useAutoScroll({
  deps = [],
  smooth = true,
}: UseAutoScrollOptions = {}): UseAutoScrollReturn {
  const containerRef = useRef<HTMLDivElement>(null);
  const endRef = useRef<HTMLDivElement>(null);

  // Primary state machine — never use setState for this; refs are synchronous.
  const scrollModeRef = useRef<ScrollMode>("follow");

  // RAF handle
  const rafRef = useRef<number | null>(null);

  // Programmatic scroll guard
  const isProgrammaticRef = useRef(false);
  const guardTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Direction detection
  const prevScrollTopRef = useRef(0);

  // Hint button — only this is React state (needs re-render)
  const [showScrollBtn, setShowScrollBtn] = useState(false);

  // ── guard helpers ──────────────────────────────────────────────────────────

  const armGuard = useCallback((ms: number) => {
    isProgrammaticRef.current = true;
    if (guardTimerRef.current !== null) clearTimeout(guardTimerRef.current);
    guardTimerRef.current = setTimeout(() => {
      guardTimerRef.current = null;
      isProgrammaticRef.current = false;
      if (containerRef.current) {
        prevScrollTopRef.current = containerRef.current.scrollTop;
      }
    }, ms);
  }, []);

  // ── position helpers ───────────────────────────────────────────────────────

  const isAtBottom = useCallback((): boolean => {
    const c = containerRef.current;
    if (!c) return true;
    return c.scrollHeight - c.scrollTop - c.clientHeight <= AT_BOTTOM_THRESHOLD;
  }, []);

  const isContentBelowViewport = useCallback((): boolean => {
    const c = containerRef.current;
    if (!c) return false;
    return c.scrollHeight - c.scrollTop - c.clientHeight > AT_BOTTOM_THRESHOLD;
  }, []);

  // ── public scroll actions ──────────────────────────────────────────────────

  const scrollToBottom = useCallback(
    (instant = false) => {
      const container = containerRef.current;
      const end = endRef.current;
      if (!container || !end) return;

      scrollModeRef.current = "follow";

      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
      rafRef.current = requestAnimationFrame(() => {
        rafRef.current = null;
        armGuard(instant ? 50 : PROGRAMMATIC_GUARD_MS);
        end.scrollIntoView({
          behavior: instant || !smooth ? "instant" : "smooth",
          block: "end",
        });
        setShowScrollBtn(false);
      });
    },
    [smooth, armGuard],
  );

  const scrollToAnchor = useCallback(
    (anchorEl: HTMLElement) => {
      const container = containerRef.current;
      if (!container) return;

      scrollModeRef.current = "anchor";

      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
      rafRef.current = requestAnimationFrame(() => {
        rafRef.current = null;

        const targetScrollTop = Math.max(
          0,
          calcAnchorScrollTop(anchorEl, container, ANCHOR_TOP_OFFSET),
        );

        armGuard(smooth ? PROGRAMMATIC_GUARD_MS : 50);
        container.scrollTo({
          top: targetScrollTop,
          behavior: smooth ? "smooth" : "instant",
        });
        setShowScrollBtn(false);
      });
    },
    [smooth, armGuard],
  );

  // ── react to new content (deps change = new tokens / messages) ─────────────

  useEffect(() => {
    const mode = scrollModeRef.current;

    if (mode === "follow") {
      // Instant scroll during content growth — smooth scroll on every token
      // stacks animations and causes visible jitter on long responses.
      scrollToBottom(true);
    } else if (mode === "anchor") {
      // Anchor mode: don't scroll, just update the hint button.
      setShowScrollBtn(isContentBelowViewport());
    }
    // "free" mode: user is browsing history — do nothing.
    // eslint-disable-next-line react-hooks/exhaustive-deps -- caller supplies dynamic dependency list
  }, [...deps, scrollToBottom, isContentBelowViewport]);

  // ── event listeners ────────────────────────────────────────────────────────

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    prevScrollTopRef.current = container.scrollTop;

    // ── scroll ──
    // Fires for all sources: wheel, scrollbar drag, keyboard, touch.
    const handleScroll = (): void => {
      const cur = container.scrollTop;
      const prev = prevScrollTopRef.current;
      prevScrollTopRef.current = cur;

      // Ignore events produced by our own programmatic scrolls.
      if (isProgrammaticRef.current) return;

      const scrolledUp = cur < prev - 1; // 1px hysteresis

      if (scrolledUp) {
        // User intentionally scrolled up — pause everything.
        scrollModeRef.current = "free";
        setShowScrollBtn(true);
      } else if (isAtBottom()) {
        // User scrolled back to the bottom — resume follow.
        scrollModeRef.current = "follow";
        setShowScrollBtn(false);
      } else if (!isContentBelowViewport()) {
        // Content doesn't overflow the viewport — no reason to show the button.
        setShowScrollBtn(false);
      }
    };

    // ── wheel ──
    // Fast-path for desktop: fires *before* scrollTop updates on some browsers.
    const handleWheel = (e: WheelEvent): void => {
      if (isProgrammaticRef.current) return;
      if (e.deltaY < 0) {
        scrollModeRef.current = "free";
        setShowScrollBtn(true);
      } else if (e.deltaY > 0 && isAtBottom()) {
        // User scrolled down and we're already at the bottom — hide the hint.
        // scrollTop won't change so `handleScroll` may never fire; handle here.
        scrollModeRef.current = "follow";
        setShowScrollBtn(false);
      }
    };

    // ── touch ──
    let touchStartY = 0;

    const handleTouchStart = (e: TouchEvent): void => {
      touchStartY = e.touches[0]?.clientY ?? 0;
    };

    const handleTouchMove = (e: TouchEvent): void => {
      if (isProgrammaticRef.current) return;
      const dy = (e.touches[0]?.clientY ?? 0) - touchStartY;
      if (dy > 0) {
        // Swiping down = scrolling up = user wants to read history.
        scrollModeRef.current = "free";
        setShowScrollBtn(true);
      }
    };

    const handleTouchEnd = (): void => {
      setTimeout(() => {
        if (isAtBottom()) {
          scrollModeRef.current = "follow";
          setShowScrollBtn(false);
        }
      }, MOMENTUM_SETTLE_MS);
    };

    // ── ResizeObserver ──
    // Content height grew (new tokens painted). Act per current mode.
    const handleResize = (): void => {
      const mode = scrollModeRef.current;
      if (mode === "follow") {
        scrollToBottom(true); // instant during streaming for snappiness
      } else if (mode === "anchor") {
        setShowScrollBtn(isContentBelowViewport());
      } else {
        // "free" — just keep the button state accurate
        setShowScrollBtn(!isAtBottom());
      }
    };

    const ro = new ResizeObserver(handleResize);
    ro.observe(container);

    container.addEventListener("scroll", handleScroll, { passive: true });
    container.addEventListener("wheel", handleWheel, { passive: true });
    container.addEventListener("touchstart", handleTouchStart, {
      passive: true,
    });
    container.addEventListener("touchmove", handleTouchMove, { passive: true });
    container.addEventListener("touchend", handleTouchEnd, { passive: true });

    return () => {
      ro.disconnect();
      container.removeEventListener("scroll", handleScroll);
      container.removeEventListener("wheel", handleWheel);
      container.removeEventListener("touchstart", handleTouchStart);
      container.removeEventListener("touchmove", handleTouchMove);
      container.removeEventListener("touchend", handleTouchEnd);
      if (guardTimerRef.current !== null) clearTimeout(guardTimerRef.current);
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
    };
  }, [scrollToBottom, isAtBottom, isContentBelowViewport]);

  return {
    containerRef,
    endRef,
    showScrollBtn,
    scrollToBottom,
    scrollToAnchor,
  };
}
