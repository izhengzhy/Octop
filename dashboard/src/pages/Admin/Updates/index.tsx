import { useTranslation } from "react-i18next";
import PageShell from "../../../layouts/PageShell";
import UpdateConfig from "../../Settings/AdvancedSettings/UpdateConfig";

export default function UpdatesPage() {
  const { t } = useTranslation();

  return (
    <PageShell
      title={t("pageShell.adminUpdates.title")}
      subtitle={t("pageShell.adminUpdates.subtitle")}
    >
      <UpdateConfig />
    </PageShell>
  );
}
