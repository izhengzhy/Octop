/**
 * PresetProviderModal — quick setup dialog for a built-in preset provider.
 */
import { useEffect, useState } from "react";
import { Form, Input, Modal, Tag, message, Button, Space } from "antd";
import { Zap } from "lucide-react";
import { useTranslation } from "react-i18next";
import { request } from "../../../../../api/request";
import { enrichWizardModel } from "../../wizardModelMeta";
import type { ProviderPreset, ProviderRow } from "../../useProviders";
import { PresetModelPicker } from "../PresetModelPicker";
import { CodexOAuthConnect } from "../CodexOAuthConnect";
import { testProviderDraft } from "../../providerApi";

interface PresetProviderModalProps {
  preset: ProviderPreset;
  open: boolean;
  onClose: () => void;
  onSaved: () => void | Promise<void>;
}

interface PresetForm {
  name: string;
  base_url: string;
  api_key?: string;
  selectedModels: string[];
  customModel?: string;
}

export function PresetProviderModal({
  preset,
  open,
  onClose,
  onSaved,
}: PresetProviderModalProps) {
  const { t } = useTranslation();
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [form] = Form.useForm<PresetForm>();
  const isOllama = preset.id === "ollama";
  const isCodexOAuth = preset.auth_method === "codex_oauth";

  useEffect(() => {
    if (open) {
      form.resetFields();
      form.setFieldsValue({
        name: preset.name,
        base_url: preset.base_url,
        selectedModels: preset.models.map((m) => m.id),
      });
    }
  }, [open, preset, form]);

  const resolveModelId = (values: PresetForm): string | null => {
    const selectedIds = new Set(values.selectedModels ?? []);
    const first = preset.models.find((m) => selectedIds.has(m.id));
    if (first) return first.id;
    const custom = values.customModel?.trim();
    return custom || null;
  };

  const handleTest = async () => {
    if (isCodexOAuth) return;
    try {
      const values = await form.validateFields();
      const modelId = resolveModelId(values);
      if (!modelId) {
        message.warning(t("models.testDraftNeedModel"));
        return;
      }
      const apiKey = values.api_key?.trim() || (isOllama ? "ollama" : "");
      if (!apiKey) {
        message.warning(t("models.pleaseEnterApiKey"));
        return;
      }
      setTesting(true);
      const result = await testProviderDraft({
        name: values.name.trim(),
        kind: preset.protocol,
        api_key: apiKey,
        base_url: values.base_url?.trim() || preset.base_url,
        model_id: modelId,
      });
      if (result.ok) {
        message.success(
          t("models.testSuccess", {
            name: modelId,
            time: result.latency_ms ?? 0,
          }),
        );
      } else {
        message.error(
          t("models.testConnectionFailed", {
            error: result.error ?? "unknown",
          }),
        );
      }
    } catch (err) {
      if (err && typeof err === "object" && "errorFields" in err) return;
      message.error(
        err instanceof Error ? err.message : t("models.testFailedSimple"),
      );
    } finally {
      setTesting(false);
    }
  };

  const handleSubmit = async () => {
    if (isCodexOAuth) return;
    try {
      const values = await form.validateFields();
      setSaving(true);

      const selectedIds = new Set(values.selectedModels ?? []);
      const modelEntries = preset.models
        .filter((m) => selectedIds.has(m.id))
        .map((m) => {
          const meta = enrichWizardModel(m, t);
          const entry: Record<string, unknown> = {
            id: m.id,
            name: m.name,
            enabled: true,
            input: meta.input,
            thinking: null,
          };
          if (meta.reasoning) entry.reasoning = true;
          const ctx =
            m.context_window ?? m.max_input_tokens ?? meta.context_window;
          if (ctx) entry.context_window = ctx;
          if (meta.max_tokens) entry.max_tokens = meta.max_tokens;
          return entry;
        });

      if (values.customModel?.trim()) {
        const cid = values.customModel.trim();
        if (!modelEntries.some((m) => m.id === cid)) {
          modelEntries.push({
            id: cid,
            name: cid,
            enabled: true,
            input: ["text"],
            thinking: null,
          });
        }
      }

      await request<ProviderRow>("/admin/providers", {
        method: "POST",
        body: JSON.stringify({
          name: values.name.trim(),
          kind: preset.protocol,
          base_url: values.base_url?.trim() || null,
          api_key: values.api_key?.trim() || (isOllama ? "ollama" : null),
          models: modelEntries,
        }),
      });
      message.success(
        t("models.providerCreatedSimple", { name: values.name.trim() }),
      );
      await onSaved();
      onClose();
    } catch (err) {
      if (err && typeof err === "object" && "errorFields" in err) return;
      const msg =
        err instanceof Error ? err.message : t("models.createFailedSimple");
      if (typeof msg === "string" && msg.includes("UNIQUE")) {
        message.error(t("models.presetNameExists"));
      } else {
        message.error(msg);
      }
    } finally {
      setSaving(false);
    }
  };

  const apiKeyPlaceholder = preset.api_key_prefix
    ? `${preset.api_key_prefix}...`
    : "sk-...";

  return (
    <Modal
      title={t("models.setupPreset", { name: preset.name })}
      open={open}
      onCancel={onClose}
      onOk={isCodexOAuth ? undefined : handleSubmit}
      confirmLoading={saving}
      okText={t("common.create")}
      cancelText={t("common.cancel")}
      destroyOnHidden
      width={640}
      footer={
        isCodexOAuth ? (
          <Button onClick={onClose}>{t("common.cancel")}</Button>
        ) : (
          <Space>
            <Button onClick={onClose}>{t("common.cancel")}</Button>
            <Button
              icon={<Zap size={14} />}
              loading={testing}
              onClick={() => void handleTest()}
            >
              {t("models.testConnection")}
            </Button>
            <Button
              type="primary"
              loading={saving}
              onClick={() => void handleSubmit()}
            >
              {t("common.create")}
            </Button>
          </Space>
        )
      }
    >
      {isCodexOAuth ? (
        <CodexOAuthConnect
          onSuccess={async () => {
            await onSaved();
            onClose();
          }}
        />
      ) : (
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item
            name="name"
            label={t("models.nameLabel")}
            rules={[{ required: true }]}
          >
            <Input placeholder={preset.name} />
          </Form.Item>

          <Form.Item label={t("models.kindLabel")}>
            <Tag color="blue">{preset.protocol}</Tag>
          </Form.Item>

          <Form.Item name="base_url" label="Base URL">
            <Input placeholder={preset.base_url || "https://..."} />
          </Form.Item>

          <Form.Item
            name="api_key"
            label="API Key"
            rules={
              isOllama
                ? []
                : [{ required: true, message: t("models.pleaseEnterApiKey") }]
            }
            extra={isOllama ? t("models.apiKeyExtraOptional") : undefined}
          >
            <Input.Password
              placeholder={
                isOllama ? t("models.apiKeyExtraOptional") : apiKeyPlaceholder
              }
              visibilityToggle
            />
          </Form.Item>

          {preset.models.length > 0 && (
            <Form.Item
              name="selectedModels"
              label={t("models.initialModelsLabel")}
              rules={[
                {
                  validator: (_, ids: string[] | undefined) =>
                    (ids?.length ?? 0) > 0
                      ? Promise.resolve()
                      : Promise.reject(
                          new Error(t("models.selectAtLeastOneModel")),
                        ),
                },
              ]}
            >
              <PresetModelPicker models={preset.models} />
            </Form.Item>
          )}

          <Form.Item
            name="customModel"
            label={t("models.addModel")}
            extra={t("models.modelIdPlaceholder")}
          >
            <Input placeholder={t("models.modelIdPlaceholder")} />
          </Form.Item>
        </Form>
      )}
    </Modal>
  );
}
