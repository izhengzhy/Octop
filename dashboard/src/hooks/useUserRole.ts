import { useEffect, useState } from "react";
import { authApi } from "../api/modules/auth";

/**
 * Fetch the current user's role once on mount.
 * Returns null while the request is in-flight or on failure —
 * callers should treat null as "not admin" to avoid info leaks.
 */
export function useUserRole(): "admin" | "user" | null {
  const [role, setRole] = useState<"admin" | "user" | null>(null);
  useEffect(() => {
    let cancelled = false;
    authApi
      .me()
      .then((u) => {
        if (!cancelled) setRole(u.role);
      })
      .catch(() => {
        // Non-200 (unauthenticated probe etc.) — leave role as null.
      });
    return () => {
      cancelled = true;
    };
  }, []);
  return role;
}
