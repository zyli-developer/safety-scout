import { View, Text } from '@tarojs/components';

import { Icon, type IconName } from '../Icon';

import styles from './index.module.scss';

export interface BigButtonProps {
  text: string;                  // 中文 label (e.g. "拍摄现场照片")
  subtitle?: string;             // Latin uppercase subtitle (e.g. "CAPTURE INSPECTION PHOTO")
  prefixGlyph?: IconName;        // Optional engineering glyph (e.g. 'plus-square')
  onTap: () => void;
  loading?: boolean;
  disabled?: boolean;
}

export function BigButton({
  text,
  subtitle,
  prefixGlyph,
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
      {prefixGlyph && (
        <View className={styles.glyphSlot}>
          <Icon name={prefixGlyph} size={28} color="#F4EFE5" />
        </View>
      )}
      <View className={styles.labels}>
        <Text className={styles.labelZh}>{loading ? '处理中' : text}</Text>
        {subtitle && <Text className={styles.labelEn}>{loading ? 'PROCESSING' : subtitle}</Text>}
      </View>
    </View>
  );
}
