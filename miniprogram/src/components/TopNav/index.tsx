/**
 * TopNav — 桌面 4-tab 水平导航：Brand + 巡检/报告/班组/设置 + actions + 搜索 + 头像。
 * tabs 配置写死（巡检/报告/班组/设置），切换通过 onTabChange 回调出去；
 * 当前生效 tab 由 activeTab 决定，纯受控。
 */
import { View, Text } from '@tarojs/components';
import type { ReactNode } from 'react';

import { Brand } from '../Brand';
import { Icon } from '../Icon';

import styles from './index.module.scss';

export type TopNavTabId = 'inspect' | 'reports' | 'team' | 'setting';

const TABS: Array<{ id: TopNavTabId; label: string }> = [
  { id: 'inspect', label: '巡检' },
  { id: 'reports', label: '报告' },
  { id: 'team', label: '班组' },
  { id: 'setting', label: '设置' },
];

export interface TopNavProps {
  activeTab?: TopNavTabId;
  onTabChange?: (id: TopNavTabId) => void;
  /** 额外按钮组，放在 search 之前。 */
  actions?: ReactNode;
  /** 头像里的首字（默认 "用"）。 */
  user?: string;
  onSearch?: () => void;
  onAvatarClick?: () => void;
  className?: string;
}

export function TopNav({
  activeTab = 'inspect',
  onTabChange,
  actions,
  user = '用',
  onSearch,
  onAvatarClick,
  className,
}: TopNavProps) {
  return (
    <View className={[styles.nav, className].filter(Boolean).join(' ')}>
      <View className={styles.left}>
        <Brand />
        <View className={styles.links}>
          {TABS.map((t) => {
            const isActive = t.id === activeTab;
            return (
              <View
                key={t.id}
                className={[styles.link, isActive ? styles.active : ''].filter(Boolean).join(' ')}
                onClick={() => onTabChange?.(t.id)}
                role="button"
                aria-current={isActive ? 'page' : undefined}
                data-tab={t.id}
              >
                <Text>{t.label}</Text>
              </View>
            );
          })}
        </View>
      </View>
      <View className={styles.right}>
        {actions}
        <View className={styles.iconBtn} onClick={onSearch} role="button" aria-label="搜索">
          <Icon name="search" size={18} color="var(--ink-2)" />
        </View>
        <View className={styles.avatar} onClick={onAvatarClick} role="button">
          <Text>{user.slice(0, 1)}</Text>
        </View>
      </View>
    </View>
  );
}
