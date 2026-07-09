import { useCallback, useEffect, useRef, useState } from "react";
import { updateApi, type UpdateStatus } from "../api/modules/update";

const FOCUS_CHECK_MIN_MS = 30 * 60 * 1000;

export function useUpdateStatus() {
  const [status, setStatus] = useState<UpdateStatus | null>(null);
  const lastFetchRef = useRef(0);

  const refreshStatus = useCallback(async (force = false) => {
    const now = Date.now();
    if (!force && now - lastFetchRef.current < FOCUS_CHECK_MIN_MS) return;
    lastFetchRef.current = now;
    try {
      const next = await updateApi.getUpdateStatus();
      setStatus(next);
    } catch {
      /* ignore — UI should stay quiet on failure */
    }
  }, []);

  useEffect(() => {
    void refreshStatus(true);
  }, [refreshStatus]);

  useEffect(() => {
    const onFocus = () => {
      void refreshStatus(false);
    };
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, [refreshStatus]);

  const hasUpdate = Boolean(status?.has_update && status?.latest_version);

  return { status, hasUpdate, refreshStatus };
}
