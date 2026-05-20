/**
 * HeroBanner —— 页面顶部白卡 hero，两种模式（discriminated union）：
 *  - intro: 左 icon + 右 title/subtitle，用于首页"产品名片"位
 *  - metric: 左 severity ring + 右 count/meta，用于报告页"风险概览"位
 *
 * 设计意图：信息密度 + 视觉锚点；不引入新色板、新交互。
 * 不接受 children —— 该组件是定型 pattern，不是通用 slot。
 *
 * NOTE: metric 分支 + 对应的 severity 工具导入由 Task 4 加 ——
 * tsconfig 启用 noUnusedLocals，预先 stage 会编不过。
 */
import { View, Text } from '@tarojs/components';

import { Icon, type IconName } from '../Icon';
import type { Severity } from '../../types/report';

import styles from './index.module.scss';

export type HeroBannerProps =
  | {
      mode: 'intro';
      icon: IconName;
      title: string;
      subtitle: string;
    }
  | {
      mode: 'metric';
      severity: Severity;
      count: number;
      meta: string;
    };

export function HeroBanner(props: HeroBannerProps) {
  if (props.mode === 'intro') {
    return (
      <View className={styles.banner}>
        <View className={styles.iconSlot}>
          <Icon name={props.icon} size={56} color="#007AFF" />
        </View>
        <View className={styles.textCol}>
          <Text className={styles.title}>{props.title}</Text>
          <Text className={styles.subtitle}>{props.subtitle}</Text>
        </View>
      </View>
    );
  }
  // metric mode — implemented in Task 4
  return null;
}
