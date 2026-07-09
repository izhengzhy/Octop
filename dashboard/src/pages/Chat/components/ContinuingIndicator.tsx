import { useTranslation } from "react-i18next";
import styles from "../index.module.less";

interface ContinuingIndicatorProps {
  onCancel?: () => void;
}

export default function ContinuingIndicator({
  onCancel,
}: ContinuingIndicatorProps) {
  const { t } = useTranslation();
  return (
    <div className={styles.continuingIndicator}>
      <span className={styles.thinkingDot} />
      <span className={styles.thinkingDot} />
      <span className={styles.thinkingDot} />
      <span className={styles.continuingText}>{t("chat.continuing")}</span>
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
  );
}
