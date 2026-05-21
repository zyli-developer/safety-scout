/**
 * Brand — small mark + "Safety Scout" wordmark.
 * 用在桌面 TopNav 左侧、移动 home 顶栏。size='lg' 让首屏 hero 区可放大版本。
 */
import { View, Text } from '@tarojs/components';

import styles from './index.module.scss';

export interface BrandProps {
  size?: 'md' | 'lg';
  className?: string;
}

export function Brand({ size = 'md', className }: BrandProps) {
  const cls = [styles.brand, size === 'lg' ? styles.lg : '', className]
    .filter(Boolean)
    .join(' ');
  return (
    <View className={cls}>
      <View className={styles.mark}>
        <Text className={styles.markText}>S</Text>
      </View>
      <Text className={styles.name}>Safety Scout</Text>
    </View>
  );
}
