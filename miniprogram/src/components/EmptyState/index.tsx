/**
 * EmptyState — 4 态空 / 错误展示。对齐 docs/plans/2026-05-22-unified-modern-minimal/empty-error.html。
 *
 * 4 态：
 *   - empty:    "还没拍过照片" 冷启动
 *   - blurry:   "这张照片有点糊" 模糊 / 低质量（critique P1 新增）
 *   - rejected: "这张照片似乎不是工地现场" AI 拒识
 *   - network:  "上传超时，AI 分析未能开始" 网络 / 服务失败
 *
 * 用法：
 *   <EmptyState variant="blurry" onPrimary={...} onGhost={...} />
 *   覆盖默认文案可传 title / sub。
 *   details: 显示在 art 下方的 2 列小卡（如"清晰度评分 0.31"），来自具体场景。
 */
import { View, Text } from '@tarojs/components';
import type { ReactNode } from 'react';

import { Icon, type IconName } from '../Icon';

import styles from './index.module.scss';

export type EmptyStateVariant = 'empty' | 'blurry' | 'rejected' | 'network';

export interface EmptyStateAction {
  label: string;
  onTap: () => void;
}

export interface EmptyStateProps {
  variant: EmptyStateVariant;
  title?: string;
  sub?: string;
  eyebrow?: string;
  /** primary 按钮 (橙)；mockup 4 态都有 */
  primaryAction?: EmptyStateAction;
  /** ghost 按钮 (灰边)；可选 */
  ghostAction?: EmptyStateAction;
  /** art 下方两个小卡，如"清晰度评分 0.31 · 偏低" */
  details?: Array<{ label: string; value: string }>;
  /** 底部小贴士 */
  tips?: { title: string; items: ReactNode[] };
  className?: string;
}

interface VariantPreset {
  eyebrow: string;
  title: string;
  sub: string;
  iconName: IconName;
  artClass: string;
}

const PRESETS: Record<EmptyStateVariant, VariantPreset> = {
  empty: {
    eyebrow: '还没拍过照片',
    title: '拍下第一张现场照片，开始第一次巡检',
    sub: 'Safety Scout 不需要注册，不需要选项目 — 拍一张就开始。识别全程在国内服务器内完成。',
    iconName: 'camera',
    artClass: 'artEmpty',
  },
  blurry: {
    eyebrow: '画面模糊 · 抖动 / 失焦',
    title: '这张照片有点糊',
    sub: 'AI 在画面里识别到明显抖动 / 失焦，关键细节看不清，强行分析容易漏检或误判。重拍一张更清楚的，识别准得多。',
    iconName: 'camera',
    artClass: 'artBlurry',
  },
  rejected: {
    eyebrow: 'AI 拒识 · 不像建筑工地',
    title: '这张照片似乎不是工地现场',
    sub: 'AI 在画面中没有识别出脚手架、楼层结构、临时用电箱或工地常见要素，因此没有给出隐患报告。',
    iconName: 'slash-circle',
    artClass: 'artRejected',
  },
  network: {
    eyebrow: '连接失败 · 请稍后重试',
    title: '上传超时，AI 分析未能开始',
    sub: '已为你保留这张照片在本地。等网络恢复后可一键重传，不需要重新拍。',
    iconName: 'x-circle',
    artClass: 'artNetwork',
  },
};

export function EmptyState({
  variant,
  title,
  sub,
  eyebrow,
  primaryAction,
  ghostAction,
  details,
  tips,
  className,
}: EmptyStateProps) {
  const preset = PRESETS[variant];
  const finalTitle = title ?? preset.title;
  const finalSub = sub ?? preset.sub;
  const finalEyebrow = eyebrow ?? preset.eyebrow;
  const artCls = [styles.art, styles[preset.artClass]].filter(Boolean).join(' ');

  return (
    <View className={[styles.state, className].filter(Boolean).join(' ')} data-state={variant}>
      <View className={artCls} aria-hidden="true">
        <Icon name={preset.iconName} size={64} color="currentColor" />
      </View>

      <View className={styles.head}>
        <Text className={styles.eyebrow}>{finalEyebrow}</Text>
        <Text className={styles.title}>{finalTitle}</Text>
        <Text className={styles.sub}>{finalSub}</Text>
      </View>

      {details && details.length > 0 && (
        <View className={styles.details}>
          {details.map((d) => (
            <View key={d.label} className={styles.detailCell}>
              <Text className={styles.detailLabel}>{d.label}</Text>
              <Text className={styles.detailValue}>{d.value}</Text>
            </View>
          ))}
        </View>
      )}

      <View className={styles.actions}>
        {primaryAction && (
          <View
            className={[styles.btn, styles.btnPrimary].join(' ')}
            role="button"
            onClick={primaryAction.onTap}
          >
            <Text>{primaryAction.label}</Text>
          </View>
        )}
        {ghostAction && (
          <View
            className={[styles.btn, styles.btnGhost].join(' ')}
            role="button"
            onClick={ghostAction.onTap}
          >
            <Text>{ghostAction.label}</Text>
          </View>
        )}
      </View>

      {tips && tips.items.length > 0 && (
        <View className={styles.tips}>
          <Text className={styles.tipsTitle}>{tips.title}</Text>
          <View className={styles.tipsList}>
            {tips.items.map((item, i) => (
              <View key={i} className={styles.tipItem}>
                <View className={styles.tipBullet} />
                <Text className={styles.tipText}>{item}</Text>
              </View>
            ))}
          </View>
        </View>
      )}
    </View>
  );
}
