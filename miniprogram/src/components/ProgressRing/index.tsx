/**
 * ProgressRing — SVG 圆环进度。pct 0-100；中心 label 文本（如 "63%"）。
 * Taro weapp 不支持原生 <svg>，统一通过 dangerouslySetInnerHTML 注入（H5 走 innerHTML）。
 */
import { View } from '@tarojs/components';

import styles from './index.module.scss';

export interface ProgressRingProps {
  pct: number;
  label?: string;
  size?: number;
  /** ring stroke 宽度，默认 6。 */
  thickness?: number;
  /** 进度条颜色，默认 var(--accent)。 */
  color?: string;
  /** 轨道色，默认 var(--line)。 */
  trackColor?: string;
}

export function ProgressRing({
  pct,
  label,
  size = 88,
  thickness = 6,
  color = 'var(--accent)',
  trackColor = 'var(--line)',
}: ProgressRingProps) {
  const clamped = Math.max(0, Math.min(100, pct));
  const r = (size - thickness) / 2;
  const c = 2 * Math.PI * r;
  const off = c * (1 - clamped / 100);
  const cx = size / 2;
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}" style="transform:rotate(-90deg)">
    <circle cx="${cx}" cy="${cx}" r="${r}" stroke="${trackColor}" stroke-width="${thickness}" fill="none" />
    <circle cx="${cx}" cy="${cx}" r="${r}" stroke="${color}" stroke-width="${thickness}" fill="none"
            stroke-linecap="round" stroke-dasharray="${c}" stroke-dashoffset="${off}" />
  </svg>`;
  return (
    <View
      className={styles.ring}
      style={{ width: `${size}px`, height: `${size}px` }}
      data-pct={clamped}
    >
      <View
        className={styles.svgWrap}
        style={{ width: `${size}px`, height: `${size}px` }}
        dangerouslySetInnerHTML={{ __html: svg }}
      />
      {label != null && <View className={styles.text}>{label}</View>}
    </View>
  );
}
