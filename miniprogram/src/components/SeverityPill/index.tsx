/**
 * SeverityPill — high/medium/low 严重度 pill。
 * variant='soft' (default) 用在列表 row、概要卡里；'solid' 用在大报告 hero 处。
 * count 可选 —— 加在标签后面（如 "高风险 · 3"）。
 */
import { View, Text } from '@tarojs/components';

import { SEVERITY_LABEL } from '../../utils/severity';
import type { Severity } from '../../types/report';

import styles from './index.module.scss';

export interface SeverityPillProps {
  level: Severity;
  variant?: 'soft' | 'solid';
  count?: number;
  className?: string;
}

export function SeverityPill({ level, variant = 'soft', count, className }: SeverityPillProps) {
  const cls = [
    variant === 'solid' ? styles.solid : styles.soft,
    styles[level],
    className,
  ]
    .filter(Boolean)
    .join(' ');
  const text = count != null ? `${SEVERITY_LABEL[level]} · ${count}` : SEVERITY_LABEL[level];
  return (
    <View className={cls} data-sev={level} data-variant={variant}>
      {variant === 'soft' && <View className={styles.dot} />}
      <Text className={styles.label}>{text}</Text>
    </View>
  );
}
