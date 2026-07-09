import { Globe } from "lucide-react";
import { useTranslation } from "react-i18next";
import BrowserWorkspace, {
  type PanelMode,
} from "../../../components/BrowserWorkspace";
import type { DisplayEnvironment } from "../../../api/types/browser";
import styles from "../index.module.less";

interface ChatBrowserPanelsProps {
  hasBrowserTool: boolean;
  isMobile: boolean;
  browserPanelOpen: boolean;
  browserPanelMode: PanelMode;
  isResizing: boolean;
  panelSizes: { rightWidth: number; bottomHeight: number };
  browserSessionId: string | null;
  activeThreadId: string | null;
  browserEnvironment: DisplayEnvironment;
  browserSessionState: string;
  browserControlOwner: "agent" | "user";
  onModeChange: (mode: PanelMode) => void;
  onClose: () => void;
  onResizeStart: (
    e: React.MouseEvent,
    direction: "horizontal" | "vertical",
  ) => void;
  onTogglePanel: () => void;
}

export default function ChatBrowserPanels({
  hasBrowserTool,
  isMobile,
  browserPanelOpen,
  browserPanelMode,
  isResizing,
  panelSizes,
  browserSessionId,
  activeThreadId,
  browserEnvironment,
  browserSessionState,
  browserControlOwner,
  onModeChange,
  onClose,
  onResizeStart,
  onTogglePanel,
}: ChatBrowserPanelsProps) {
  const { t } = useTranslation();
  const sessionId = browserSessionId ?? activeThreadId ?? null;
  const isAuth =
    browserSessionState === "awaiting_user_auth" ||
    browserSessionState === "authenticating";

  const statusTitle = browserSessionId
    ? t("browserWorkspace.browserStatusActive", {
        owner:
          browserControlOwner === "agent"
            ? t("browserWorkspace.agentControl")
            : t("browserWorkspace.userTakeover"),
      })
    : t("browserWorkspace.browserStatusIdle");

  if (!hasBrowserTool || isMobile) return null;

  return (
    <>
      {!browserPanelOpen && (
        <button
          type="button"
          className={`${styles.browserStatusBtn} ${
            styles.browserStatusActive
          } ${isAuth ? styles.browserStatusAuth : ""} ${
            browserControlOwner === "user" ? styles.browserStatusTakeover : ""
          }`}
          onClick={onTogglePanel}
          title={statusTitle}
        >
          <Globe size={14} />
          {browserSessionId && (
            <span
              className={`${styles.browserStatusDot} ${
                styles[`browserStatus_${browserControlOwner}`]
              }`}
            />
          )}
        </button>
      )}

      {browserPanelOpen && browserPanelMode === "right" && (
        <>
          <div
            className={`${styles.panelResizer} ${styles.horizontal} ${
              isResizing ? styles.resizerActive : ""
            }`}
            onMouseDown={(e) => onResizeStart(e, "horizontal")}
          >
            <div className={styles.resizerHandle} />
          </div>
          <BrowserWorkspace
            sessionId={sessionId}
            environment={browserEnvironment}
            onModeChange={onModeChange}
            onClose={onClose}
            style={{ width: panelSizes.rightWidth }}
          />
        </>
      )}

      {browserPanelOpen && browserPanelMode === "popup" && (
        <BrowserWorkspace
          sessionId={sessionId}
          environment={browserEnvironment}
          onModeChange={onModeChange}
          onClose={onClose}
        />
      )}
    </>
  );
}
