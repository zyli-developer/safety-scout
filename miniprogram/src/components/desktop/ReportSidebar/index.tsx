/**
 * 报告页桌面右栏概要卡 — clean-minimal 重排。
 *
 * eyebrow + 大数字 + 项 + SeverityPills(high/medium/low breakdown) + summary +
 * meta（分析耗时 / 模型）。plain_warning 不再在此渲染（移到页面全宽 AlarmBox）。
 * sticky 定位由父容器（DesktopReport）的 grid 控制；本组件不自 sticky。
 */
import { View, Text } from '@tarojs/components';

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

export function ReportSidebar({ report, hazardCount }: ReportSidebarProps) {
  const counts = countBySeverity(report.hazards);
  const meta = report.model_meta;
  return (
    <View className={styles.card}>
      <Text className={styles.eyebrow}>巡检概要</Text>

      <View className={styles.countRow}>
        <Text className={styles.count}>{hazardCount}</Text>
        <Text className={styles.countUnit}>项隐患</Text>
      </View>

      <View className={styles.breakdown}>
        <SeverityPill level="high" count={counts.high} />
        <SeverityPill level="medium" count={counts.medium} />
        <SeverityPill level="low" count={counts.low} />
      </View>

      <Text className={styles.summary}>{report.summary}</Text>

      <View className={styles.metaGrid}>
        <View className={styles.metaCell}>
          <Text className={styles.metaLabel}>分析耗时</Text>
          <Text className={styles.metaValue}>{formatLatency(meta?.latency_ms)}</Text>
        </View>
        <View className={styles.metaCell}>
          <Text className={styles.metaLabel}>模型</Text>
          <Text className={styles.metaValue}>{meta?.model ?? '—'}</Text>
        </View>
      </View>
    </View>
  );
}
