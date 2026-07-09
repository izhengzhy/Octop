import { Spin } from "antd";
import { Navigate } from "react-router-dom";
import { useUserRole } from "../hooks/useUserRole";

interface Props {
  children: React.ReactNode;
}

/**
 * Wraps admin-only routes. Redirects to /chat for non-admins.
 * Shows a full-screen spinner while the role is loading to avoid
 * a flash of the admin page before the redirect fires.
 */
export default function RequireAdmin({ children }: Props) {
  const role = useUserRole();

  if (role === null) {
    // Loading — show spinner.
    return (
      <div
        style={{
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <Spin size="large" />
      </div>
    );
  }

  if (role !== "admin") {
    return <Navigate to="/chat" replace />;
  }

  return <>{children}</>;
}
