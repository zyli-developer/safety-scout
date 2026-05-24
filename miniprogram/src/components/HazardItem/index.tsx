/**
 * HazardItem — 隐患明细列表 row（替代旧 HazardCard 卡片形态）。
 * 三列布局：编号(40px) / 主体(1fr) / 行动按钮(auto)。
 * 主体里：类别 + 严重度 pill 一行 + 现象描述 + meta（code · regulation） + 可选的整改建议块。
 */
import { View, Text } from '@tarojs/components';

import { Icon } from '../Icon';
import { SeverityPill } from '../SeverityPill';
import type { Hazard } from '../../types/report';

import styles from './index.module.scss';

export interface HazardItemProps {
  hazard: Hazard;
  /** 1-indexed 序号；显示为 "01" / "02"。 */
  index: number;
  /** 是否展开"整改建议"块，默认 true。 */
  showFix?: boolean;
  onAction?: () => void;
  className?: string;
}

export function HazardItem({
  hazard,
  index,
  showFix = true,
  onAction,
  className,
}: HazardItemProps) {
  const { severity, description, regulation, suggestion, category_name, category_code } = hazard;
  const hasReg = regulation.length > 0;
  return (
    <View className={[styles.row, className].filter(Boolean).join(' ')} data-severity={severity}>
      <View className={styles.idx}>
        <Text>{String(index).padStart(2, '0')}</Text>
      </View>
      <View className={styles.body}>
        <View className={styles.head}>
          <Text className={styles.cat}>{category_name}</Text>
          <SeverityPill level={severity} />
        </View>
        <Text className={styles.desc}>{description}</Text>
        <View className={styles.meta}>
          <Text>{category_code}</Text>
          {hasReg && (
            <>
              <Text className={styles.sep}>·</Text>
              <Text>{regulation}</Text>
            </>
          )}
        </View>
        {showFix && (
          // 2026-05-24：对齐 mockup .suggestion-callout —— accent-soft 橙色块 + 左 icon，
          // 与 report.html 列表里的整改建议视觉同源。
          <View className={styles.fix}>
            <View className={styles.fixIcon}>
              <Icon name="tick" size={16} color="var(--accent)" />
            </View>
            <View className={styles.fixContent}>
              <Text className={styles.fixLabel}>整改建议 · </Text>
              <Text className={styles.fixBody}>{suggestion}</Text>
            </View>
          </View>
        )}
      </View>
      <View
        className={styles.action}
        onClick={onAction}
        role={onAction ? 'button' : undefined}
        aria-label={onAction ? '查看详情' : undefined}
      >
        <Icon name="chevron-right" size={16} color="var(--ink-3)" />
      </View>
    </View>
  );
}
