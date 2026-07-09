import { useEffect, useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { Spin } from "antd";
import { getAuthToken } from "../api/request";
import { authApi } from "../api/modules/auth";
import { applyUserLocale } from "../utils/locale";

interface AuthGuardProps {
  children: React.ReactNode;
}

/**
 * Gate every protected route on (a) the initial admin existing and
 * (b) a valid JWT in localStorage. Octop always requires auth — there is
 * no "password protection disabled" mode like finnie had.
 */
export default function AuthGuard({ children }: AuthGuardProps) {
  const navigate = useNavigate();
  const location = useLocation();
  const [checking, setChecking] = useState(true);
  const [authed, setAuthed] = useState(false);

  useEffect(() => {
    let cancelled = false;

    const check = async () => {
      try {
        const status = await authApi.getAuthStatus();

        // No admin yet → push to setup wizard.
        if (status.setup_required) {
          if (!cancelled) navigate("/setup", { replace: true });
          return;
        }

        // Setup done. Need a token.
        const token = getAuthToken();
        if (!token) {
          if (!cancelled) navigate("/login", { replace: true });
          return;
        }

        // Validate the token by hitting /auth/me. On 401 the request.ts
        // interceptor already kicks the user back to /login, so we just
        // need to swallow the throw here.
        try {
          const me = await authApi.me();
          await applyUserLocale(me.locale);
          if (!cancelled) {
            setAuthed(true);
            setChecking(false);
          }
        } catch {
          if (!cancelled) navigate("/login", { replace: true });
        }
      } catch {
        // Backend unreachable — let the user through. The next API call
        // will surface the real error if the network is broken.
        if (!cancelled) {
          setAuthed(true);
          setChecking(false);
        }
      }
    };

    check();
    return () => {
      cancelled = true;
    };
  }, [location.pathname, navigate]);

  if (checking && !authed) {
    return (
      <div
        style={{
          height: "100dvh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "var(--fn-bg-layout)",
        }}
      >
        <Spin size="large" />
      </div>
    );
  }

  return <>{children}</>;
}
