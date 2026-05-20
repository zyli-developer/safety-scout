import Taro from '@tarojs/taro';
import { View, Text } from '@tarojs/components';
import { useState } from 'react';

import { BigButton } from '../../components/BigButton';
import { HeaderBand } from '../../components/HeaderBand';
import { captureImage } from '../../hooks/useImageCapture';
import { createInspection } from '../../api/inspections';
import { mapApiError } from '../../utils/errorMessage';

import styles from './index.module.scss';

const SHOT_TIPS = [
  '贴近隐患位置，保持光线充足',
  '画面含工人 / 护栏 / 电箱 等关键元素',
  '距离 1–3m 为佳',
];

export default function IndexPage() {
  const [uploading, setUploading] = useState(false);

  const handleTap = async () => {
    if (uploading) return;
    let image;
    try { image = await captureImage(); } catch (_e) { return; }
    setUploading(true);
    try {
      const resp = await createInspection(image.tempFilePath);
      Taro.navigateTo({
        url: `/pages/report/index?id=${resp.inspection_id}&pi=${resp.poll_interval_ms}&to=${resp.timeout_ms}`,
      });
    } catch (e) {
      const ui = mapApiError(e);
      Taro.showToast({ title: ui.userMessage, icon: 'none', duration: 3000 });
    } finally {
      setUploading(false);
    }
  };

  return (
    <View className={styles.page}>
      <HeaderBand subtitle="拍照即查 · AI 30s 出报告" />

      <View className={styles.titleBlock}>
        <Text className={styles.h1}>工地隐患识别</Text>
        <Text className={styles.h1Latin}>AI · SITE HAZARD INSPECTION</Text>
      </View>

      <BigButton
        text="拍摄现场照片"
        subtitle="CAPTURE INSPECTION PHOTO"
        prefixGlyph="plus-square"
        onTap={handleTap}
        loading={uploading}
      />

      <View className={styles.section}>
        <View className={styles.sectionRule}>
          <Text className={styles.sectionLabel}>拍摄要点</Text>
        </View>
        {SHOT_TIPS.map((tip, i) => (
          <View key={i} className={styles.tipRow}>
            <Text className={styles.tipIndex}>{String(i + 1).padStart(2, '0')}</Text>
            <Text className={styles.tipText}>{tip}</Text>
          </View>
        ))}
      </View>

      <View className={styles.footer}>
        <Text className={styles.footerText}>⌖ AI ENGINE v3 · Claude Vision · ~30s/帧</Text>
      </View>
    </View>
  );
}
