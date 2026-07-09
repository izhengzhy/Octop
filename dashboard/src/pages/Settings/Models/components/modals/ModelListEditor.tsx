/**
 * ModelListEditor — manage models within a single octop provider.
 *
 * Adapts finnie's ModelListEditor to octop's data model:
 *   - octop has no per-model add/remove/toggle API endpoints
 *   - instead, we PATCH the full `models` array via PATCH /providers/{id}
 *   - models are stored as ProviderModel[] on the ProviderRow
 */
import { useState } from "react";
import {
  Button,
  Form,
  Input,
  InputNumber,
  Modal,
  Select,
  Switch,
  message,
} from "antd";
import {
  Check,
  ChevronDown,
  ChevronUp,
  Pencil,
  Plus,
  Trash2,
  X,
  Zap,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { request } from "../../../../../api/request";
import type { ProviderRow, ProviderModel } from "../../useProviders";
import { ModelMetaTags } from "../../modelMeta";
import styles from "../../index.module.less";

interface ModelListEditorProps {
  provider: ProviderRow;
  onSaved: () => void | Promise<void>;
  /** API path prefix for PATCH. Defaults to "/providers". */
  apiPrefix?: string;
}

const INPUT_TYPE_OPTIONS = [
  { value: "text", label: "inputTypeText" as const },
  { value: "image", label: "inputTypeImage" as const },
  { value: "audio", label: "inputTypeAudio" as const },
];

export function ModelListEditor({
  provider,
  onSaved,
  apiPrefix = "/providers",
}: ModelListEditorProps) {
  const { t } = useTranslation();
  const [adding, setAdding] = useState(false);
  const [editingModelId, setEditingModelId] = useState<string | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testingIds, setTestingIds] = useState<Set<string>>(new Set());
  const [testResults, setTestResults] = useState<
    Map<string, "success" | "failure">
  >(new Map());
  const [testingForm, setTestingForm] = useState(false);
  const [form] = Form.useForm();

  const models = provider.models ?? [];

  /** Save the updated models list to the backend. */
  const saveModels = async (updated: ProviderModel[]) => {
    await request(`${apiPrefix}/${provider.id}`, {
      method: "PATCH",
      body: JSON.stringify({ models: updated }),
    });
    await onSaved();
  };

  const handleToggleEnabled = async (
    modelId: string,
    modelName: string,
    enabled: boolean,
  ) => {
    try {
      const updated = models.map((m) =>
        m.id === modelId ? { ...m, enabled } : m,
      );
      await saveModels(updated);
      message.success(
        enabled
          ? t("models.modelEnabled", { name: modelName })
          : t("models.modelDisabled", { name: modelName }),
      );
    } catch (err) {
      message.error(
        err instanceof Error ? err.message : t("models.toggleFailed"),
      );
    }
  };

  const handleRemoveModel = (modelId: string, modelName: string) => {
    Modal.confirm({
      title: t("models.removeModel"),
      content: t("models.removeModelConfirm", {
        name: modelName,
        provider: provider.name,
      }),
      okText: t("common.delete"),
      okButtonProps: { danger: true },
      cancelText: t("common.cancel"),
      onOk: async () => {
        try {
          const updated = models.filter((m) => m.id !== modelId);
          await saveModels(updated);
          message.success(t("models.modelRemoved", { name: modelName }));
        } catch (err) {
          message.error(
            err instanceof Error ? err.message : t("models.modelRemoveFailed"),
          );
        }
      },
    });
  };

  const handleTestModel = async (modelId: string, modelName: string) => {
    setTestingIds((prev) => new Set(prev).add(modelId));
    try {
      const result = await request<{
        ok: boolean;
        latency_ms?: number;
        error?: string;
      }>(`${apiPrefix}/${provider.id}/test`, {
        method: "POST",
        body: JSON.stringify({ model_id: modelId }),
      });
      if (result.ok) {
        message.success(
          t("models.testSuccess", {
            name: modelName,
            time: result.latency_ms ?? 0,
          }),
        );
        setTestResults((prev) => new Map(prev).set(modelId, "success"));
      } else {
        message.error(
          t("models.testFailed", { error: result.error ?? "unknown" }),
        );
        setTestResults((prev) => new Map(prev).set(modelId, "failure"));
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      message.error(t("models.testFailed", { error: msg }));
      setTestResults((prev) => new Map(prev).set(modelId, "failure"));
    } finally {
      setTestingIds((prev) => {
        const next = new Set(prev);
        next.delete(modelId);
        return next;
      });
      setTimeout(() => {
        setTestResults((prev) => {
          const next = new Map(prev);
          next.delete(modelId);
          return next;
        });
      }, 2000);
    }
  };

  const handleTestFormModel = async () => {
    const modelId = (form.getFieldValue("id") as string | undefined)?.trim();
    if (!modelId) {
      message.warning(t("models.modelIdLabel"));
      return;
    }
    if (!provider.api_key) {
      message.warning(t("models.testRequiresAuth"));
      return;
    }
    setTestingForm(true);
    try {
      const result = await request<{
        ok: boolean;
        latency_ms?: number;
        error?: string;
      }>(`${apiPrefix}/${provider.id}/test`, {
        method: "POST",
        body: JSON.stringify({ model_id: modelId }),
      });
      const modelName =
        (form.getFieldValue("name") as string | undefined)?.trim() || modelId;
      if (result.ok) {
        message.success(
          t("models.testSuccess", {
            name: modelName,
            time: result.latency_ms ?? 0,
          }),
        );
      } else {
        message.error(
          t("models.testFailed", { error: result.error ?? "unknown" }),
        );
      }
    } catch (err) {
      message.error(t("models.testFailed", { error: String(err) }));
    } finally {
      setTestingForm(false);
    }
  };

  const buildModelEntry = (values: Record<string, unknown>): ProviderModel => {
    const id = (values.id as string).trim();
    const name = (values.name as string | undefined)?.trim() || id;
    const entry: ProviderModel = {
      id,
      name,
      enabled: true,
      input: (values.input as string[] | undefined) || ["text"],
      thinking: null,
    };
    if (values.context_window != null)
      entry.context_window = values.context_window as number;
    if (values.max_tokens != null)
      entry.max_tokens = values.max_tokens as number;
    if (values.reasoning != null) entry.reasoning = values.reasoning as boolean;
    return entry;
  };

  const handleAddModel = async () => {
    try {
      const values = await form.validateFields();
      setSaving(true);
      const entry = buildModelEntry(values as Record<string, unknown>);
      if (models.some((m) => m.id === entry.id)) {
        message.error(t("models.initialModelDuplicate", { name: entry.id }));
        return;
      }
      await saveModels([...models, entry]);
      message.success(t("models.modelAdded", { name: entry.name }));
      resetForm();
    } catch (err) {
      if (err && typeof err === "object" && "errorFields" in err) return;
      message.error(
        err instanceof Error ? err.message : t("models.modelAddFailed"),
      );
    } finally {
      setSaving(false);
    }
  };

  const handleEditModel = async () => {
    if (!editingModelId) return;
    try {
      const values = await form.validateFields();
      setSaving(true);
      const entry = buildModelEntry(values as Record<string, unknown>);
      // Preserve enabled state from existing model
      const existing = models.find((m) => m.id === editingModelId);
      if (existing) {
        entry.enabled = existing.enabled;
      }
      const updated = models.map((m) => (m.id === editingModelId ? entry : m));
      await saveModels(updated);
      message.success(t("models.modelUpdated", { name: entry.name }));
      resetForm();
    } catch (err) {
      if (err && typeof err === "object" && "errorFields" in err) return;
      message.error(
        err instanceof Error ? err.message : t("models.modelUpdateFailed"),
      );
    } finally {
      setSaving(false);
    }
  };

  const startEditing = (model: ProviderModel & Record<string, unknown>) => {
    setAdding(false);
    setEditingModelId(model.id);
    form.setFieldsValue({
      id: model.id,
      name: model.name,
      context_window:
        (model as Record<string, unknown>).context_window ?? undefined,
      max_tokens: (model as Record<string, unknown>).max_tokens ?? undefined,
      reasoning: (model as Record<string, unknown>).reasoning ?? undefined,
      input: model.input ?? ["text"],
    });
    const hasAdvanced =
      (model as Record<string, unknown>).context_window != null ||
      (model as Record<string, unknown>).max_tokens != null ||
      (model as Record<string, unknown>).reasoning != null;
    setShowAdvanced(hasAdvanced);
  };

  const startAdding = () => {
    setEditingModelId(null);
    form.resetFields();
    setAdding(true);
    setShowAdvanced(false);
  };

  const resetForm = () => {
    setAdding(false);
    setEditingModelId(null);
    setShowAdvanced(false);
    form.resetFields();
  };

  const isEditing = editingModelId !== null;
  const isFormVisible = adding || isEditing;
  const hasApiKey = !!provider.api_key;

  return (
    <div>
      {/* Model list */}
      <div className={styles.modelList}>
        {models.length === 0 ? (
          <div className={styles.modelListEmpty}>{t("models.noModels")}</div>
        ) : (
          models.map((m) => {
            const isCurrentEditing = editingModelId === m.id;
            const isEnabled = m.enabled !== false;
            const isTesting = testingIds.has(m.id);
            return (
              <div
                key={m.id}
                className={`${styles.modelListItem}${
                  isCurrentEditing ? ` ${styles.modelListItemEditing}` : ""
                }${!isEnabled ? ` ${styles.modelListItemDisabled}` : ""}`}
              >
                <Switch
                  size="small"
                  checked={isEnabled}
                  onChange={(checked) =>
                    handleToggleEnabled(m.id, m.name, checked)
                  }
                  className={styles.modelToggle}
                />
                <div className={styles.modelListItemInfo}>
                  <span className={styles.modelListItemName}>{m.name}</span>
                  {m.name !== m.id && (
                    <span className={styles.modelListItemId}>{m.id}</span>
                  )}
                  <ModelMetaTags
                    includeText
                    input={m.input}
                    context_window={m.context_window}
                    max_tokens={m.max_tokens}
                    reasoning={m.reasoning}
                  />
                </div>
                <div className={styles.modelListItemActions}>
                  {hasApiKey &&
                    isEnabled &&
                    (isTesting ? (
                      <Button
                        type="text"
                        size="small"
                        loading
                        style={{ marginRight: 4 }}
                      />
                    ) : testResults.get(m.id) === "success" ? (
                      <Check
                        size={14}
                        style={{
                          color: "#52c41a",
                          marginRight: 8,
                        }}
                      />
                    ) : testResults.get(m.id) === "failure" ? (
                      <X
                        size={14}
                        style={{
                          color: "#ff4d4f",
                          marginRight: 8,
                        }}
                      />
                    ) : (
                      <Button
                        type="text"
                        size="small"
                        icon={<Zap size={14} />}
                        onClick={() => handleTestModel(m.id, m.name)}
                        title={t("models.testConnection")}
                        style={{ marginRight: 4 }}
                      />
                    ))}
                  <Button
                    type="text"
                    size="small"
                    icon={<Pencil size={14} />}
                    onClick={() =>
                      startEditing(m as ProviderModel & Record<string, unknown>)
                    }
                    disabled={isCurrentEditing}
                  />
                  <Button
                    type="text"
                    size="small"
                    danger
                    icon={<Trash2 size={14} />}
                    onClick={() => handleRemoveModel(m.id, m.name)}
                  />
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Add / Edit model form */}
      {isFormVisible ? (
        <div className={styles.modelAddForm}>
          <Form form={form} layout="vertical" style={{ marginBottom: 0 }}>
            <Form.Item
              name="id"
              label={t("models.modelIdLabel")}
              rules={[{ required: true, message: t("models.modelIdLabel") }]}
              style={{ marginBottom: 12 }}
            >
              <Input
                placeholder={t("models.modelIdPlaceholder")}
                disabled={isEditing}
              />
            </Form.Item>
            <Form.Item
              name="name"
              label={t("models.modelNameLabel")}
              style={{ marginBottom: 12 }}
            >
              <Input placeholder={t("models.modelNamePlaceholder")} />
            </Form.Item>

            <Form.Item
              name="input"
              label={t("models.inputTypes")}
              initialValue={["text"]}
              style={{ marginBottom: 12 }}
            >
              <Select
                mode="multiple"
                allowClear
                placeholder={t("models.inputTypes")}
                options={INPUT_TYPE_OPTIONS.map((opt) => ({
                  value: opt.value,
                  label: t(`models.${opt.label}`),
                }))}
              />
            </Form.Item>

            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                marginBottom: showAdvanced ? 8 : 12,
              }}
            >
              <Button
                type="link"
                size="small"
                style={{ padding: 0 }}
                icon={
                  showAdvanced ? (
                    <ChevronUp size={14} />
                  ) : (
                    <ChevronDown size={14} />
                  )
                }
                onClick={() => setShowAdvanced(!showAdvanced)}
              >
                {showAdvanced
                  ? t("models.hideAdvanced")
                  : t("models.showAdvanced")}
              </Button>
            </div>

            {showAdvanced && (
              <div
                style={{
                  background:
                    "var(--ant-color-fill-quaternary, rgba(0,0,0,0.02))",
                  borderRadius: 6,
                  padding: "12px 12px 4px",
                  marginBottom: 12,
                }}
              >
                <div style={{ display: "flex", gap: 12 }}>
                  <Form.Item
                    name="context_window"
                    label={t("models.contextWindow")}
                    style={{ flex: 1, marginBottom: 10 }}
                  >
                    <InputNumber
                      min={0}
                      style={{ width: "100%" }}
                      placeholder={t("models.contextWindowPlaceholder")}
                    />
                  </Form.Item>
                  <Form.Item
                    name="max_tokens"
                    label={t("models.maxTokens")}
                    style={{ flex: 1, marginBottom: 10 }}
                  >
                    <InputNumber
                      min={0}
                      style={{ width: "100%" }}
                      placeholder={t("models.maxTokensPlaceholder")}
                    />
                  </Form.Item>
                </div>
                <Form.Item
                  name="reasoning"
                  label={t("models.reasoning")}
                  valuePropName="checked"
                  style={{ marginBottom: 10 }}
                >
                  <Switch size="small" />
                </Form.Item>
              </div>
            )}

            <div
              style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}
            >
              <Button size="small" onClick={resetForm}>
                {t("common.cancel")}
              </Button>
              {hasApiKey && (
                <Button
                  size="small"
                  icon={<Zap size={14} />}
                  loading={testingForm}
                  onClick={handleTestFormModel}
                >
                  {t("models.testConnection")}
                </Button>
              )}
              <Button
                type="primary"
                size="small"
                loading={saving}
                onClick={isEditing ? handleEditModel : handleAddModel}
              >
                {isEditing ? t("models.saveEdit") : t("models.addModel")}
              </Button>
            </div>
          </Form>
        </div>
      ) : (
        <Button
          type="dashed"
          block
          icon={<Plus size={14} />}
          onClick={startAdding}
          style={{ marginTop: 12 }}
        >
          {t("models.addModel")}
        </Button>
      )}
    </div>
  );
}
