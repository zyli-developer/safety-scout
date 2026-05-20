import Taro from '@tarojs/taro';
import { View, Text } from '@tarojs/components';
import { useState } from 'react';

import { BigButton } from '../../components/BigButton';
import { HeroBanner } from '../../components/HeroBanner';
import { captureImage } from '../../hooks/useImageCapture';
import { createInspection } from '../../api/inspections';
import { mapApiError } from '../../utils/errorMessage';

import styles from './index.module.scss';

export default function IndexPage() {
  const [uploading, setUploading] = useState(false);

  const handleTap = async () => {
    if (uploading) return;
    let image;
    try {
      image = await captureImage();
    } catch (_e) {
      return;
    }
    setUploading(true);
    try {
      const resp = await createInspection(image.tempFilePath);
      Taro.navigateTo({
        url:
          `/pages/report/index?id=${resp.inspection_id}` +
          `&pi=${resp.poll_interval_ms}&to=${resp.timeout_ms}`,
      });
    } catch (e) {
      const ui = mapApiError(e);
      Taro.showToast({ title: ui.userMessage, icon: 'none', duration: 3000 });
    } finally {
      setUploading(false);
    }
  };

  return (
    <View className={styles.indexPage}>
      <HeroBanner
        mode="intro"
        icon="document"
        title="Safety Scout"
        subtitle="拍一张，AI 30 秒出报告"
      />

      <View className={styles.header}>
        <Text className={styles.largeTitle}>工地隐患识别</Text>
      </View>

      <BigButton text="拍照检查" onTap={handleTap} loading={uploading} />

      <View className={styles.tipBlock}>
        <Text className={styles.tipText}>
          贴近隐患位置拍摄，保持光线充足；画面包含工人、护栏、电箱等关键元素，识别更准确。
        </Text>
      </View>
    </View>
  );
}
