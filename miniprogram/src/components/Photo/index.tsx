/**
 * Photo — 圆角工地图卡 + 可选 meta 角标 + 可选底部渐变。
 * ratio 走 CSS aspect-ratio（H5 现代浏览器支持；weapp 走 height 退化时由调用方传 height）。
 * meta 是右下角的胶囊（如 "上次巡检 · 12 分钟前"）。
 *
 * H5 端故意用原生 <img> 而非 Taro <Image>：
 *   - Taro Image 编译为 <taro-image-core> Stencil 自定义元素，blob: URL 在自定义
 *     元素生命周期里有时序问题（首次加载到 onLoad 之间会闪空）；原生 <img>
 *     直接走浏览器渲染管线，blob URL 立刻显示，print 时也能正常出图
 *   - object-fit 在原生 <img> 上直接生效，省去自定义元素的 mode 分支
 *   - weapp 路径目前未启用，TODO: 用 process.env.TARO_ENV === 'weapp' 分支挂回 Taro Image
 */
import { View, Text } from '@tarojs/components';

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
      {src ? (
        // 原生 <img> + object-fit:cover 来自 .img；blob:/data:/http(s) 均原生支持。
        <img className={styles.img} src={src} alt={alt} />
      ) : (
        // 空 src 兜底：不渲染 <img>（避免 H5 显示破图 icon），让父容器 surface-2
        // 灰底兜底，meta 仍可显示 —— 用作"等数据"占位。
        <View className={styles.empty} aria-hidden />
      )}
      {overlay && src && <View className={styles.grad} />}
      {meta && (
        <View className={styles.meta}>
          <View className={styles.dot} />
          <Text className={styles.metaText}>{meta}</Text>
        </View>
      )}
    </View>
  );
}
