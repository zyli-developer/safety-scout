/**
 * StepList — 安静的步骤列表。三态：done / active / pending。
 * currentStep 1-indexed：== i+1 时 active；< i+1 时 done；> i+1 时 pending。
 */
import { View, Text } from '@tarojs/components';

import styles from './index.module.scss';

export interface StepListProps {
  steps: string[];
  currentStep: number;
  className?: string;
}

function stateFor(idx: number, currentStep: number): 'done' | 'active' | 'pending' {
  const oneBased = idx + 1;
  if (oneBased < currentStep) return 'done';
  if (oneBased === currentStep) return 'active';
  return 'pending';
}

export function StepList({ steps, currentStep, className }: StepListProps) {
  return (
    <View className={[styles.list, className].filter(Boolean).join(' ')}>
      {steps.map((label, i) => {
        const state = stateFor(i, currentStep);
        const stateClass =
          state === 'done' ? styles.done : state === 'active' ? styles.active : styles.pending;
        return (
          <View key={`${i}-${label}`} className={[styles.step, stateClass].join(' ')} data-state={state}>
            <View className={styles.check}>
              <Text>{state === 'done' ? '✓' : String(i + 1).padStart(2, '0')}</Text>
            </View>
            <Text className={styles.label}>{label}</Text>
          </View>
        );
      })}
    </View>
  );
}
