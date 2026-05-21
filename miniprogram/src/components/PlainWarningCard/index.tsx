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
    <View className={styles.card}>
      <View
        className={styles.accentBar}
        style={{ backgroundColor: SEVERITY_COLOR[severity] }}
        data-severity={severity}
      />
      <View className={styles.body}>
        <Text
          className={styles.severityLabel}
          style={{ color: SEVERITY_COLOR[severity] }}
        >
          {SEVERITY_LABEL[severity]}
        </Text>
        <Text className={styles.text}>{text}</Text>
      </View>
    </View>
  );
}
