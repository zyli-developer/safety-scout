/**
 * HazardCard (dossier) —— 编号 + severity 条带 + 三栏标签。
 *
 * 形态：
 *   ┌──────────────────────────────────────┐
 *   │ 01 ·  HIGH  ·····················     │   ← header rule，编号 + severity tag
 *   │ 现象  |  高处作业未挂安全带          │
 *   │ 依据  |  GB 50656-2011 §3.2          │
 *   │ 整改  |  立即停工配发安全带          │
 *   │ ╲╲╲╲╲╲╲╲╲╲╲╲╲╲╲╲╲╲╲╲╲╲╲╲╲╲╲╲╲╲╲╲╲╲ │   ← bottom hazard-tape on severity color
 *   └──────────────────────────────────────┘
 *
 * 没有 expand toggle —— 直接展开。规范条款为空就省略整行。
 */
import { View, Text } from '@tarojs/components';

import { SEVERITY_COLOR, SEVERITY_LABEL, SEVERITY_TEXT_ON_TINT } from '../../utils/severity';
import type { Hazard } from '../../types/report';

import styles from './index.module.scss';

export interface HazardCardProps {
  hazard: Hazard;
  index?: number;
  total?: number;
}

const SEVERITY_TAG: Record<Hazard['severity'], string> = {
  high: 'HIGH',
  medium: 'MEDIUM',
  low: 'LOW',
};

export function HazardCard({ hazard, index, total }: HazardCardProps) {
  const hasIndex = typeof index === 'number';
  const hasRegulation = hazard.regulation.length > 0;
  return (
    <View className={styles.card} data-category={hazard.category_code}>
      <View className={styles.header}>
        {hasIndex && (
          <Text className={styles.index}>{String(index).padStart(2, '0')}</Text>
        )}
        <Text className={styles.dot}>·</Text>
        <Text
          className={styles.tag}
          data-severity-tag={hazard.severity}
          style={{ color: SEVERITY_TEXT_ON_TINT[hazard.severity] }}
        >
          {SEVERITY_TAG[hazard.severity]}
        </Text>
        <Text className={styles.headerRule}>
          {'·'.repeat(40)}
        </Text>
        {hasIndex && typeof total === 'number' && (
          <Text className={styles.indexOfTotal}>{`/ ${String(total).padStart(2, '0')}`}</Text>
        )}
      </View>

      <View className={styles.field}>
        <Text className={styles.fieldLabel}>现象</Text>
        <Text className={styles.fieldDivider}>|</Text>
        <Text className={styles.fieldValue}>{hazard.description}</Text>
      </View>

      {hasRegulation && (
        <View className={styles.field}>
          <Text className={styles.fieldLabel}>依据</Text>
          <Text className={styles.fieldDivider}>|</Text>
          <Text className={styles.fieldValue}>{hazard.regulation}</Text>
        </View>
      )}

      <View className={styles.field}>
        <Text className={styles.fieldLabel}>整改</Text>
        <Text className={styles.fieldDivider}>|</Text>
        <Text className={styles.fieldValue}>{hazard.suggestion}</Text>
      </View>

      <View
        className={styles.stripe}
        data-severity-stripe={hazard.severity}
        style={{ backgroundColor: SEVERITY_COLOR[hazard.severity] }}
      />
      <Text
        className={styles.metaTag}
        style={{ color: SEVERITY_TEXT_ON_TINT[hazard.severity] }}
      >
        {SEVERITY_LABEL[hazard.severity]} · {hazard.category_name}
      </Text>
    </View>
  );
}
