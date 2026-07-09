import { useCallback, useEffect, useState } from "react";
import {
  Button,
  Card,
  Form,
  Input,
  Modal,
  Select,
  Space,
  Switch,
  Tabs,
  Typography,
  message,
} from "antd";
import { useTranslation } from "react-i18next";
import PageShell from "../../../layouts/PageShell";
import {
  securityApi,
  type FilesystemRule,
  type SecurityPolicy,
} from "../../../api/modules/security";
import ToolGuardRulesPanel from "./ToolGuardRulesPanel";
import styles from "./index.module.less";

const { Title, Text, Paragraph } = Typography;
const { confirm } = Modal;
const { TextArea } = Input;

const DEFAULT_HITL_TOOLS = ["bash", "execute", "write_file", "edit_file"];

function pathsToText(rules: FilesystemRule[]): string {
  const paths = rules.flatMap((r) => r.paths);
  return paths.join("\n");
}

function textToRules(text: string | undefined): FilesystemRule[] {
  const paths = (text ?? "")
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
  if (paths.length === 0) return [];
  return [{ operations: ["read", "write"], paths, mode: "deny" }];
}

export default function SecuritySettingsPage() {
  const { t } = useTranslation();
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [policy, setPolicy] = useState<SecurityPolicy | null>(null);

  const fetchPolicy = useCallback(async () => {
    setLoading(true);
    try {
      const cfg = await securityApi.getPolicy();
      setPolicy(cfg);
      const tools =
        cfg.hitl.tools === "default" ? [...DEFAULT_HITL_TOOLS] : cfg.hitl.tools;
      form.setFieldsValue({
        hitl_enabled: cfg.hitl.enabled,
        hitl_tools: tools,
        fs_enabled: cfg.filesystem.enabled,
        fs_paths: pathsToText(cfg.filesystem.rules),
        pii_enabled: cfg.pii.enabled,
        pii_strategy: cfg.pii.strategy,
        skill_scan_mode: cfg.skill_scan.mode,
        tool_guard_enabled: cfg.tool_guard?.enabled ?? true,
        tool_guard_mode: cfg.tool_guard?.mode ?? "warn",
      });
    } catch (err) {
      message.error(t("security.loadError"));
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [form, t]);

  useEffect(() => {
    void fetchPolicy();
  }, [fetchPolicy]);

  const handleSave = async () => {
    try {
      await form.validateFields();
      const values = form.getFieldsValue(true);
      setSaving(true);
      const body: Partial<SecurityPolicy> = {
        hitl: {
          enabled: values.hitl_enabled ?? policy?.hitl.enabled ?? false,
          tools: (values.hitl_tools as string[] | undefined) ?? [],
          allowed_decisions: policy?.hitl.allowed_decisions ?? [
            "approve",
            "reject",
          ],
        },
        filesystem: {
          enabled: values.fs_enabled ?? policy?.filesystem.enabled ?? true,
          rules: textToRules(values.fs_paths as string | undefined),
        },
        pii: {
          enabled: values.pii_enabled ?? policy?.pii.enabled ?? true,
          strategy: values.pii_strategy ?? policy?.pii.strategy ?? "mask",
          surfaces: policy?.pii.surfaces ?? ["input", "output", "tool_results"],
        },
        skill_scan: {
          mode: values.skill_scan_mode ?? policy?.skill_scan.mode ?? "warn",
        },
        tool_guard: {
          enabled:
            values.tool_guard_enabled ?? policy?.tool_guard?.enabled ?? true,
          mode: values.tool_guard_mode ?? policy?.tool_guard?.mode ?? "warn",
        },
      };
      const saved = await securityApi.savePolicy(body);
      setPolicy(saved);
      message.success(t("security.saved"));
    } catch (err) {
      if (err && typeof err === "object" && "errorFields" in err) return;
      const detail = err instanceof Error ? err.message : null;
      message.error(detail || t("security.saveFailed"));
      console.error(err);
    } finally {
      setSaving(false);
    }
  };

  return (
    <PageShell
      title={t("pageShell.security.title")}
      subtitle={t("pageShell.security.subtitle")}
    >
      <div className={styles.wrap}>
        <Paragraph type="secondary">{t("security.intro")}</Paragraph>
        <Form form={form} layout="vertical" disabled={loading}>
          <Tabs
            destroyInactiveTabPane={false}
            items={[
              {
                key: "hitl",
                forceRender: true,
                label: t("security.tabHitl"),
                children: (
                  <Card size="small">
                    <Form.Item
                      name="hitl_enabled"
                      label={t("security.hitlEnable")}
                      valuePropName="checked"
                    >
                      <Switch
                        onChange={(checked) => {
                          if (checked) {
                            confirm({
                              title: t("security.hitlEnable"),
                              content: t("security.hitlEnableWarning"),
                              okText: t("common.confirm"),
                              cancelText: t("common.cancel"),
                              onCancel: () => {
                                form.setFieldValue("hitl_enabled", false);
                              },
                            });
                          }
                        }}
                      />
                    </Form.Item>
                    <Form.Item
                      name="hitl_tools"
                      label={t("security.hitlTools")}
                    >
                      <Select
                        mode="tags"
                        tokenSeparators={[","]}
                        options={DEFAULT_HITL_TOOLS.map((v) => ({
                          value: v,
                          label: v,
                        }))}
                      />
                    </Form.Item>
                    <Text type="secondary">{t("security.hitlHint")}</Text>
                  </Card>
                ),
              },
              {
                key: "filesystem",
                forceRender: true,
                label: t("security.tabFilesystem"),
                children: (
                  <Card size="small">
                    <Form.Item
                      name="fs_enabled"
                      label={t("security.fsEnable")}
                      valuePropName="checked"
                    >
                      <Switch />
                    </Form.Item>
                    <Form.Item name="fs_paths" label={t("security.fsPaths")}>
                      <TextArea
                        rows={8}
                        placeholder="/etc/**&#10;/root/**"
                      />
                    </Form.Item>
                    <Text type="secondary">{t("security.fsHint")}</Text>
                  </Card>
                ),
              },
              {
                key: "pii",
                forceRender: true,
                label: t("security.tabPii"),
                children: (
                  <Card size="small">
                    <Form.Item
                      name="pii_enabled"
                      label={t("security.piiEnable")}
                      valuePropName="checked"
                    >
                      <Switch />
                    </Form.Item>
                    <Form.Item
                      name="pii_strategy"
                      label={t("security.piiStrategy")}
                    >
                      <Select
                        options={[
                          { value: "mask", label: t("security.piiMask") },
                          { value: "redact", label: t("security.piiRedact") },
                          { value: "block", label: t("security.piiBlock") },
                          { value: "hash", label: t("security.piiHash") },
                        ]}
                      />
                    </Form.Item>
                  </Card>
                ),
              },
              {
                key: "tool_guard",
                forceRender: true,
                label: t("security.tabToolGuard"),
                children: (
                  <Card size="small">
                    <Form.Item
                      name="tool_guard_enabled"
                      label={t("security.toolGuardEnable")}
                      valuePropName="checked"
                    >
                      <Switch />
                    </Form.Item>
                    <Form.Item
                      name="tool_guard_mode"
                      label={t("security.toolGuardMode")}
                    >
                      <Select
                        options={[
                          {
                            value: "block",
                            label: t("security.toolGuardBlock"),
                          },
                          {
                            value: "require_approval",
                            label: t("security.toolGuardRequireApproval"),
                          },
                          { value: "warn", label: t("security.toolGuardWarn") },
                        ]}
                      />
                    </Form.Item>
                    <Text type="secondary">{t("security.toolGuardHint")}</Text>
                    <div style={{ marginTop: 16 }}>
                      <ToolGuardRulesPanel />
                    </div>
                  </Card>
                ),
              },
              {
                key: "skill_scan",
                forceRender: true,
                label: t("security.tabSkillScan"),
                children: (
                  <Card size="small">
                    <Form.Item
                      name="skill_scan_mode"
                      label={t("security.skillScanMode")}
                    >
                      <Select
                        options={[
                          { value: "off", label: t("security.skillScanOff") },
                          { value: "warn", label: t("security.skillScanWarn") },
                          {
                            value: "block",
                            label: t("security.skillScanBlock"),
                          },
                        ]}
                      />
                    </Form.Item>
                    <Text type="secondary">{t("security.skillScanHint")}</Text>
                  </Card>
                ),
              },
            ]}
          />
          <Space style={{ marginTop: 16 }}>
            <Button
              type="primary"
              loading={saving}
              onClick={() => void handleSave()}
            >
              {t("common.save")}
            </Button>
          </Space>
        </Form>
        <Title level={5} style={{ marginTop: 24 }}>
          {t("security.runtimeTitle")}
        </Title>
        <Text type="secondary">{t("security.runtimeHint")}</Text>
      </div>
    </PageShell>
  );
}
