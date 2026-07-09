import { Empty, Typography } from "antd";
import { useTranslation } from "react-i18next";
import PageShell from "../../../layouts/PageShell";
import AgentSelector from "../../../components/AgentSelector";
import { useAgent } from "../../../context/AgentContext";
import { useIsMobile } from "../../../hooks/useIsMobile";
import SubagentManager from "../../Experts/components/SubagentManager";
import styles from "./index.module.less";

const { Text } = Typography;

export default function SubagentsPage() {
  const { t } = useTranslation();
  const isMobile = useIsMobile();
  const { activeAgentId, agents } = useAgent();
  const activeAgent = agents.find((a) => a.agent_id === activeAgentId);

  const manager = !activeAgentId ? (
    <Empty
      style={{ marginTop: isMobile ? 48 : 24 }}
      description={t("subagents.pickAgent")}
    />
  ) : (
    <SubagentManager
      key={activeAgentId}
      agentId={activeAgentId}
      agentState={activeAgent?.state ?? "stopped"}
      fillHeight={isMobile}
    />
  );

  if (isMobile) {
    return (
      <div className={styles.subagentsFullscreen}>
        <header className={styles.subagentsFullscreenHeader}>
          <div className={styles.subagentsFullscreenTitleRow}>
            <h1 className={styles.subagentsFullscreenTitle}>
              {t("pageShell.subagents.title")}
            </h1>
          </div>
          <Text type="secondary" className={styles.subagentsFullscreenSubtitle}>
            {t("pageShell.subagents.subtitle")}
          </Text>
          <div className={styles.subagentsFullscreenAgentBar}>
            <AgentSelector />
          </div>
        </header>
        <div className={styles.subagentsFullscreenBody}>{manager}</div>
      </div>
    );
  }

  return (
    <PageShell
      title={t("pageShell.subagents.title")}
      subtitle={t("pageShell.subagents.subtitle")}
      agentScoped
    >
      <div className={styles.subagentsPage}>{manager}</div>
    </PageShell>
  );
}
