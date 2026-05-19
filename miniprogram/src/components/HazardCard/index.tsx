import { useState } from 'react';
import { View, Text } from '@tarojs/components';
import { SEVERITY_COLOR, SEVERITY_LABEL } from '../../utils/severity';
import type { Hazard } from '../../types/report';
import styles from './index.module.scss';

export interface HazardCardProps {
  hazard: Hazard;
}

export function HazardCard({ hazard }: HazardCardProps) {
  const [expanded, setExpanded] = useState(false);
  const hasRegulation = hazard.regulation.length > 0;

  return (
    <View className={styles.card} data-category={hazard.category_code}>
      <View className={styles.header}>
        <Text className={styles.categoryName}>{hazard.category_name}</Text>
        <Text
          className={styles.severityBadge}
          style={{ backgroundColor: SEVERITY_COLOR[hazard.severity] }}
        >
          {SEVERITY_LABEL[hazard.severity]}
        </Text>
      </View>

      <Text className={styles.description}>{hazard.description}</Text>

      {hasRegulation && (
        <View
          className={styles.regulationToggle}
          onClick={() => setExpanded((v) => !v)}
          role="button"
        >
          <Text>{expanded ? '收起规范条款' : '展开规范条款'}</Text>
        </View>
      )}
      {hasRegulation && expanded && (
        <View className={styles.regulation}>
          <Text>{hazard.regulation}</Text>
        </View>
      )}

      <View className={styles.suggestion}>
        <Text className={styles.suggestionLabel}>整改建议：</Text>
        <Text className={styles.suggestionText}>{hazard.suggestion}</Text>
      </View>
    </View>
  );
}
