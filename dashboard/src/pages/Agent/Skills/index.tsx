/**
 * Skills page — three tabs:
 *   1. Customized Skills  (workspace kind, editable + deletable)
 *   2. Built-in Skills    (builtin kind, toggle only)
 *   3. Skill Market       (SkillHub marketplace)
 */

import { useState } from "react";
import { Empty } from "antd";
import { useTranslation } from "react-i18next";
import { useAgent } from "../../../context/AgentContext";
import InstalledSkillsTab from "./components/InstalledSkillsTab";
import SkillHubTab from "./components/SkillHubTab";
import PageShell from "../../../layouts/PageShell";
import { useSkills } from "./useSkills";
import styles from "./index.module.less";

type SkillsTab = "custom" | "builtin" | "skillhub";

function SkillsPage() {
  const { t } = useTranslation();
  const { activeAgentId } = useAgent();
  const [activeTab, setActiveTab] = useState<SkillsTab>("custom");
  const onInstalledTab = activeTab === "custom" || activeTab === "builtin";
  const installedSkills = useSkills(activeAgentId, { enabled: onInstalledTab });

  const noAgent = (
    <Empty
      description={t("skills.noAgentSelected")}
      style={{ marginTop: 64 }}
    />
  );

  return (
    <PageShell
      title={t("pageShell.skills.title")}
      subtitle={t("pageShell.skills.subtitle")}
      agentScoped
    >
      <div className={styles.tabBar}>
        <button
          className={`${styles.tab}${
            activeTab === "custom" ? ` ${styles.active}` : ""
          }`}
          onClick={() => setActiveTab("custom")}
        >
          {t("skills.customizedSkills")}
        </button>
        <button
          className={`${styles.tab}${
            activeTab === "builtin" ? ` ${styles.active}` : ""
          }`}
          onClick={() => setActiveTab("builtin")}
        >
          {t("skills.builtinSkills")}
        </button>
        <button
          className={`${styles.tab}${
            activeTab === "skillhub" ? ` ${styles.active}` : ""
          }`}
          onClick={() => setActiveTab("skillhub")}
        >
          {t("skills.tencentSkillHub")}
        </button>
      </div>

      <div className={styles.content}>
        {activeTab === "custom" || activeTab === "builtin" ? (
          activeAgentId ? (
            <InstalledSkillsTab
              key={activeAgentId}
              kind={activeTab === "builtin" ? "builtin" : "custom"}
              {...installedSkills}
            />
          ) : (
            noAgent
          )
        ) : activeAgentId ? (
          <SkillHubTab key={activeAgentId} activeAgentId={activeAgentId} />
        ) : (
          noAgent
        )}
      </div>
    </PageShell>
  );
}

export default SkillsPage;
