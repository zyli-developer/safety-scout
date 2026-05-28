/**
 * HistoryPage — 巡检历史列表（B8 · localStorage 临时方案）。
 *
 * 对齐 docs/plans/2026-05-22-unified-modern-minimal/history.html 主要 UX：
 *   - 顶部 h1 "巡检报告" + 副 "近 N 次 · M 处高风险待整改" + 新建巡检按钮
 *   - summary strip 4 cell（本周巡检 / 高风险 / 整改完成 / 总计）
 *   - toolbar：search input + severity filter chips（"全部 / 高 / 中 / 低"）
 *   - row list 按时间倒序，含缩略 + warn + meta + severity counts pill
 *
 * 未做（简化版）：
 *   - daygroup sticky + dayhead（按日期分组），改用 flat list 按 capturedAt 倒序
 *   - "+ 加筛选"浮层（4 组：时间/严重度/状态/类别）→ 简化为单层 severity chip
 *   - search 暂为视觉占位，filter chip 已联动 list
 *
 * 数据源：historyStore (localStorage)，与 lastPhotoStore 共享设备本地数据。
 * 后端 list endpoint 上线后整页改读 API。
 */
import Taro from '@tarojs/taro';
import { View, Text } from '@tarojs/components';
import { useEffect, useMemo, useState } from 'react';

import { TopNav } from '../../components/TopNav';
import { Icon } from '../../components/Icon';
import { SeverityPill } from '../../components/SeverityPill';
import { EmptyState } from '../../components/EmptyState';
import { Button } from '../../components/Button';
import { appendHistory, getHistory, summarizeHistory, type HistoryEntry } from '../../utils/historyStore';
import { getPhotoFor } from '../../utils/lastPhotoStore';
import { relativeTime } from '../../utils/relativeTime';
import { getInspection } from '../../api/inspections';
import { mapV2ReportToV1 } from '../../utils/v2Adapter';
import type { Severity, ReportPayload } from '../../types/report';
import type { ReportV2Payload } from '../../types/report-v2';

import styles from './index.module.scss';

type SeverityFilter = 'all' | 'high' | 'medium' | 'low';

// 每 5s 轮询一次 analyzing 条目；与 ProgressTracker 的现场感节奏对齐，
// 也不会对后端 GET 端点造成压力（每条 analyzing inspection 一次请求）。
const ANALYZING_POLL_MS = 5000;

export default function HistoryPage() {
  const [entries, setEntries] = useState<HistoryEntry[]>([]);
  const [summary, setSummary] = useState(() => summarizeHistory());
  const [filter, setFilter] = useState<SeverityFilter>('all');
  const [query, setQuery] = useState('');

  // 进入页面时刷一次。didShow 类似 React useEffect []，保证从其他页返回时数据新鲜。
  useEffect(() => {
    setEntries(getHistory());
    setSummary(summarizeHistory());
  }, []);

  // 2026-05-26：自动轮询升级 analyzing 条目 —— 用户中途回到首页 / 进 history
  // 时不必再手动点回报告页，history 自己每 5s 查后端一次，命中 succeeded/failed
  // 即写入完整数据。修复 #2 报告：「等了很久没新结果」。
  useEffect(() => {
    const analyzing = entries.filter((e) => e.analysisStatus === 'analyzing');
    if (analyzing.length === 0) return;

    let cancelled = false;

    const tick = async () => {
      for (const entry of analyzing) {
        if (cancelled) return;
        try {
          const r = await getInspection(
            entry.inspectionId,
            entry.schemaVersion ?? 'v1',
          );
          if (cancelled) return;
          if (r.status === 'succeeded' && r.report) {
            // v2 报告先经 adapter 转回 v1 shape，再做 breakdown 统计
            const v1Report: ReportPayload =
              entry.schemaVersion === 'v2'
                ? mapV2ReportToV1(
                    r.report as ReportV2Payload,
                    entry.inspectionId,
                    r.created_at,
                  )
                : (r.report as ReportPayload);
            const breakdown = { high: 0, medium: 0, low: 0 } as Record<Severity, number>;
            for (const h of v1Report.hazards) breakdown[h.severity] += 1;
            appendHistory({
              inspectionId: entry.inspectionId,
              capturedAt: Date.parse(r.created_at) || entry.capturedAt,
              summary: v1Report.summary,
              overallSeverity: v1Report.overall_severity,
              hazardCount: v1Report.hazards.length,
              breakdown,
              status: 'pending',
              schemaVersion: entry.schemaVersion,
              analysisStatus: 'succeeded',
            });
          } else if (r.status === 'failed') {
            appendHistory({
              inspectionId: entry.inspectionId,
              capturedAt: Date.parse(r.created_at) || entry.capturedAt,
              summary: r.error?.user_message ?? '分析失败',
              overallSeverity: 'low',
              hazardCount: 0,
              breakdown: { high: 0, medium: 0, low: 0 },
              status: 'pending',
              schemaVersion: entry.schemaVersion,
              analysisStatus: 'failed',
            });
          }
        } catch {
          // 单次 poll 失败（网络抖动 / 后端临时 5xx）下次再试，不打断 interval
        }
      }
      if (!cancelled) {
        setEntries(getHistory());
        setSummary(summarizeHistory());
      }
    };

    // 立刻先 tick 一次（用户进页面时有 stale analyzing entry 的话最快秒级生效）
    tick();
    const interval = setInterval(tick, ANALYZING_POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
    // entries 变化时重启 effect —— 新 analyzing 加进来要轮询、resolved 出去要停。
    // 用 join(',') 做稳定字符串依赖避免对 entries 引用变化触发不必要重启。
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [entries.filter((e) => e.analysisStatus === 'analyzing').map((e) => e.inspectionId).join(',')]);

  const filtered = useMemo(() => {
    return entries.filter((e) => {
      if (filter !== 'all' && e.overallSeverity !== filter) return false;
      if (query.trim() && !e.summary.includes(query.trim())) return false;
      return true;
    });
  }, [entries, filter, query]);

  // chip counts 排除 analyzing/failed 条目 —— 它们的 overallSeverity 是 placeholder='low'，
  // 计入"低"会让用户误以为有低风险已分析报告。所有 analyzing/failed 单独 badge 展示。
  const counts = useMemo(() => {
    const ready = entries.filter((e) => e.analysisStatus !== 'analyzing' && e.analysisStatus !== 'failed');
    const acc = { all: ready.length, high: 0, medium: 0, low: 0 };
    for (const e of ready) acc[e.overallSeverity] += 1;
    return acc;
  }, [entries]);

  const onNewInspection = () => {
    Taro.reLaunch({ url: '/pages/index/index' });
  };

  return (
    <View className={styles.page}>
      <TopNav
        activeTab="reports"
        onTabChange={(tab) => {
          if (tab === 'inspect') Taro.reLaunch({ url: '/pages/index/index' });
        }}
      />

      <View className={styles.container}>
        <View className={styles.head}>
          <View className={styles.headLeft}>
            <Text className={styles.h1}>巡检报告</Text>
            <Text className={styles.sub}>
              {entries.length === 0
                ? '还没有巡检记录，开始第一次拍照吧'
                : `本机共 ${entries.length} 次巡检 · ${counts.high} 处高风险`}
            </Text>
            {/*
              质量趋势入口（docs/specs/quality-tracking.md §5.2）。
              低调链接而非 TopNav 第三 tab —— 守 TopNav 2-tab 设计、不暴露给安全员日常使用。
            */}
            <View
              className={styles.qualityLink}
              role="button"
              aria-label="进入质量趋势 dashboard"
              onClick={() => Taro.navigateTo({ url: '/pages/quality/index' })}
            >
              <Text>质量趋势 →</Text>
            </View>
          </View>
          <Button variant="primary" onTap={onNewInspection}>
            <Icon name="camera" size={16} color="var(--on-accent)" />
            <Text className={styles.btnText}>新建巡检</Text>
          </Button>
        </View>

        {entries.length === 0 ? (
          <EmptyState
            variant="empty"
            primaryAction={{ label: '拍第一张', onTap: onNewInspection }}
          />
        ) : (
          <>
            <View className={styles.summary}>
              <SummaryCell label="本机总数" num={summary.total} />
              <SummaryCell label="近 7 天" num={summary.weekly} />
              <SummaryCell label="高风险" num={summary.highRisk} tone="high" />
              <SummaryCell label="已闭环" num={summary.closed} tone="low" />
            </View>

            <View className={styles.toolbar}>
              <View className={styles.search}>
                <Icon name="search" size={16} color="var(--ink-3)" />
                <input
                  className={styles.searchInput}
                  type="search"
                  placeholder="搜索：外架 / 临边 / 用电…"
                  value={query}
                  onInput={(e) => setQuery((e.target as HTMLInputElement).value ?? '')}
                />
              </View>
              <View className={styles.chips} role="tablist">
                <Chip
                  label="全部"
                  count={counts.all}
                  active={filter === 'all'}
                  onTap={() => setFilter('all')}
                />
                <Chip
                  label="高"
                  count={counts.high}
                  active={filter === 'high'}
                  onTap={() => setFilter('high')}
                  sev="high"
                />
                <Chip
                  label="中"
                  count={counts.medium}
                  active={filter === 'medium'}
                  onTap={() => setFilter('medium')}
                  sev="medium"
                />
                <Chip
                  label="低"
                  count={counts.low}
                  active={filter === 'low'}
                  onTap={() => setFilter('low')}
                  sev="low"
                />
              </View>
            </View>

            {filtered.length === 0 ? (
              <View className={styles.emptyFilter}>
                <Text>当前筛选下没有记录</Text>
              </View>
            ) : (
              <View className={styles.list}>
                {filtered.map((e) => (
                  <HistoryRow key={e.inspectionId} entry={e} />
                ))}
              </View>
            )}
          </>
        )}
      </View>
    </View>
  );
}

function SummaryCell({
  label,
  num,
  tone,
}: {
  label: string;
  num: number;
  tone?: 'high' | 'low';
}) {
  const numCls = [
    styles.summaryNum,
    tone === 'high' ? styles.summaryNumHigh : '',
    tone === 'low' ? styles.summaryNumLow : '',
  ]
    .filter(Boolean)
    .join(' ');
  return (
    <View className={styles.summaryCell}>
      <Text className={styles.summaryLabel}>{label}</Text>
      <Text className={numCls}>{num}</Text>
    </View>
  );
}

function Chip({
  label,
  count,
  active,
  sev,
  onTap,
}: {
  label: string;
  count: number;
  active: boolean;
  sev?: Severity;
  onTap: () => void;
}) {
  const disabled = count === 0 && label !== '全部';
  const cls = [
    styles.chip,
    active ? styles.chipActive : '',
    disabled ? styles.chipDisabled : '',
  ]
    .filter(Boolean)
    .join(' ');
  return (
    <View
      className={cls}
      role="tab"
      aria-selected={active}
      aria-disabled={disabled ? 'true' : undefined}
      onClick={disabled ? undefined : onTap}
    >
      {sev && <View className={[styles.chipDot, styles[`chipDot${sev}`]].join(' ')} />}
      <Text>
        {label} <Text className={styles.chipCount}>{count}</Text>
      </Text>
    </View>
  );
}

function HistoryRow({ entry }: { entry: HistoryEntry }) {
  const photo = getPhotoFor(entry.inspectionId);
  const isAnalyzing = entry.analysisStatus === 'analyzing';
  const isFailed = entry.analysisStatus === 'failed';
  const onTap = () => {
    // v2 inspection 必须带 ?v=2 —— 否则 report 页按 v1 调 GET /api/v1/...
    // 后端 v2 路由会 404（schema_version 隔离）。缺省（undefined）按 v1 处理，
    // 与历史无 schemaVersion 字段的本地缓存条目兼容。
    const vParam = entry.schemaVersion === 'v2' ? '&v=2' : '';
    Taro.navigateTo({
      url: `/pages/report/index?id=${entry.inspectionId}${vParam}`,
    });
  };
  return (
    <View className={styles.row} role="button" onClick={onTap}>
      <View
        className={styles.rowThumb}
        style={{
          background: photo?.src
            ? `url(${photo.src}) center / cover no-repeat`
            : undefined,
        }}
      />
      <View className={styles.rowBody}>
        <Text className={styles.rowWarn}>{entry.summary}</Text>
        <View className={styles.rowMeta}>
          {!isAnalyzing && !isFailed && (
            <Text className={styles.rowMetaItem}>
              <Text className={styles.rowMetaB}>{entry.hazardCount}</Text> 项隐患
            </Text>
          )}
          <Text className={styles.rowMetaTime}>{relativeTime(new Date(entry.capturedAt).toISOString())}</Text>
        </View>
      </View>
      <View className={styles.rowCounts}>
        {/* analysisStatus 优先于 severity 渲染：分析中 → 旋转点；失败 → 红色 badge；
            成功（含 undefined 老条目）→ 走原 severity pill 渲染 */}
        {isAnalyzing && (
          <View className={styles.analyzingBadge} aria-label="分析中">
            <View className={styles.analyzingDot} />
            <Text>分析中</Text>
          </View>
        )}
        {isFailed && (
          <View className={styles.failedBadge} aria-label="分析失败">
            <Text>失败</Text>
          </View>
        )}
        {!isAnalyzing && !isFailed && (
          <>
            {entry.breakdown.high > 0 && (
              <SeverityPill level="high" count={entry.breakdown.high} />
            )}
            {entry.breakdown.medium > 0 && (
              <SeverityPill level="medium" count={entry.breakdown.medium} />
            )}
            {entry.breakdown.low > 0 && (
              <SeverityPill level="low" count={entry.breakdown.low} />
            )}
            {entry.hazardCount === 0 && <Text className={styles.rowPass}>✓ 通过</Text>}
          </>
        )}
      </View>
      <Icon name="chevron-right" size={16} color="var(--ink-3)" />
    </View>
  );
}
