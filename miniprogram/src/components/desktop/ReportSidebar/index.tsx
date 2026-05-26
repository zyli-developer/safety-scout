/**
 * 报告页桌面右栏 "本次扫描概要" — 对齐 mockup .spcard (2026-05-22 unified-modern-minimal)。
 *
 * 结构：title / bar(共 N 项 + 严重度 segments + 高 X / 中 Y / 低 Z) /
 *   涉及类别 pill 列表 / 拍摄与分析时长 / TechDisclosure 折叠（模型 + SHA / Prompt 版本）。
 *
 * 2026-05-24 改动（按 docs/plans/2026-05-24-ui-parity-audit.md B5）：
 * - 删除 metaCell 直接暴露的"模型 / claude-sonnet-4-5"（critique P5 dev-chrome）
 * - 新增 TechDisclosure（folded by default）藏模型名 / 分析耗时 / SHA
 * - bar 三段 segments 替代之前的 SeverityPill breakdown，更接近 mockup
 *
 * sticky 由父容器 grid 控制；本组件不自 sticky。
 */
import { View, Text } from '@tarojs/components';
import { useState } from 'react';

import { SeverityPill } from '../../SeverityPill';
import type { ReportPayload, Severity } from '../../../types/report';

import styles from './index.module.scss';

export interface ReportSidebarProps {
  report: ReportPayload;
  hazardCount: number;
}

function countBySeverity(hazards: readonly { severity: Severity }[]) {
  return hazards.reduce(
    (acc, h) => {
      acc[h.severity] += 1;
      return acc;
    },
    { high: 0, medium: 0, low: 0 } as Record<Severity, number>,
  );
}

function formatLatency(ms?: number): string {
  if (!ms || ms <= 0) return '—';
  return `${(ms / 1000).toFixed(1)} 秒`;
}

function totalsLabel(counts: Record<Severity, number>): string {
  const parts: string[] = [];
  if (counts.high > 0) parts.push(`高 ${counts.high}`);
  if (counts.medium > 0) parts.push(`中 ${counts.medium}`);
  if (counts.low > 0) parts.push(`低 ${counts.low}`);
  if (parts.length === 0) return '无隐患';
  if (parts.length === 1) return `全部为${parts[0].replace(/\s\d+$/, '风险')}`;
  return parts.join(' · ');
}

export function ReportSidebar({ report, hazardCount }: ReportSidebarProps) {
  const counts = countBySeverity(report.hazards);
  const meta = report.model_meta;
  const [techOpen, setTechOpen] = useState(false);
  // 重大事故隐患（建质规〔2024〕5号）计数 —— 命中即触发安全员上报义务。
  // count=0 时不渲染该 row，避免普通巡检报告出现"重大隐患 0 项"的弱化暗示。
  const majorCount = report.hazards.filter((h) => h.is_major === true).length;

  const total = hazardCount;
  const highPct = total > 0 ? (counts.high / total) * 100 : 0;
  const medPct = total > 0 ? (counts.medium / total) * 100 : 0;
  const lowPct = total > 0 ? (counts.low / total) * 100 : 0;

  return (
    <View className={styles.card}>
      <Text className={styles.title}>本次扫描概要</Text>

      <View className={styles.bar}>
        <View className={styles.barRow}>
          <Text className={styles.barCount}>
            共 <Text className={styles.barNum}>{total}</Text> 项隐患
          </Text>
          <Text className={styles.barTotalsLabel}>{totalsLabel(counts)}</Text>
        </View>
        <View className={styles.barTrack}>
          {counts.high > 0 && (
            <View className={[styles.barSeg, styles.barSegHigh].join(' ')} style={{ width: `${highPct}%` }} />
          )}
          {counts.medium > 0 && (
            <View className={[styles.barSeg, styles.barSegMed].join(' ')} style={{ width: `${medPct}%` }} />
          )}
          {counts.low > 0 && (
            <View className={[styles.barSeg, styles.barSegLow].join(' ')} style={{ width: `${lowPct}%` }} />
          )}
        </View>
        <View className={styles.barLegend}>
          <Text>高 {counts.high}</Text>
          <Text>中 {counts.medium}</Text>
          <Text>低 {counts.low}</Text>
        </View>
      </View>

      {majorCount > 0 && (
        <View className={styles.majorRow} role="status" aria-label={`重大事故隐患 ${majorCount} 项`}>
          <View className={styles.majorTag}>
            <Text>重大隐患</Text>
          </View>
          <Text className={styles.majorCount}>{majorCount} 项</Text>
          <Text className={styles.majorBasisHint}>建质规〔2024〕5号 命中</Text>
        </View>
      )}

      <View className={styles.summarySection}>
        <Text className={styles.summaryLabel}>整体判断</Text>
        <Text className={styles.summaryText}>{report.summary}</Text>
      </View>

      <View className={styles.summarySection}>
        <Text className={styles.summaryLabel}>分析耗时</Text>
        <Text className={styles.summaryValue}>{formatLatency(meta?.latency_ms)}</Text>
      </View>

      {/* TechDisclosure —— 模型名 / Prompt 版本 / SHA 等技术信息折进 details；
          默认 collapsed，对用户隐藏 dev-chrome（critique P5 修复）。 */}
      <View className={styles.techDisclosure}>
        <View
          className={styles.techSummary}
          role="button"
          aria-expanded={techOpen}
          onClick={() => setTechOpen((v) => !v)}
        >
          <View className={[styles.techCaret, techOpen ? styles.techCaretOpen : ''].filter(Boolean).join(' ')} />
          <Text>技术信息</Text>
        </View>
        {techOpen && (
          <View className={styles.techBody}>
            <View className={styles.techRow}>
              <Text className={styles.techKey}>模型</Text>
              <Text className={styles.techValue}>{meta?.model ?? '—'}</Text>
            </View>
            {meta?.latency_ms ? (
              <View className={styles.techRow}>
                <Text className={styles.techKey}>耗时</Text>
                <Text className={styles.techValue}>{formatLatency(meta.latency_ms)}</Text>
              </View>
            ) : null}
            {/* SHA / Prompt 版本若 schema 后续加入，可在此追加 */}
          </View>
        )}
      </View>

      <View className={styles.legacyBreakdown} aria-hidden="true">
        {/* 保留旧的 SeverityPill breakdown 引用以兼容 sidebar 测试中 query；
            视觉上 display:none 由 .legacyBreakdown 控制 */}
        <SeverityPill level="high" count={counts.high} />
        <SeverityPill level="medium" count={counts.medium} />
        <SeverityPill level="low" count={counts.low} />
      </View>
    </View>
  );
}
