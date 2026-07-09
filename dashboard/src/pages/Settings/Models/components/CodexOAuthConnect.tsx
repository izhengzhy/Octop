import { useCallback, useState } from "react";
import { Alert, Button, Space, Typography, message } from "antd";
import { useTranslation } from "react-i18next";
import { pollCodexOAuth, startCodexOAuth } from "../providerApi";

interface CodexOAuthConnectProps {
  onSuccess: () => void | Promise<void>;
}

export function CodexOAuthConnect({ onSuccess }: CodexOAuthConnectProps) {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(false);

  const handleLogin = useCallback(async () => {
    setLoading(true);
    try {
      const { authorize_url, state_id } = await startCodexOAuth(
        "/admin/models",
      );
      const popup = window.open(
        authorize_url,
        "octop-codex-oauth",
        "width=520,height=720",
      );
      const onMessage = async (ev: MessageEvent) => {
        if (ev.data?.type !== "octop:codex-oauth") return;
        if (ev.data.state_id !== state_id) return;
        window.removeEventListener("message", onMessage);
        popup?.close();
        try {
          const pending = await pollCodexOAuth(state_id);
          if (pending.status === "ok") {
            message.success(t("models.codexOAuthSuccess"));
            await onSuccess();
          } else {
            message.error(
              t("models.codexOAuthFailed", {
                error: pending.error ?? "unknown",
              }),
            );
          }
        } catch {
          message.error(t("models.codexOAuthFailed", { error: "poll" }));
        } finally {
          setLoading(false);
        }
      };
      window.addEventListener("message", onMessage);
    } catch (err) {
      message.error(
        err instanceof Error ? err.message : t("models.codexOAuthStartFailed"),
      );
      setLoading(false);
    }
  }, [onSuccess, t]);

  return (
    <Space direction="vertical" size="middle" style={{ width: "100%" }}>
      <Alert
        type="warning"
        showIcon
        message={t("models.codexOAuthDisclaimer")}
      />
      <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
        {t("models.codexOAuthHint")}
      </Typography.Paragraph>
      <Button
        type="primary"
        loading={loading}
        onClick={() => void handleLogin()}
      >
        {t("models.codexOAuthLogin")}
      </Button>
    </Space>
  );
}
