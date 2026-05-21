import { View, Text } from '@tarojs/components';

import styles from './index.module.scss';

export interface ProgressIndicatorProps {
  /** 当前步骤：1=拍照已就绪 2=AI 识别中 3=报告生成中 */
  currentStep: 1 | 2 | 3;
  /** 已耗时（毫秒），步骤 2 显示 */
  elapsedMs?: number;
}

const STEPS = [
  { key: 1, label: '拍照已就绪' },
  { key: 2, label: 'AI 识别中' },
  { key: 3, label: '报告生成中' },
] as const;

export function ProgressIndicator({ currentStep, elapsedMs }: ProgressIndicatorProps) {
  const secs = typeof elapsedMs === 'number' ? Math.floor(elapsedMs / 1000) : 0;
  const dotsCount = 16 + (secs % 8);  // mild text-tick so the user knows it's alive
  return (
    <View className={styles.container}>
      <View className={styles.readout}>
        <Text className={styles.readoutLabel}>READING</Text>
        <Text className={styles.readoutDots}>{'·'.repeat(dotsCount)}</Text>
        {currentStep === 2 && <Text className={styles.readoutTime}>{secs}s</Text>}
      </View>
      <Text className={styles.readoutHint}>预计 60–180s · Claude Vision 推理中</Text>

      <View className={styles.steps}>
        {STEPS.map((s) => {
          const isDone = s.key < currentStep;
          const isActive = s.key === currentStep;
          const state = isDone ? 'done' : isActive ? 'active' : 'pending';
          return (
            <View key={s.key} className={styles.step} data-state={state}>
              <Text className={styles.stepIndex}>{String(s.key).padStart(2, '0')}</Text>
              <Text className={styles.stepLabel}>{s.label}</Text>
            </View>
          );
        })}
      </View>
    </View>
  );
}
