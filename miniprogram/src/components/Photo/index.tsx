/**
 * Photo — 圆角工地图卡 + 可选 meta 角标 + 可选底部渐变。
 * ratio 走 CSS aspect-ratio（H5 现代浏览器支持；weapp 走 height 退化时由调用方传 height）。
 * meta 是右下角的胶囊（如 "上次巡检 · 12 分钟前"）。
 */
import { View, Text, Image } from '@tarojs/components';

import styles from './index.module.scss';

export interface PhotoProps {
  src: string;
  alt?: string;
  /** 形如 '16/9' / '4/3' / '1/1'；优先级低于 height。 */
  ratio?: string;
  /** 显式高度（数字 px 或带单位字符串）。设了就忽略 ratio。 */
  height?: number | string;
  /** 加底部黑色渐变罩，让 meta 文字在亮图上仍清晰。 */
  overlay?: boolean;
  meta?: string;
  className?: string;
}

export function Photo({
  src,
  alt = '',
  ratio = '16/9',
  height,
  overlay = false,
  meta,
  className,
}: PhotoProps) {
  const style: Record<string, string | number> = {};
  if (height != null) {
    style.height = typeof height === 'number' ? `${height}px` : height;
  } else if (ratio) {
    style.aspectRatio = ratio.replace('/', ' / ');
  }
  return (
    <View className={[styles.photo, className].filter(Boolean).join(' ')} style={style}>
      <Image className={styles.img} src={src} mode="aspectFill" {...({ alt } as { alt: string })} />
      {overlay && <View className={styles.grad} />}
      {meta && (
        <View className={styles.meta}>
          <View className={styles.dot} />
          <Text className={styles.metaText}>{meta}</Text>
        </View>
      )}
    </View>
  );
}
