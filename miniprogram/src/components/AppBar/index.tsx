/**
 * AppBar — 移动顶部栏。左侧（可选）返回按钮 + 自定义 left + 标题；右侧操作组。
 * 用在 mobile report 等子页。home 通常用 Brand 不挂 AppBar。
 */
import { View, Text } from '@tarojs/components';
import type { ReactNode } from 'react';

import { Icon } from '../Icon';

import styles from './index.module.scss';

export interface AppBarProps {
  title?: string;
  left?: ReactNode;
  right?: ReactNode;
  /** 隐藏左侧返回按钮（home / 顶层入口）。 */
  backless?: boolean;
  onBack?: () => void;
  className?: string;
}

export function AppBar({ title, left, right, backless = false, onBack, className }: AppBarProps) {
  return (
    <View className={[styles.bar, className].filter(Boolean).join(' ')}>
      <View className={styles.side}>
        {!backless && (
          <View
            className={styles.back}
            onClick={onBack}
            role="button"
            aria-label="返回"
          >
            <Icon name="chevron-left" size={18} color="var(--ink-2)" />
          </View>
        )}
        {left}
        {title && <Text className={styles.title}>{title}</Text>}
      </View>
      <View className={styles.side}>{right}</View>
    </View>
  );
}
