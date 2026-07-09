/**
 * Overview.tsx — first tab of the Memory page.
 *
 * This tab is strictly a statistics overview: KPI counts, atom-kind
 * distribution, growth trend, and computed composition. User-profile narrative
 * lives in ProfileOverview, while emotional trends live in EpisodesList.
 */
import { useCallback, useEffect, useState } from "react";
import { Button, Card, Empty, Skeleton, Tooltip } from "antd";
import {
  BarChart3,
  Loader2,
  Network,
  PieChart as PieChartIcon,
  RefreshCw,
} from "lucide-react";
import {
  Cell,
  Pie,
  PieChart,
  Tooltip as RTooltip,
  ResponsiveContainer,
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  XAxis,
  YAxis,
} from "recharts";
import { useTranslation } from "react-i18next";
import type { TFunction } from "i18next";

import MigrateMemory from "./MigrateMemory";

import {
  memoryDashboardApi,
  isAtomDeprecated,
  type AtomItem,
  type StatsCounts,
  type StatsAtomKindsResponse,
  type StatsGrowthResponse,
} from "../../../api/modules/memoryDashboard";

import styles from "./Overview.module.less";

interface Props {
  agentId: string;
}

/** Memory composition computed from listAtoms: confidence, importance, and status. */
interface Composition {
  total: number;
  confidence: { high: number; medium: number; low: number };
  importance: { high: number; medium: number; low: number };
  status: { active: number; deprecated: number };
}

interface PageState {
  counts: StatsCounts | null;
  kinds: StatsAtomKindsResponse | null;
  growth: StatsGrowthResponse | null;
  composition: Composition | null;
  /** First-load state. Shows skeletons and stays false after the first successful loadAll. */
  firstLoading: boolean;
  /** Subsequent refresh state. Spins only the refresh button without replacing content. */
  refreshing: boolean;
}

const INITIAL_STATE: PageState = {
  counts: null,
  kinds: null,
  growth: null,
  composition: null,
  firstLoading: true,
  refreshing: false,
};

/** Maximum atoms fetched to compute composition, including deprecated atoms. */
const COMPOSITION_SAMPLE_LIMIT = 500;

/** Semantic tones switched through className accent colors. */
type Tone = "rose" | "amber" | "blue" | "violet";

/** Atom-kind colors aligned with the tone colors in the module stylesheet. */
const KIND_COLOR: Record<string, string> = {
  Preference: "#e85d75", // rose for identity/preferences.
  Task: "#f59e0b", // amber for current tasks.
  Fact: "#3b82f6", // blue for historical facts.
  Decision: "#8b5cf6", // violet for decisions.
  ConflictCandidate: "#94a3b8", // slate for rare conflict candidates.
};

export default function Overview({ agentId }: Props) {
  const { t } = useTranslation();
  const [state, setState] = useState<PageState>(INITIAL_STATE);

  const loadAll = useCallback(async () => {
    if (!agentId) return;
    setState((s) => ({ ...s, refreshing: true }));

    const results = await Promise.allSettled([
      memoryDashboardApi.statsCounts(agentId),
      memoryDashboardApi.statsAtomKinds(agentId),
      memoryDashboardApi.statsGrowth(agentId, 14),
      memoryDashboardApi.listAtoms(agentId, {
        include_deprecated: true,
        limit: COMPOSITION_SAMPLE_LIMIT,
      }),
    ]);

    const [counts, kinds, growth, atoms] = results;

    setState({
      counts: counts.status === "fulfilled" ? counts.value : null,
      kinds: kinds.status === "fulfilled" ? kinds.value : null,
      growth: growth.status === "fulfilled" ? growth.value : null,
      composition:
        atoms.status === "fulfilled"
          ? buildComposition(atoms.value?.items ?? [])
          : null,
      firstLoading: false,
      refreshing: false,
    });
  }, [agentId]);

  useEffect(() => {
    if (!agentId) return;
    void loadAll();
  }, [agentId, loadAll]);

  const { firstLoading, refreshing } = state;

  return (
    <div className={styles.overview}>
      {/* Header for the statistics overview, not the profile narrative */}
      <div className={styles.heroHeader}>
        <div className={styles.heroTitleBlock}>
          <h2 className={styles.heroTitle}>
            {t("memory.overview.dashboardTitle", "概览")}
          </h2>
          {firstLoading ? (
            <Skeleton.Input
              active
              size="small"
              style={{ width: 260, height: 18, minHeight: 18 }}
            />
          ) : state.counts ? (
            <div className={styles.heroSubtitle}>
              {t(
                "memory.overview.dashboardSubtitle",
                "记忆规模、类型分布与待处理事项一览",
              )}
              <span className={styles.heroSubtitleDot}>·</span>
              <strong>{state.counts.atoms}</strong> 条记忆
              <span className={styles.heroSubtitleDot}>·</span>
              <strong>{state.counts.entities}</strong>{" "}
              {t("memory.overview.subtitleEntitiesUnit", "个关键主题")}
            </div>
          ) : (
            <div className={styles.heroSubtitle}>
              {t(
                "memory.overview.dashboardSubtitle",
                "记忆规模、类型分布与待处理事项一览",
              )}
            </div>
          )}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <Tooltip title={t("common.refresh", "刷新")}>
            <Button
              size="small"
              icon={
                refreshing ? <Loader2 size={14} /> : <RefreshCw size={14} />
              }
              onClick={() => void loadAll()}
              disabled={refreshing}
            />
          </Tooltip>
          <MigrateMemory agentId={agentId} />
        </div>
      </div>

      {/* Insights section: KPI plus charts */}
      <InsightsSection
        loading={firstLoading}
        counts={state.counts}
        kinds={state.kinds}
        growth={state.growth}
        composition={state.composition}
        t={t}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Insights section: KPI pills, pie chart, and bar chart.
// ---------------------------------------------------------------------------

function InsightsSection({
  loading,
  counts,
  kinds,
  growth,
  composition,
  t,
}: {
  loading: boolean;
  counts: StatsCounts | null;
  kinds: StatsAtomKindsResponse | null;
  growth: StatsGrowthResponse | null;
  composition: Composition | null;
  t: TFunction;
}) {
  return (
    <section className={styles.insights}>
      {/* KPI pill row */}
      <div className={styles.kpiStrip}>
        <KpiPill
          tone="rose"
          label={t("memory.overview.atoms", "记忆条目")}
          value={counts?.atoms}
          delta={counts?.atoms_delta_7d}
          loading={loading}
        />
        <KpiPill
          tone="violet"
          label={t("memory.overview.entities", "关键人事物")}
          value={counts?.entities}
          delta={counts?.entities_delta_7d}
          loading={loading}
        />
        <KpiPill
          tone="amber"
          label={t("memory.overview.episodes", "情绪片段")}
          value={counts?.episodes}
          delta={counts?.episodes_delta_7d}
          loading={loading}
        />
        <KpiPill
          tone="blue"
          label={t("memory.overview.activeAtoms", "活跃记忆")}
          value={composition?.status.active}
          loading={loading}
        />
        <KpiPill
          tone="rose"
          label={t("memory.overview.candidatesPending", "待沉淀")}
          value={counts?.candidates_pending}
          loading={loading}
          warn={(counts?.candidates_pending ?? 0) > 0}
        />
      </div>

      {/* Top row: memory composition and memory type distribution, 50% each */}
      <div className={styles.chartsRow}>
        <Card
          className={styles.chartCard}
          size="small"
          title={
            <span className={styles.chartTitle}>
              <Network className={styles.chartTitleIcon} size={16} />
              {t("memory.overview.compositionTitle", "记忆构成")}
              <span className={styles.compSubtitle}>
                {t(
                  "memory.overview.compositionSubtitle",
                  "这些记忆的质量与状态",
                )}
              </span>
            </span>
          }
        >
          {loading && !composition ? (
            <Skeleton active paragraph={{ rows: 3 }} title={false} />
          ) : !composition || composition.total === 0 ? (
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description={t(
                "memory.overview.compositionEmpty",
                "暂无记忆构成数据",
              )}
            />
          ) : (
            <div className={styles.compBlockList}>
              <DistRow
                label={t("memory.overview.compConfidence", "置信度")}
                segments={[
                  {
                    key: "high",
                    label: t("memory.confidence.high", "高置信"),
                    value: composition.confidence.high,
                    color: "#e85d75",
                  },
                  {
                    key: "medium",
                    label: t("memory.confidence.medium", "中置信"),
                    value: composition.confidence.medium,
                    color: "#f59e0b",
                  },
                  {
                    key: "low",
                    label: t("memory.confidence.low", "低置信"),
                    value: composition.confidence.low,
                    color: "#94a3b8",
                  },
                ]}
              />
              <DistRow
                label={t("memory.overview.compImportance", "重要度")}
                segments={[
                  {
                    key: "high",
                    label: t("memory.importance.high", "非常重要"),
                    value: composition.importance.high,
                    color: "#e85d75",
                  },
                  {
                    key: "medium",
                    label: t("memory.importance.medium", "重要"),
                    value: composition.importance.medium,
                    color: "#f59e0b",
                  },
                  {
                    key: "low",
                    label: t("memory.importance.low", "一般"),
                    value: composition.importance.low,
                    color: "#94a3b8",
                  },
                ]}
              />
              <DistRow
                label={t("memory.overview.compStatus", "状态")}
                segments={[
                  {
                    key: "active",
                    label: t("memory.status.active", "活跃"),
                    value: composition.status.active,
                    color: "#52c41a",
                  },
                  {
                    key: "deprecated",
                    label: t("memory.status.deprecated", "已废弃"),
                    value: composition.status.deprecated,
                    color: "#94a3b8",
                  },
                ]}
              />
            </div>
          )}
        </Card>

        <Card
          className={styles.chartCard}
          size="small"
          title={
            <span className={styles.chartTitle}>
              <PieChartIcon className={styles.chartTitleIcon} size={16} />
              {t("memory.overview.kindsTitle", "记忆类型分布")}
            </span>
          }
        >
          {loading && !kinds ? (
            <Skeleton active paragraph={{ rows: 4 }} />
          ) : !kinds || kinds.series.length === 0 ? (
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description={t("memory.overview.kindsEmpty", "暂无记忆类型数据")}
            />
          ) : (
            <div className={styles.chartBox}>
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={kinds.series}
                    dataKey="count"
                    nameKey="kind"
                    cx="35%"
                    innerRadius={44}
                    outerRadius={76}
                    paddingAngle={2}
                    stroke="none"
                  >
                    {kinds.series.map((entry) => (
                      <Cell
                        key={entry.kind}
                        fill={KIND_COLOR[entry.kind] ?? "#94a3b8"}
                      />
                    ))}
                  </Pie>
                  <RTooltip
                    formatter={(v, name) => [v, kindLabel(String(name), t)]}
                  />
                  <Legend
                    layout="vertical"
                    align="right"
                    verticalAlign="middle"
                    iconType="circle"
                    formatter={(value) => (
                      <span className={styles.legendItem}>
                        {kindLabel(String(value), t)}
                      </span>
                    )}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
          )}
        </Card>
      </div>

      {/* Bottom row: 14-day growth trend, full width */}
      <Card
        className={styles.chartCard}
        size="small"
        title={
          <span className={styles.chartTitle}>
            <BarChart3 className={styles.chartTitleIcon} size={16} />
            {t("memory.overview.growthTitle", "近 14 天新增趋势")}
          </span>
        }
      >
        {loading && !growth ? (
          <Skeleton active paragraph={{ rows: 4 }} />
        ) : !growth || growth.series.length === 0 ? (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description={t("memory.overview.growthEmpty", "近 14 天暂无新增")}
          />
        ) : (
          <div className={styles.compGrowthBox}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={growth.series}
                margin={{ top: 8, right: 8, bottom: 0, left: -16 }}
              >
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="var(--fn-border-secondary, #f0f0f0)"
                />
                <XAxis
                  dataKey="date"
                  tick={{
                    fontSize: 11,
                    fill: "var(--fn-text-tertiary, #8c8c8c)",
                  }}
                  tickFormatter={(d: string) => d.slice(5)}
                />
                <YAxis
                  allowDecimals={false}
                  tick={{
                    fontSize: 11,
                    fill: "var(--fn-text-tertiary, #8c8c8c)",
                  }}
                />
                <RTooltip
                  formatter={(v, name) => [v, growthLabel(String(name), t)]}
                />
                <Legend
                  iconType="circle"
                  formatter={(value) => (
                    <span className={styles.legendItem}>
                      {growthLabel(String(value), t)}
                    </span>
                  )}
                />
                <Bar dataKey="atoms" fill="#e85d75" radius={[4, 4, 0, 0]} />
                <Bar dataKey="entities" fill="#8b5cf6" radius={[4, 4, 0, 0]} />
                <Bar dataKey="episodes" fill="#f59e0b" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </Card>
    </section>
  );
}

interface DistSegment {
  key: string;
  label: string;
  value: number;
  color: string;
}

/** Vertical distribution block: label -> full-width progress bar -> horizontal legend. */
function DistRow({
  label,
  segments,
}: {
  label: string;
  segments: DistSegment[];
}) {
  const total = segments.reduce((sum, s) => sum + s.value, 0);
  return (
    <div className={styles.distBlock}>
      {/* Top: left-aligned dimension label */}
      <span className={styles.distBlockLabel}>{label}</span>

      {/* Progress bar: full-width segmented color bar */}
      <div className={styles.distBlockBar}>
        {total > 0 ? (
          segments
            .filter((s) => s.value > 0)
            .map((s) => (
              <Tooltip key={s.key} title={`${s.label}: ${s.value}`}>
                <div
                  className={styles.compSeg}
                  style={{
                    width: `${(s.value / total) * 100}%`,
                    background: s.color,
                  }}
                />
              </Tooltip>
            ))
        ) : (
          <div className={styles.compSegEmpty} />
        )}
      </div>

      {/* Bottom legend: color dot, label, and count */}
      <div className={styles.distBlockLegend}>
        {segments.map((s) => (
          <span key={s.key} className={styles.distBlockLegendItem}>
            <i className={styles.compDot} style={{ background: s.color }} />
            <span className={styles.distBlockLegendLabel}>{s.label}</span>
            <span
              className={styles.distBlockLegendValue}
              style={s.value > 0 ? { color: s.color } : undefined}
            >
              {s.value}
            </span>
          </span>
        ))}
      </div>
    </div>
  );
}

/** Compute confidence, importance, and status distribution from atom rows. */
function buildComposition(items: AtomItem[]): Composition {
  const confidence = { high: 0, medium: 0, low: 0 };
  const importance = { high: 0, medium: 0, low: 0 };
  const status = { active: 0, deprecated: 0 };
  for (const a of items) {
    if (isAtomDeprecated(a)) status.deprecated += 1;
    else status.active += 1;
    if (a.confidence === "high") confidence.high += 1;
    else if (a.confidence === "medium") confidence.medium += 1;
    else confidence.low += 1;
    if (a.importance === "high") importance.high += 1;
    else if (a.importance === "medium") importance.medium += 1;
    else importance.low += 1;
  }
  return { total: items.length, confidence, importance, status };
}

function KpiPill({
  tone,
  label,
  value,
  delta,
  loading,
  warn,
  valueSuffix,
}: {
  tone: Tone;
  label: string;
  value: number | undefined;
  delta?: number;
  loading: boolean;
  warn?: boolean;
  valueSuffix?: string;
}) {
  return (
    <div
      className={`${styles.kpiPill} ${styles[`tone_${tone}`]} ${
        warn ? styles.kpiPillWarn : ""
      }`}
    >
      <div className={styles.kpiLabel}>{label}</div>
      <div className={styles.kpiValueRow}>
        {loading && value === undefined ? (
          <Skeleton.Input
            active
            size="small"
            style={{ width: 40, height: 22, minHeight: 22 }}
          />
        ) : (
          <span className={styles.kpiValue}>
            {value ?? "-"}
            {value !== undefined && valueSuffix ? (
              <span className={styles.kpiValueSuffix}>{valueSuffix}</span>
            ) : null}
          </span>
        )}
        {delta !== undefined && delta > 0 ? (
          <span className={styles.kpiDelta}>+{delta}/7d</span>
        ) : null}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

type TFn = TFunction;

function kindLabel(k: string, t: TFn): string {
  switch (k) {
    case "Fact":
      return t("memory.kind.fact", "事实");
    case "Decision":
      return t("memory.kind.decision", "决定");
    case "Task":
      return t("memory.kind.task", "任务");
    case "Preference":
      return t("memory.kind.preference", "偏好");
    case "ConflictCandidate":
      return t("memory.kind.conflict", "可能矛盾");
    default:
      return k;
  }
}

function growthLabel(key: string, t: TFn): string {
  switch (key) {
    case "atoms":
      return t("memory.overview.atoms", "记忆条目");
    case "entities":
      return t("memory.overview.entities", "涉及人物/事物");
    case "episodes":
      return t("memory.overview.episodes", "经历");
    default:
      return key;
  }
}
