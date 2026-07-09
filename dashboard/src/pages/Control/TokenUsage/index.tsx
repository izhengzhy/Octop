/**
 * Token Usage — orca-flavoured summary page.
 *
 * Backed by ``GET /api/usage/summary`` (P1.1). Three controls at the
 * top: time window, granularity, optional agent scope. Body shows a
 * stat row with totals + a bar chart (when granularity ≠ total) +
 * a sortable bucket table.
 *
 * Replaced ~1050 LOC of finnie code that targeted endpoints octop
 * doesn't expose (per-channel histogram, dayjs-driven custom range,
 * per-turn drilldown). Those flows can be reintroduced as analytical
 * needs harden — for the MVP the contract is "tokens by day / agent /
 * model, scoped to the caller".
 */

import { useEffect, useMemo, useState } from "react";
import { Card, Select, Spin, Table, Empty, Tag, Space } from "antd";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
} from "recharts";
import { useTranslation } from "react-i18next";
import PageShell from "../../../layouts/PageShell";
import { useIsMobile } from "../../../hooks/useIsMobile";
import { request } from "../../../api/request";
import { useAgent } from "../../../context/AgentContext";

interface UsageBucket {
  key: string;
  label: string;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  turns: number;
}

interface UsageSummary {
  window: string;
  granularity: string;
  range_start: number;
  range_end: number;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  turns: number;
  avg_per_turn: number;
  buckets: UsageBucket[];
}

const WINDOW_OPTIONS = [
  { value: "today", label: "今天" },
  { value: "yesterday", label: "昨天" },
  { value: "last_7d", label: "最近 7 天" },
  { value: "last_30d", label: "最近 30 天" },
  { value: "all", label: "全部" },
];

const GRANULARITY_OPTIONS = [
  { value: "total", label: "汇总" },
  { value: "by_day", label: "按天" },
  { value: "by_agent", label: "按 Agent" },
  { value: "by_model", label: "按模型" },
];

function formatNumber(n: number): string {
  return n.toLocaleString();
}

function StatBlock({
  label,
  value,
}: {
  label: string;
  value: string | number;
}) {
  return (
    <div
      style={{
        flex: 1,
        padding: "12px 16px",
        background: "var(--fn-bg-secondary)",
        borderRadius: 6,
        border: "1px solid var(--fn-border-secondary)",
      }}
    >
      <div
        style={{
          fontSize: 11,
          color: "var(--fn-text-tertiary)",
          textTransform: "uppercase",
          letterSpacing: "0.04em",
        }}
      >
        {label}
      </div>
      <div style={{ fontSize: 22, fontWeight: 600, marginTop: 4 }}>{value}</div>
    </div>
  );
}

export default function TokenUsagePage() {
  const { t } = useTranslation();
  const { agents, activeAgentId } = useAgent();
  const isMobile = useIsMobile();
  const [windowKey, setWindowKey] = useState("last_30d");
  const [granularity, setGranularity] = useState("by_day");
  const [agentFilter, setAgentFilter] = useState<string | "all">("all");
  const [data, setData] = useState<UsageSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Default the agent filter to the currently-active one if it's set,
  // so the page reads as "look at the agent I'm chatting with right now".
  useEffect(() => {
    if (activeAgentId && agentFilter === "all") {
      setAgentFilter(activeAgentId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeAgentId]);

  const refresh = async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({
        window: windowKey,
        granularity,
      });
      if (agentFilter !== "all") {
        params.set("agent_id", agentFilter);
      }
      const summary = await request<UsageSummary>(`/usage/summary?${params}`);
      setData(summary);
    } catch (err: unknown) {
      const detail = err instanceof Error ? err.message : String(err);
      setError(detail);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [windowKey, granularity, agentFilter]);

  // The bar chart consumes buckets in display order. ``by_day`` is
  // returned newest-first by the API so we reverse for chronological
  // x-axis; the other granularities are already sorted by total desc
  // which reads more naturally in chart form.
  const chartBuckets = useMemo(() => {
    if (!data) return [];
    if (data.granularity === "by_day") return [...data.buckets].reverse();
    return data.buckets.slice(0, 20);
  }, [data]);

  return (
    <PageShell
      title={t("pageShell.tokenUsage.title")}
      subtitle={t("pageShell.tokenUsage.subtitle")}
      agentScoped
    >
      {/* Filter controls — stack on mobile, inline on desktop */}
      {isMobile ? (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 8,
            marginBottom: 16,
          }}
        >
          <Select
            value={windowKey}
            onChange={setWindowKey}
            style={{ width: "100%" }}
            options={WINDOW_OPTIONS}
          />
          <Select
            value={granularity}
            onChange={setGranularity}
            style={{ width: "100%" }}
            options={GRANULARITY_OPTIONS}
          />
          <Select
            value={agentFilter}
            onChange={(v) => setAgentFilter(v)}
            style={{ width: "100%" }}
            options={[
              { value: "all", label: "全部 Agent" },
              ...agents.map((a) => ({ value: a.agent_id, label: a.name })),
            ]}
          />
        </div>
      ) : (
        <Space style={{ marginBottom: 16 }} wrap>
          <Select
            value={windowKey}
            onChange={setWindowKey}
            style={{ width: 140 }}
            options={WINDOW_OPTIONS}
          />
          <Select
            value={granularity}
            onChange={setGranularity}
            style={{ width: 140 }}
            options={GRANULARITY_OPTIONS}
          />
          <Select
            value={agentFilter}
            onChange={(v) => setAgentFilter(v)}
            style={{ width: 200 }}
            options={[
              { value: "all", label: "全部 Agent" },
              ...agents.map((a) => ({ value: a.agent_id, label: a.name })),
            ]}
          />
        </Space>
      )}

      {error && (
        <Card
          size="small"
          style={{ borderColor: "var(--fn-color-error)", marginBottom: 16 }}
        >
          <span style={{ color: "var(--fn-color-error)" }}>{error}</span>
        </Card>
      )}

      {loading && !data ? (
        <div style={{ display: "flex", justifyContent: "center", padding: 40 }}>
          <Spin />
        </div>
      ) : data ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {/* Stats row — 5-up on desktop, 2-column grid on mobile */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: isMobile
                ? "repeat(2, minmax(0, 1fr))"
                : "repeat(5, minmax(0, 1fr))",
              gap: 12,
            }}
          >
            <StatBlock
              label="总 tokens"
              value={formatNumber(data.total_tokens)}
            />
            <StatBlock label="输入" value={formatNumber(data.input_tokens)} />
            <StatBlock label="输出" value={formatNumber(data.output_tokens)} />
            <StatBlock label="对话轮数" value={data.turns} />
            <StatBlock
              label="均值/轮"
              value={formatNumber(data.avg_per_turn)}
            />
          </div>

          {/* Chart */}
          {data.granularity !== "total" && data.buckets.length > 0 && (
            <Card
              size="small"
              style={{ borderColor: "var(--fn-border-secondary)" }}
            >
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={chartBuckets}>
                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke="var(--fn-border-secondary)"
                  />
                  <XAxis
                    dataKey="label"
                    tick={{ fontSize: 11 }}
                    interval="preserveStartEnd"
                  />
                  <YAxis tick={{ fontSize: 11 }} />
                  <RechartsTooltip
                    contentStyle={{
                      background: "var(--fn-bg-elevated)",
                      border: "1px solid var(--fn-border-secondary)",
                      borderRadius: 6,
                      fontSize: 12,
                    }}
                  />
                  <Bar
                    dataKey="input_tokens"
                    stackId="a"
                    fill="#4f6ef7"
                    name="input"
                  />
                  <Bar
                    dataKey="output_tokens"
                    stackId="a"
                    fill="#a06ef7"
                    name="output"
                  />
                </BarChart>
              </ResponsiveContainer>
            </Card>
          )}

          {/* Bucket table / item list — desktop: antd Table; mobile: stacked items */}
          {data.granularity !== "total" && (
            <Card
              size="small"
              title="明细"
              style={{ borderColor: "var(--fn-border-secondary)" }}
              styles={{ body: { padding: isMobile ? 0 : 24 } }}
            >
              {data.buckets.length === 0 ? (
                <Empty
                  description="区间内无记录"
                  style={{ padding: isMobile ? "20px 0" : undefined }}
                />
              ) : isMobile ? (
                <div>
                  {data.buckets.map((b) => (
                    <div
                      key={b.key}
                      style={{
                        display: "flex",
                        flexDirection: "column",
                        gap: 6,
                        padding: "12px 16px",
                        borderBottom: "1px solid var(--fn-border-secondary)",
                      }}
                    >
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between",
                        }}
                      >
                        <Tag style={{ margin: 0 }}>{b.label}</Tag>
                        <span
                          style={{
                            fontSize: 13,
                            fontWeight: 600,
                            color: "var(--fn-text-primary)",
                          }}
                        >
                          {formatNumber(b.total_tokens)}
                        </span>
                      </div>
                      <div
                        style={{
                          display: "grid",
                          gridTemplateColumns: "1fr 1fr 1fr",
                          gap: 4,
                          fontSize: 11,
                          color: "var(--fn-text-tertiary)",
                        }}
                      >
                        <span>输入 {formatNumber(b.input_tokens)}</span>
                        <span>输出 {formatNumber(b.output_tokens)}</span>
                        <span>{b.turns} 轮</span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <Table<UsageBucket>
                  rowKey="key"
                  size="small"
                  pagination={false}
                  dataSource={data.buckets}
                  scroll={{ x: "max-content" }}
                  columns={[
                    {
                      title: granularity === "by_day" ? "日期" : "Key",
                      dataIndex: "label",
                      fixed: "left",
                      width: 120,
                      render: (v) => <Tag>{v}</Tag>,
                    },
                    {
                      title: "输入",
                      dataIndex: "input_tokens",
                      render: formatNumber,
                      sorter: (a, b) => a.input_tokens - b.input_tokens,
                      align: "right",
                    },
                    {
                      title: "输出",
                      dataIndex: "output_tokens",
                      render: formatNumber,
                      sorter: (a, b) => a.output_tokens - b.output_tokens,
                      align: "right",
                    },
                    {
                      title: "总计",
                      dataIndex: "total_tokens",
                      render: formatNumber,
                      sorter: (a, b) => a.total_tokens - b.total_tokens,
                      defaultSortOrder: "descend",
                      align: "right",
                    },
                    {
                      title: "轮次",
                      dataIndex: "turns",
                      sorter: (a, b) => a.turns - b.turns,
                      align: "right",
                    },
                  ]}
                />
              )}
            </Card>
          )}
        </div>
      ) : null}
    </PageShell>
  );
}
