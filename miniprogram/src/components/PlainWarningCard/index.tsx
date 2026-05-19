import { View, Text } from '@tarojs/components';

import { SEVERITY_COLOR, SEVERITY_LABEL } from '../../utils/severity';
import type { Severity } from '../../types/report';

import styles from './index.module.scss';

export interface PlainWarningCardProps {
  text: string;
  severity: Severity;
}

export function PlainWarningCard({ text, severity }: PlainWarningCardProps) {
  return (
    <View
      className={styles.card}
      style={{ backgroundColor: SEVERITY_COLOR[severity] }}
      data-severity={severity}
    >
      <View className={styles.decorCircle} />
      <View className={styles.header}>
        <Text className={styles.icon}>⚠️</Text>
        <Text className={styles.severityLabel}>{SEVERITY_LABEL[severity]}</Text>
      </View>
      <Text className={styles.text}>{text}</Text>
    </View>
  );
}
