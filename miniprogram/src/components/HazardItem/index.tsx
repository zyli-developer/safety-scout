/**
 * HazardItem — 隐患明细列表 row（替代旧 HazardCard 卡片形态）。
 * 三列布局：编号(40px) / 主体(1fr) / 行动按钮(auto)。
 * 主体里：类别 + 严重度 pill 一行 + 现象描述 + meta（code · regulation） + 可选的整改建议块。
 */
import { View, Text } from '@tarojs/components';

import { Icon } from '../Icon';
import { SeverityPill } from '../SeverityPill';
import type { Hazard } from '../../types/report';

import styles from './index.module.scss';

export interface HazardItemProps {
  hazard: Hazard;
  /** 1-indexed 序号；显示为 "01" / "02"。 */
  index: number;
  /** 是否展开"整改建议"块，默认 true。 */
  showFix?: boolean;
  onAction?: () => void;
  /**
   * 反馈入口回调。传入 → 渲染"反馈"小链接（meta 行右侧）；不传 → 不渲染。
   * 仅在 v2 inspection 上由 caller 传入（v1 后端无 feedback API）。
   */
  onFeedback?: () => void;
  className?: string;
}

export function HazardItem({
  hazard,
  index,
  showFix = true,
  onAction,
  onFeedback,
  className,
}: HazardItemProps) {
  const { severity, description, regulation, suggestion, category_name, category_code } = hazard;
  const hasReg = regulation.length > 0;
  const isMajor = hazard.is_major === true;
  const majorBasis = hazard.major_basis ?? '';
  return (
    <View
      className={[styles.row, isMajor ? styles.rowMajor : '', className].filter(Boolean).join(' ')}
      data-severity={severity}
      data-major={isMajor ? 'true' : undefined}
    >
      <View className={styles.idx}>
        <Text>{String(index).padStart(2, '0')}</Text>
      </View>
      <View className={styles.body}>
        <View className={styles.head}>
          <Text className={styles.cat}>{category_name}</Text>
          <SeverityPill level={severity} />
          {isMajor && (
            <View className={styles.majorBadge} role="status" aria-label="重大事故隐患">
              <Text>重大隐患</Text>
            </View>
          )}
        </View>
        <Text className={styles.desc}>{description}</Text>
        {isMajor && majorBasis.length > 0 && (
          <View className={styles.majorBasis}>
            <Text className={styles.majorBasisLabel}>判定依据 · </Text>
            <Text className={styles.majorBasisText}>{majorBasis}</Text>
          </View>
        )}
        <View className={styles.meta}>
          <Text>{category_code}</Text>
          {hasReg && (
            <>
              <Text className={styles.sep}>·</Text>
              <Text>{regulation}</Text>
            </>
          )}
          {onFeedback && (
            <>
              <Text className={styles.sep}>·</Text>
              <View
                className={styles.feedbackLink}
                role="button"
                aria-label={`对 ${category_code} 提交反馈`}
                onClick={(e) => {
                  // 阻止冒泡 —— action 列的"查看详情"是父级 onClick，反馈链接独立行为
                  e.stopPropagation();
                  onFeedback();
                }}
              >
                <Text>反馈</Text>
              </View>
            </>
          )}
        </View>
        {showFix && (
          // 2026-05-24：对齐 mockup .suggestion-callout —— accent-soft 橙色块 + 左 icon，
          // 与 report.html 列表里的整改建议视觉同源。
          <View className={styles.fix}>
            <View className={styles.fixIcon}>
              <Icon name="tick" size={16} color="var(--accent)" />
            </View>
            <View className={styles.fixContent}>
              <Text className={styles.fixLabel}>整改建议 · </Text>
              <Text className={styles.fixBody}>{suggestion}</Text>
            </View>
          </View>
        )}
      </View>
      <View
        className={styles.action}
        onClick={onAction}
        role={onAction ? 'button' : undefined}
        aria-label={onAction ? '查看详情' : undefined}
      >
        <Icon name="chevron-right" size={16} color="var(--ink-3)" />
      </View>
    </View>
  );
}
