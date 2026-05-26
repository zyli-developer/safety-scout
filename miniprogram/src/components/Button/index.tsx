/**
 * Button — 4 variant 统一按钮组件。
 *   primary  : 安全橙实心 pill，主操作（出现次数 ≤ 3 每屏）
 *   secondary: 白底 + 浅线 pill，次操作
 *   ghost    : 透明，文本按钮
 *   hero     : 大块 CTA — 左 icon 圆 + 中 (title / subtitle 两行) + 右箭头；用在 home 开始巡检
 *
 * size='md' (default) | 'lg'。block=true 占满父容器宽。
 * 非 hero variant 用 children；hero 用 title/subtitle/icon。
 */
import { View, Text } from '@tarojs/components';
import type { ReactNode } from 'react';

import { Icon, type IconName } from '../Icon';

import styles from './index.module.scss';

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'hero';

export interface ButtonProps {
  variant?: ButtonVariant;
  size?: 'md' | 'lg';
  block?: boolean;
  onTap?: () => void;
  loading?: boolean;
  disabled?: boolean;
  children?: ReactNode;
  /** Hero only — left icon circle. */
  icon?: IconName;
  /** Hero only — main label. */
  title?: string;
  /** Hero only — secondary label. */
  subtitle?: string;
  className?: string;
}

export function Button({
  variant = 'primary',
  size = 'md',
  block = false,
  onTap,
  loading = false,
  disabled = false,
  children,
  icon,
  title,
  subtitle,
  className,
}: ButtonProps) {
  const isInteractive = !loading && !disabled;
  const classes = [
    styles.btn,
    styles[variant],
    size === 'lg' ? styles.lg : '',
    block ? styles.block : '',
    loading ? styles.loading : '',
    disabled ? styles.disabled : '',
    className,
  ]
    .filter(Boolean)
    .join(' ');

  if (variant === 'hero') {
    return (
      <View
        className={classes}
        onClick={isInteractive ? onTap : undefined}
        role="button"
        aria-disabled={!isInteractive}
      >
        {icon && (
          <View className={styles.heroIcon}>
            <Icon name={icon} size={20} color="#fff" />
          </View>
        )}
        <View className={styles.heroText}>
          {title && <Text className={styles.heroTitle}>{loading ? '处理中' : title}</Text>}
          {subtitle && <Text className={styles.heroSub}>{loading ? 'PROCESSING' : subtitle}</Text>}
        </View>
        <View className={styles.heroArrow}>
          <Icon name="arrow-right" size={18} color="#fff" />
        </View>
      </View>
    );
  }

  return (
    <View
      className={classes}
      onClick={isInteractive ? onTap : undefined}
      role="button"
      aria-disabled={!isInteractive}
    >
      {children}
    </View>
  );
}
