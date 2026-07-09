import { useTranslation } from "react-i18next";
import styles from "../index.module.less";

interface ScrollToBottomButtonProps {
  visible: boolean;
  onClick: () => void;
}

export default function ScrollToBottomButton({
  visible,
  onClick,
}: ScrollToBottomButtonProps) {
  const { t } = useTranslation();
  return (
    <button
      className={`${styles.scrollToBottomBtn} ${
        visible
          ? styles.scrollToBottomBtnVisible
          : styles.scrollToBottomBtnHidden
      }`}
      onClick={onClick}
      type="button"
      title={t("chat.scrollToBottom")}
      aria-hidden={!visible}
    >
      ↓
    </button>
  );
}
