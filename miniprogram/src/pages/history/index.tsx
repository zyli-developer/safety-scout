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
import { getHistory, summarizeHistory, type HistoryEntry } from '../../utils/historyStore';
import { getPhotoFor } from '../../utils/lastPhotoStore';
import { relativeTime } from '../../utils/relativeTime';
import type { Severity } from '../../types/report';

import styles from './index.module.scss';

type SeverityFilter = 'all' | 'high' | 'medium' | 'low';

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

  const filtered = useMemo(() => {
    return entries.filter((e) => {
      if (filter !== 'all' && e.overallSeverity !== filter) return false;
      if (query.trim() && !e.summary.includes(query.trim())) return false;
      return true;
    });
  }, [entries, filter, query]);

  const counts = useMemo(() => {
    const acc = { all: entries.length, high: 0, medium: 0, low: 0 };
    for (const e of entries) acc[e.overallSeverity] += 1;
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
          <Text className={styles.rowMetaItem}>
            <Text className={styles.rowMetaB}>{entry.hazardCount}</Text> 项隐患
          </Text>
          <Text className={styles.rowMetaTime}>{relativeTime(new Date(entry.capturedAt).toISOString())}</Text>
        </View>
      </View>
      <View className={styles.rowCounts}>
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
      </View>
      <Icon name="chevron-right" size={16} color="var(--ink-3)" />
    </View>
  );
}
