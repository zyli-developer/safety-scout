/**
 * TopNav — Brand + 巡检/报告 2-tab + 头像。对齐 2026-05-22 modern-minimal mockup。
 *
 * 2026-05-24：
 * - 删除 onSearch / actions / iconBtn 入口（mockup 没有 search 按钮也没有任意 actions 槽）
 * - sticky top:0 + 固定高度 60px（mobile 54px），跟 mockup .topnav 1:1
 * - 增 ariaCurrent prop：activeTab 默认拿 "page"；在轮询页等"流程中"场景传 "step"
 *   （critique P0 修复点：polling 页 nav "巡检" 链接到 home，当前页不是 home，
 *   语义应该是 step 而非 page）
 */
import { View, Text } from '@tarojs/components';

import { Brand } from '../Brand';

import styles from './index.module.scss';

// 2026-05-22：班组 / 设置后端未实装，且违反"产品只做三步"主张，收回到 2-tab。
export type TopNavTabId = 'inspect' | 'reports';

const TABS: Array<{ id: TopNavTabId; label: string }> = [
  { id: 'inspect', label: '巡检' },
  { id: 'reports', label: '报告' },
];

export interface TopNavProps {
  activeTab?: TopNavTabId;
  /**
   * aria-current 取值：默认 "page"。
   * 当本组件用在"流程中"页面（polling / processing）且 activeTab 链接指向其它 page 时，
   * 传 "step" —— mockup polling.html:200 已修。
   */
  ariaCurrent?: 'page' | 'step';
  onTabChange?: (id: TopNavTabId) => void;
  /** 头像里的首字（默认 "用"）。 */
  user?: string;
  onAvatarClick?: () => void;
  className?: string;
}

export function TopNav({
  activeTab = 'inspect',
  ariaCurrent = 'page',
  onTabChange,
  user = '用',
  onAvatarClick,
  className,
}: TopNavProps) {
  return (
    <View className={[styles.nav, className].filter(Boolean).join(' ')}>
      <View className={styles.inner}>
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
                aria-current={isActive ? ariaCurrent : undefined}
                data-tab={t.id}
              >
                <Text>{t.label}</Text>
              </View>
            );
          })}
        </View>
        <View className={styles.spacer} />
        <View className={styles.avatar} onClick={onAvatarClick} role="button">
          <Text>{user.slice(0, 1)}</Text>
        </View>
      </View>
    </View>
  );
}
