/**
 * 报告页桌面端左 sticky 侧栏：标题块 + 隐患数 + 风险等级 + 现场总览 + plain_warning.
 *
 * sticky 定位由父容器（DesktopReport）的 grid 配合 position:sticky 实现；本组件不
 * 自己 sticky，只负责内容编排。
 */
import { View, Text } from '@tarojs/components';

import { SEVERITY_LABEL, SEVERITY_COLOR } from '../../../utils/severity';
import type { ReportPayload } from '../../../types/report';

import styles from './index.module.scss';

export interface ReportSidebarProps {
  report: ReportPayload;
  hazardCount: number;
}

export function ReportSidebar({ report, hazardCount }: ReportSidebarProps) {
  const severity = report.overall_severity;
  return (
    <View className={styles.sidebar}>
      <View className={styles.titleBlock}>
        <Text className={styles.eyebrow}>INSPECTION REPORT</Text>
        <Text className={styles.title}>现场巡检报告</Text>
      </View>

      <View className={styles.hero}>
        <View className={styles.heroRow}>
          <Text
            className={styles.heroCount}
            style={{ color: SEVERITY_COLOR[severity] }}
          >
            {hazardCount}
          </Text>
          <Text className={styles.heroCountLabel}>项隐患待整改</Text>
        </View>
        <View className={styles.heroRow}>
          <Text
            className={styles.heroSeverity}
            style={{ color: SEVERITY_COLOR[severity] }}
          >
            {SEVERITY_LABEL[severity]}
          </Text>
          <Text className={styles.heroSeverityLabel}>风险等级判定</Text>
        </View>
      </View>

      <View className={styles.summarySection}>
        <View className={styles.summaryLabel}>
          <Text className={styles.summaryLabelBar}>▎</Text>
          <Text className={styles.summaryLabelText}>现场总览</Text>
        </View>
        <Text className={styles.summaryText}>{report.summary}</Text>
        {report.plain_warning && (
          <Text className={styles.warning}>{report.plain_warning}</Text>
        )}
      </View>
    </View>
  );
}
