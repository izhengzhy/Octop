import { Button } from "antd";
import { Inbox, AlertCircle } from "lucide-react";
import type { ReactNode } from "react";

interface EmptyStateProps {
  /** Icon element. Defaults to inbox icon. */
  icon?: ReactNode;
  /** Main title */
  title?: string;
  /** Descriptive subtitle */
  description?: string;
  /** Optional action button text */
  actionLabel?: string;
  /** Optional action button callback */
  onAction?: () => void;
  /** Variant — affects icon and color */
  variant?: "empty" | "error";
  className?: string;
}

/**
 * Generic empty/error state placeholder for list and table pages.
 * Provides a consistent visual treatment across the app.
 */
export function EmptyState({
  icon,
  title,
  description,
  actionLabel,
  onAction,
  variant = "empty",
  className,
}: EmptyStateProps) {
  const defaultIcon =
    variant === "error" ? (
      <AlertCircle
        size={40}
        strokeWidth={1.2}
        style={{ color: "var(--fn-color-danger)" }}
      />
    ) : (
      <Inbox
        size={40}
        strokeWidth={1.2}
        style={{ color: "var(--fn-text-quaternary, #bfbfbf)" }}
      />
    );

  return (
    <div
      className={className}
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: "48px 24px",
        gap: 8,
        textAlign: "center",
      }}
    >
      <div style={{ marginBottom: 8 }}>{icon ?? defaultIcon}</div>
      {title && (
        <div
          style={{
            fontSize: 15,
            fontWeight: 500,
            color: "var(--fn-text-primary)",
          }}
        >
          {title}
        </div>
      )}
      {description && (
        <div
          style={{
            fontSize: 13,
            color: "var(--fn-text-tertiary)",
            maxWidth: 320,
            lineHeight: 1.6,
          }}
        >
          {description}
        </div>
      )}
      {actionLabel && onAction && (
        <Button type="primary" onClick={onAction} style={{ marginTop: 12 }}>
          {actionLabel}
        </Button>
      )}
    </div>
  );
}
