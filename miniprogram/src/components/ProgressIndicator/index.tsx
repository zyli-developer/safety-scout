import { View, Text } from '@tarojs/components';

import styles from './index.module.scss';

export interface ProgressIndicatorProps {
  /** 当前步骤：1=拍照成功（短暂） 2=AI 分析中 3=报告就绪（短暂） */
  currentStep: 1 | 2 | 3;
  /** 已耗时（毫秒），仅 currentStep=2 时显示 */
  elapsedMs?: number;
}

const STEPS = [
  { key: 1, label: '拍照成功' },
  { key: 2, label: 'AI 分析中' },
  { key: 3, label: '报告就绪' },
] as const;

export function ProgressIndicator({ currentStep, elapsedMs }: ProgressIndicatorProps) {
  return (
    <View className={styles.container}>
      <Text className={styles.title}>正在为你生成报告</Text>
      <Text className={styles.subtitle}>AI 正在分析每一处隐患，请稍候</Text>
      <View className={styles.steps}>
        <View className={styles.connector} />
        {STEPS.map((s) => {
          const isDone = s.key < currentStep;
          const isActive = s.key === currentStep;
          return (
            <View
              key={s.key}
              className={styles.step}
              data-state={isDone ? 'done' : isActive ? 'active' : 'pending'}
            >
              <View className={styles.dotOuter}>
                <View className={styles.dot} />
              </View>
              <Text className={styles.label}>{s.label}</Text>
            </View>
          );
        })}
      </View>
      {currentStep === 2 && typeof elapsedMs === 'number' && (
        <Text className={styles.elapsed}>
          已耗时 {(elapsedMs / 1000).toFixed(0)}s（通常需 60–180s）
        </Text>
      )}
    </View>
  );
}
