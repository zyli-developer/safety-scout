/**
 * ProgressIndicator — clean-minimal 进度面板：ProgressRing + StepList 组合。
 *
 * 入参 API 维持原样（currentStep 1/2/3 + 可选 elapsedMs），以便 pages/report/*
 * 直接消费。Step 2 时把 elapsed 秒数显示在环中央；环本身按 currentStep 平均推进
 * （0% / 50% / 100%）。3 步标签固定写死，与旧版一致。
 */
import { View, Text } from '@tarojs/components';

import { ProgressRing } from '../ProgressRing';
import { StepList } from '../StepList';

import styles from './index.module.scss';

export interface ProgressIndicatorProps {
  /** 当前步骤：1=拍照已就绪 2=AI 识别中 3=报告生成中 */
  currentStep: 1 | 2 | 3;
  /** 已耗时（毫秒），步骤 2 显示。 */
  elapsedMs?: number;
}

const STEP_LABELS = ['拍照已就绪', 'AI 识别中', '报告生成中'];

export function ProgressIndicator({ currentStep, elapsedMs }: ProgressIndicatorProps) {
  const secs = typeof elapsedMs === 'number' ? Math.floor(elapsedMs / 1000) : 0;
  // 环面进度：1 → 5%，2 → 50%，3 → 100%。step 1 给一点非零让用户看到 ring 不是空的。
  const pct = currentStep === 1 ? 5 : currentStep === 2 ? 50 : 100;
  const ringLabel = currentStep === 2 ? `${secs}s` : `${Math.round(pct)}%`;

  return (
    <View className={styles.wrap}>
      <View className={styles.head}>
        <ProgressRing pct={pct} label={ringLabel} />
        <View className={styles.headText}>
          <Text className={styles.eyebrow}>READING</Text>
          <Text className={styles.hint}>预计 60–180s · Claude Vision 推理中</Text>
        </View>
      </View>

      <StepList steps={STEP_LABELS} currentStep={currentStep} />
    </View>
  );
}
