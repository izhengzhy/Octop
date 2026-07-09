import BrowserWorkspace, {
  type PanelMode,
} from "../../../components/BrowserWorkspace";
import type { DisplayEnvironment } from "../../../api/types/browser";
import styles from "../index.module.less";

interface ChatBrowserBottomPanelProps {
  sessionId: string | null;
  environment: DisplayEnvironment;
  isResizing: boolean;
  bottomHeight: number;
  onModeChange: (mode: PanelMode) => void;
  onClose: () => void;
  onResizeStart: (
    e: React.MouseEvent,
    direction: "horizontal" | "vertical",
  ) => void;
}

export default function ChatBrowserBottomPanel({
  sessionId,
  environment,
  isResizing,
  bottomHeight,
  onModeChange,
  onClose,
  onResizeStart,
}: ChatBrowserBottomPanelProps) {
  return (
    <>
      <div
        className={`${styles.panelResizer} ${styles.vertical} ${
          isResizing ? styles.resizerActive : ""
        }`}
        onMouseDown={(e) => onResizeStart(e, "vertical")}
      >
        <div className={styles.resizerHandle} />
      </div>
      <BrowserWorkspace
        sessionId={sessionId}
        environment={environment}
        onModeChange={onModeChange}
        onClose={onClose}
        style={{ height: bottomHeight }}
      />
    </>
  );
}
