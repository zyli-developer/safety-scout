import { useState } from 'react';
import { View, Text } from '@tarojs/components';

import {
  SEVERITY_BG_TINT,
  SEVERITY_COLOR,
  SEVERITY_LABEL,
  SEVERITY_TEXT_ON_TINT,
} from '../../utils/severity';
import type { Hazard } from '../../types/report';
import { Icon } from '../Icon';

import styles from './index.module.scss';

export interface HazardCardProps {
  hazard: Hazard;
  /** 1-based 编号（可选）；与 total 一起显示为 "01 / 03"。 */
  index?: number;
  /** 总数；与 index 一起显示。 */
  total?: number;
}

export function HazardCard({ hazard, index, total }: HazardCardProps) {
  const [expanded, setExpanded] = useState(false);
  const hasRegulation = hazard.regulation.length > 0;
  const showIndex = typeof index === 'number';

  return (
    <View className={styles.card} data-category={hazard.category_code}>
      <View className={styles.header}>
        <View className={styles.headerLeft}>
          {showIndex && (
            <Text className={styles.indexBadge}>
              {String(index).padStart(2, '0')}
              {typeof total === 'number' ? ` / ${String(total).padStart(2, '0')}` : ''}
            </Text>
          )}
          <Text className={styles.categoryName}>{hazard.category_name}</Text>
        </View>
        <View
          className={styles.severityBadge}
          style={{
            backgroundColor: SEVERITY_BG_TINT[hazard.severity],
            color: SEVERITY_TEXT_ON_TINT[hazard.severity],
          }}
        >
          <View
            className={styles.severityDot}
            style={{ backgroundColor: SEVERITY_COLOR[hazard.severity] }}
          />
          <Text>{SEVERITY_LABEL[hazard.severity]}</Text>
        </View>
      </View>

      <Text className={styles.description}>{hazard.description}</Text>

      {hasRegulation && (
        <View
          className={styles.regulationToggle}
          onClick={() => setExpanded((v) => !v)}
          role="button"
        >
          <Text className={styles.regulationToggleLabel}>
            {expanded ? '收起规范条款' : '展开规范条款'}
          </Text>
          <Icon name={expanded ? 'chevron-up' : 'chevron-down'} size={20} color="#007AFF" />
        </View>
      )}
      {hasRegulation && expanded && (
        <View className={styles.regulation}>
          <Text>{hazard.regulation}</Text>
        </View>
      )}

      <View className={styles.suggestionDivider} />
      <View className={styles.suggestion}>
        <Text className={styles.suggestionLabel}>整改建议</Text>
        <Text className={styles.suggestionText}>{hazard.suggestion}</Text>
      </View>
    </View>
  );
}
