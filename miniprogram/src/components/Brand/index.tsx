/**
 * Brand — helmet mark + "Safety Scout" wordmark + 可选 sub "/ 工地安全巡检"。
 *
 * 2026-05-24：从字母 chip "S" 升级到 helmet SVG，对齐 docs/plans/2026-05-22-unified-modern-minimal/
 * 的 brand mark。底盘仍是橙色圆角方块，符合 mockup（critique P3 已提"未来上 brand 层时去掉底盘"，
 * 当前 mockup 与代码统一在带底盘这一步）。
 *
 * size='lg' 让首屏 hero 区可放大版本。
 * 移动端宽 ≤640px 时 sub 自动隐藏（由父级 .topnav 媒体查询控制 .sub display:none）。
 */
import { View, Text } from '@tarojs/components';

import styles from './index.module.scss';

export interface BrandProps {
  size?: 'md' | 'lg';
  /** 主名右侧的灰色 sub，mobile 自动隐藏。默认 "/ 工地安全巡检"。传 false 不渲染。 */
  sub?: string | false;
  className?: string;
}

// mockup home.html line 195 的 helmet SVG：半圆穹顶 + 帽檐横条，currentColor 由 .mark 的 color 控制。
const HELMET_SVG =
  '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="18" height="18">' +
  '<path fill="currentColor" d="M12 5.5c-4.1 0-7.5 3.4-7.5 7.5v.5h15v-.5c0-4.1-3.4-7.5-7.5-7.5z"/>' +
  '<rect fill="currentColor" x="3" y="14" width="18" height="2.4" rx="1.2"/>' +
  '</svg>';

export function Brand({ size = 'md', sub = '/ 工地安全巡检', className }: BrandProps) {
  const cls = [styles.brand, size === 'lg' ? styles.lg : '', className]
    .filter(Boolean)
    .join(' ');
  return (
    <View className={cls}>
      <View
        className={styles.mark}
        aria-hidden="true"
        // 同 Icon 组件做法：H5 端 <View>=<div>，dangerouslySetInnerHTML 嵌 SVG 安全；
        // weapp 端后续做平台适配
        dangerouslySetInnerHTML={{ __html: HELMET_SVG }}
      />
      <Text className={styles.name}>Safety Scout</Text>
      {sub !== false && <Text className={styles.sub}>{sub}</Text>}
    </View>
  );
}
