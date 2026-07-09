import { Typography } from "antd";
import AgentSelector from "../components/AgentSelector";
import { useIsMobile } from "../hooks/useIsMobile";
import styles from "./PageShell.module.less";

const { Title, Text } = Typography;

interface PageShellProps {
  title: string;
  subtitle?: string;
  /** Right-aligned action buttons shown alongside the title. */
  actions?: React.ReactNode;
  /** Render agent picker below the title row, outside the scrollable content card. */
  agentScoped?: boolean;
  /** When true, the content area does not scroll; children fill remaining height. */
  fill?: boolean;
  children: React.ReactNode;
}

/**
 * Universal page wrapper for every non-fullscreen, non-Chat page.
 *
 * Visual contract (master spec §5 / sub-project ② spec §6.2):
 *  - Title row: 20px / 600 weight, fixed (does not scroll with content)
 *  - Subtitle: 13px / secondary colour, 4px below title
 *  - Optional agent bar (`agentScoped`): below title, outside content card
 *  - Gap between title row and content: 24px (12px + agent bar when scoped)
 *  - Content: colorBgContainer background, 24px padding, 8px radius
 *  - Only the content area scrolls internally
 *  - `actions` slot: right-aligned in the title row
 */
export default function PageShell({
  title,
  subtitle,
  actions,
  agentScoped,
  fill,
  children,
}: PageShellProps) {
  const isMobile = useIsMobile();
  const outerPad = isMobile ? 12 : 32;
  const outerPadTop = isMobile ? 12 : 24;
  const contentPad = isMobile ? 12 : 24;

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        padding: `${outerPadTop}px ${outerPad}px ${outerPad}px`,
        boxSizing: "border-box",
        overflow: "hidden",
      }}
    >
      {/* Title row — fixed, never scrolls */}
      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          gap: 12,
          flexShrink: 0,
          marginBottom: agentScoped ? 12 : 24,
        }}
      >
        <div>
          <Title
            level={4}
            style={{
              margin: 0,
              lineHeight: "28px",
              fontSize: 20,
              fontWeight: 600,
            }}
          >
            {title}
          </Title>
          {subtitle && (
            <Text
              type="secondary"
              style={{ fontSize: 13, marginTop: 4, display: "block" }}
            >
              {subtitle}
            </Text>
          )}
        </div>
        {actions && (
          <div style={{ flexShrink: 0, paddingTop: 2 }}>{actions}</div>
        )}
      </div>

      {agentScoped && (
        <div className={styles.agentBar}>
          <AgentSelector />
        </div>
      )}

      {/* Content — scrolls internally. Tighter side padding on mobile so
         tabbed pages get more usable horizontal space. */}
      <div
        style={{
          flex: 1,
          background: "var(--fn-bg-container, var(--fn-bg-elevated))",
          borderRadius: 8,
          padding: contentPad,
          overflow: fill ? "hidden" : "auto",
          minHeight: 0,
          display: fill ? "flex" : undefined,
          flexDirection: fill ? "column" : undefined,
        }}
      >
        {children}
      </div>
    </div>
  );
}
