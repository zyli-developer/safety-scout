/**
 * AlarmBox — 红软底警示条，左侧实心红圆里塞个 '!'，右侧 lead label + body 文字。
 * 用于报告页 plain_warning 字段。
 */
import { View, Text } from '@tarojs/components';
import type { ReactNode } from 'react';

import styles from './index.module.scss';

export interface AlarmBoxProps {
  children: ReactNode;
  /** 左侧粗体导语，默认 "立即处置"。 */
  leadLabel?: string;
  className?: string;
}

export function AlarmBox({ children, leadLabel = '立即处置', className }: AlarmBoxProps) {
  return (
    <View className={[styles.alarm, className].filter(Boolean).join(' ')}>
      <View className={styles.icon}>
        <Text>!</Text>
      </View>
      <Text className={styles.text}>
        <Text className={styles.lead}>{leadLabel} · </Text>
        {children}
      </Text>
    </View>
  );
}
