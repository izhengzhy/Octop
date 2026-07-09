import { useState } from "react";
import { Button, Empty } from "antd";
import { FlaskConical } from "lucide-react";
import { useTranslation } from "react-i18next";
import MBTISelector from "../Personalization/components/MBTISelector";
import PageShell from "../../../layouts/PageShell";
import { useAgent } from "../../../context/AgentContext";
import styles from "./index.module.less";

export default function MBTIPage() {
  const { t } = useTranslation();
  const { activeAgentId } = useAgent();
  const [testOpen, setTestOpen] = useState(false);

  return (
    <PageShell
      title={t("pageShell.mbti.title")}
      subtitle={t("pageShell.mbti.subtitle")}
      agentScoped
      actions={
        activeAgentId ? (
          <Button
            icon={<FlaskConical size={14} />}
            onClick={() => setTestOpen(true)}
          >
            {t("personalization.mbti.takeTest")}
          </Button>
        ) : undefined
      }
    >
      <div className={styles.mbtiPage}>
        {!activeAgentId ? (
          <Empty
            style={{ marginTop: 24 }}
            description={t("mbtiPage.pickAgent")}
          />
        ) : (
          <MBTISelector
            key={activeAgentId}
            showHeader={false}
            testOpen={testOpen}
            onTestOpenChange={setTestOpen}
          />
        )}
      </div>
    </PageShell>
  );
}
