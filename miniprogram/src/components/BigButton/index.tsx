import { View, Text } from '@tarojs/components';

import { Icon } from '../Icon';

import styles from './index.module.scss';

export interface BigButtonProps {
  text: string;
  onTap: () => void;
  loading?: boolean;
  disabled?: boolean;
}

export function BigButton({
  text,
  onTap,
  loading = false,
  disabled = false,
}: BigButtonProps) {
  const isInteractive = !loading && !disabled;
  const className = [
    styles.button,
    loading ? styles.loading : '',
    disabled ? styles.disabled : '',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <View
      className={className}
      onClick={isInteractive ? onTap : undefined}
      role="button"
      aria-disabled={!isInteractive}
    >
      <Icon name="camera" size={36} color="#FFFFFF" />
      <Text className={styles.label}>{loading ? '上传中...' : text}</Text>
    </View>
  );
}
