import { useCallback, useEffect, useRef, useState } from "react";

interface UseHorizontalResizeOptions {
  min: number;
  max: number;
  defaultSize: number;
  storageKey?: string;
}

function loadSize(key: string | undefined, fallback: number): number {
  if (!key) return fallback;
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return fallback;
    const n = Number.parseInt(raw, 10);
    return Number.isFinite(n) ? n : fallback;
  } catch {
    return fallback;
  }
}

/** Drag-to-resize a left panel width (pixels). */
export function useHorizontalResize({
  min,
  max,
  defaultSize,
  storageKey,
}: UseHorizontalResizeOptions) {
  const [size, setSize] = useState(() => loadSize(storageKey, defaultSize));
  const sizeRef = useRef(size);
  sizeRef.current = size;

  const onResizeStart = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      const startX = e.clientX;
      const startW = sizeRef.current;

      const onMove = (ev: MouseEvent) => {
        const next = Math.min(max, Math.max(min, startW + ev.clientX - startX));
        setSize(next);
        sizeRef.current = next;
      };

      const onUp = () => {
        document.removeEventListener("mousemove", onMove);
        document.removeEventListener("mouseup", onUp);
        document.body.style.cursor = "";
        document.body.style.userSelect = "";
        if (storageKey) {
          try {
            localStorage.setItem(storageKey, String(sizeRef.current));
          } catch {
            /* ignore */
          }
        }
      };

      document.addEventListener("mousemove", onMove);
      document.addEventListener("mouseup", onUp);
      document.body.style.cursor = "col-resize";
      document.body.style.userSelect = "none";
    },
    [min, max, storageKey],
  );

  useEffect(() => {
    const clamped = Math.min(max, Math.max(min, size));
    if (clamped !== size) setSize(clamped);
  }, [min, max, size]);

  return { size, onResizeStart };
}
