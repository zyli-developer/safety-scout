/**
 * Stat — 大数字 + 标签。用于首页今日卡 / 报告概要卡。
 * tone='high'|'med'|'low' 给数字着色；默认中性 ink。
 */
import { View, Text } from '@tarojs/components';

import styles from './index.module.scss';

export type StatTone = 'high' | 'med' | 'low';

export interface StatProps {
  num: string | number;
  label: string;
  tone?: StatTone;
  className?: string;
}

export function Stat({ num, label, tone, className }: StatProps) {
  const numCls = [styles.num, tone ? styles[tone] : ''].filter(Boolean).join(' ');
  return (
    <View className={[styles.stat, className].filter(Boolean).join(' ')}>
      <Text className={numCls}>{num}</Text>
      <Text className={styles.lbl}>{label}</Text>
    </View>
  );
}
