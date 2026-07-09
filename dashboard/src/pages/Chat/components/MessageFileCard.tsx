import { useCallback, useState } from "react";
import { message as antMessage } from "antd";
import { ArrowDownToLine, FileText } from "lucide-react";
import { useTranslation } from "react-i18next";
import { downloadAuthFile } from "../../../components/AuthFileDownloadLink";
import { isDataUrl, needsAuthBlobFetch } from "../../../utils/toolMediaBlocks";
import styles from "../index.module.less";

/** Authenticated download card for chat / tool-result non-image files. */
export function MessageFileCard({
  url,
  filename,
}: {
  url: string;
  filename?: string;
}) {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(false);
  const needsAuth = needsAuthBlobFetch(url) || isDataUrl(url);
  const label = filename || url;

  const handleDownload = useCallback(async () => {
    if (!needsAuth) {
      const a = document.createElement("a");
      a.href = url;
      a.download = filename || "download";
      a.target = "_blank";
      a.rel = "noreferrer";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      return;
    }
    setLoading(true);
    try {
      await downloadAuthFile(url, { filename });
    } catch {
      antMessage.error(t("chat.downloadFailed", "下载失败，请重试"));
    } finally {
      setLoading(false);
    }
  }, [url, filename, needsAuth, t]);

  return (
    <div className={styles.messageFileCard}>
      <div className={styles.messageFileMeta}>
        <FileText size={14} className={styles.messageFileIcon} aria-hidden />
        <span className={styles.messageFileName} title={label}>
          {label}
        </span>
      </div>
      <button
        type="button"
        className={styles.messageFileDownloadBtn}
        onClick={() => void handleDownload()}
        disabled={loading}
        title={t("common.download")}
        aria-label={t("common.download")}
      >
        <ArrowDownToLine size={16} strokeWidth={2} />
      </button>
    </div>
  );
}
