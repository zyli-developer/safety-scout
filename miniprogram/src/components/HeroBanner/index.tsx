/**
 * HeroBanner —— 页面顶部白卡 hero，两种模式（discriminated union）：
 *  - intro: 左 icon + 右 title/subtitle，用于首页"产品名片"位
 *  - metric: 左 severity ring + 右 count/meta，用于报告页"风险概览"位
 *
 * 设计意图：信息密度 + 视觉锚点；不引入新色板、新交互。
 * 不接受 children —— 该组件是定型 pattern，不是通用 slot。
 */
import { View, Text } from '@tarojs/components';

import { Icon, type IconName } from '../Icon';
import {
  SEVERITY_COLOR,
  SEVERITY_BG_TINT,
  SEVERITY_TEXT_ON_TINT,
  SEVERITY_LABEL,
} from '../../utils/severity';
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
  const { severity, count, meta } = props;
  return (
    <View className={styles.banner}>
      <View
        className={styles.ring}
        data-severity={severity}
        style={{
          borderColor: SEVERITY_COLOR[severity],
          backgroundColor: SEVERITY_BG_TINT[severity],
        }}
      >
        <Text className={styles.ringLabel} style={{ color: SEVERITY_TEXT_ON_TINT[severity] }}>
          {SEVERITY_LABEL[severity].charAt(0)}
        </Text>
      </View>
      <View className={styles.textCol}>
        <Text className={styles.count}>{count} 项隐患</Text>
        <Text className={styles.subtitle}>{meta}</Text>
      </View>
    </View>
  );
}
