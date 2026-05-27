/**
 * QualityPage — 质量趋势 dashboard（docs/specs/quality-tracking.md §5.2）。
 *
 * 4 张卡片：judge_win_rate / p50_latency / output_tokens / finding_count
 * 每张按 prompt_version 分桶；用纯 SVG mini-bar 渲染（不引图表库）。
 *
 * 数据源：GET /api/v1/quality/trend，每个 metric 一次请求 → 4 个并发拉取。
 * 失败时单卡显示 err，其余卡继续渲染（部分降级）。
 *
 * 入口：通过 history 页 header 的"质量趋势"小链接进入。**不**在 TopNav 加
 * 第 3 个 tab（与 TopNav 注释"2-tab 设计、违反产品只做三步主张"对齐）。
 */
import { View, Text } from '@tarojs/components';
import { useEffect, useState } from 'react';

import { fetchQualityTrend, type QualityGroupBy, type QualityMetric, type QualityTrendResponse } from '../../api/quality';
import { ApiError } from '../../api/client';

import styles from './index.module.scss';

const METRICS: Array<{ id: QualityMetric; title: string; format: (n: number) => string }> = [
  { id: 'judge_win_rate', title: 'Judge 胜率（vs baseline）', format: (n) => `${(n * 100).toFixed(0)}%` },
  { id: 'p50_latency', title: 'p50 延迟', format: (n) => `${(n / 1000).toFixed(1)}s` },
  { id: 'output_tokens', title: 'p50 输出 tokens', format: (n) => Math.round(n).toString() },
  { id: 'finding_count', title: 'p50 隐患数', format: (n) => n.toFixed(1) },
];

const GROUP_BYS: Array<{ id: QualityGroupBy; label: string }> = [
  { id: 'prompt_version', label: '按 prompt 版本' },
  { id: 'model', label: '按 model' },
  { id: 'day', label: '按日期' },
];

type Loadable<T> =
  | { state: 'loading' }
  | { state: 'success'; data: T }
  | { state: 'error'; message: string };

/**
 * MiniBarChart —— 极简 SVG 横向柱状图。
 * 每个 series point 一条 bar，高度按 max 归一；标签写桶名 + 格式化数值。
 * 不引图表库（设计约束 §5.2）；~40 行实现，对 80px 高的卡片足够清晰。
 */
function MiniBarChart({
  series,
  format,
}: {
  series: QualityTrendResponse['series'];
  format: (n: number) => string;
}) {
  if (series.length === 0) {
    return <Text className={styles.empty}>暂无数据</Text>;
  }

  const max = Math.max(...series.map((s) => s.value));
  const safeMax = max === 0 ? 1 : max;
  // 简化布局：水平 bar，标签在右
  return (
    <View className={styles.legend}>
      {series.map((s) => {
        const pct = (s.value / safeMax) * 100;
        return (
          <View key={s.group} className={styles.legendItem}>
            <View
              className={styles.legendSwatch}
              style={{
                background: 'var(--accent, #d96322)',
                width: `${Math.max(pct, 4)}px`,
                height: '10px',
                borderRadius: '2px',
              }}
              aria-hidden
            />
            <Text>{s.group}</Text>
            <Text className={styles.legendValue}>{format(s.value)}</Text>
            <Text>·</Text>
            <Text>{`n=${s.n}`}</Text>
          </View>
        );
      })}
    </View>
  );
}

function MetricCard({
  title,
  data,
  format,
}: {
  title: string;
  data: Loadable<QualityTrendResponse>;
  format: (n: number) => string;
}) {
  let body: JSX.Element;
  let nText = '';
  if (data.state === 'loading') {
    body = <Text className={styles.loading}>加载中…</Text>;
  } else if (data.state === 'error') {
    body = <View className={styles.errBox}><Text>{data.message}</Text></View>;
  } else {
    body = <MiniBarChart series={data.data.series} format={format} />;
    const total = data.data.series.reduce((acc, s) => acc + s.n, 0);
    nText = `共 ${total} 个样本`;
  }
  return (
    <View className={styles.card}>
      <View className={styles.cardHead}>
        <Text className={styles.cardTitle}>{title}</Text>
        {nText && <Text className={styles.cardN}>{nText}</Text>}
      </View>
      <View className={styles.chartBox}>{body}</View>
    </View>
  );
}

export default function QualityPage() {
  const [groupBy, setGroupBy] = useState<QualityGroupBy>('prompt_version');
  const [cards, setCards] = useState<Record<QualityMetric, Loadable<QualityTrendResponse>>>(
    () =>
      Object.fromEntries(METRICS.map((m) => [m.id, { state: 'loading' }])) as Record<
        QualityMetric,
        Loadable<QualityTrendResponse>
      >,
  );

  useEffect(() => {
    let cancelled = false;
    // 全部重置为 loading 再并发拉
    setCards(
      Object.fromEntries(METRICS.map((m) => [m.id, { state: 'loading' }])) as Record<
        QualityMetric,
        Loadable<QualityTrendResponse>
      >,
    );
    Promise.all(
      METRICS.map(async (m) => {
        try {
          const resp = await fetchQualityTrend(m.id, groupBy);
          if (!cancelled) {
            setCards((prev) => ({ ...prev, [m.id]: { state: 'success', data: resp } }));
          }
        } catch (err) {
          if (cancelled) return;
          const msg =
            err instanceof ApiError
              ? `${err.code}: ${err.userMessage}`
              : '加载失败';
          setCards((prev) => ({ ...prev, [m.id]: { state: 'error', message: msg } }));
        }
      }),
    );
    return () => {
      cancelled = true;
    };
  }, [groupBy]);

  return (
    <View className={styles.page}>
      <View className={styles.container}>
        <View className={styles.head}>
          <Text className={styles.h1}>质量趋势</Text>
          <Text className={styles.sub}>最近 30 天</Text>
        </View>

        <View className={styles.filterRow}>
          <Text className={styles.filterLabel}>分组：</Text>
          {GROUP_BYS.map((g) => (
            <View
              key={g.id}
              className={[styles.chip, g.id === groupBy ? styles.chipActive : ''].filter(Boolean).join(' ')}
              role="button"
              aria-pressed={g.id === groupBy}
              onClick={() => setGroupBy(g.id)}
            >
              <Text>{g.label}</Text>
            </View>
          ))}
        </View>

        <View className={styles.grid}>
          {METRICS.map((m) => (
            <MetricCard
              key={m.id}
              title={m.title}
              data={cards[m.id]}
              format={m.format}
            />
          ))}
        </View>
      </View>
    </View>
  );
}
