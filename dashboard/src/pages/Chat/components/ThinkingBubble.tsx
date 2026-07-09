import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import styles from "../index.module.less";

const _thinkingStartedAtMap = new Map<string, number>();

interface ThinkingBubbleProps {
  onCancel?: () => void;
  sessionKey?: string;
}

export default function ThinkingBubble({
  onCancel,
  sessionKey = "__default__",
}: ThinkingBubbleProps) {
  const { t } = useTranslation();
  const symbolSrc = `${import.meta.env.BASE_URL}favico.svg`;

  const [elapsed, setElapsed] = useState(() => {
    let startedAt = _thinkingStartedAtMap.get(sessionKey);
    if (startedAt === undefined) {
      startedAt = Date.now();
      _thinkingStartedAtMap.set(sessionKey, startedAt);
    }
    return Math.floor((Date.now() - startedAt) / 1000);
  });

  useEffect(() => {
    const timer = setInterval(() => setElapsed((s) => s + 1), 1000);
    return () => clearInterval(timer);
  }, []);

  const elapsedLabel = elapsed > 0 ? ` · ${elapsed}s` : "";

  return (
    <div className={styles.thinkingBubble}>
      <div className={styles.avatarCol}>
        <div className={styles.botAvatar}>
          <img src={symbolSrc} alt="Octop" />
        </div>
      </div>
      <div className={styles.thinkingContent}>
        <span className={styles.thinkingDot} />
        <span className={styles.thinkingDot} />
        <span className={styles.thinkingDot} />
        <span className={styles.thinkingText}>
          {t("chat.thinking")}
          {elapsedLabel}
        </span>
        {onCancel && (
          <button
            className={styles.thinkingCancelBtn}
            onClick={onCancel}
            type="button"
            title={t("common.cancel")}
          >
            {t("common.cancel")}
          </button>
        )}
      </div>
    </div>
  );
}

export function clearThinkingTimer(sessionKey: string) {
  _thinkingStartedAtMap.delete(sessionKey);
}
