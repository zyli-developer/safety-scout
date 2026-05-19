import Taro from '@tarojs/taro';
import { View, Text } from '@tarojs/components';
import { useState } from 'react';

import { BigButton } from '../../components/BigButton';
import { captureImage } from '../../hooks/useImageCapture';
import { createInspection } from '../../api/inspections';
import { mapApiError } from '../../utils/errorMessage';

import styles from './index.module.scss';

const FLOW_STEPS = [
  { num: '01', label: '拍照' },
  { num: '02', label: 'AI 分析' },
  { num: '03', label: '看报告' },
];

export default function IndexPage() {
  const [uploading, setUploading] = useState(false);

  const handleTap = async () => {
    if (uploading) return;

    let image;
    try {
      image = await captureImage();
    } catch (_e) {
      // 用户取消拍照/选图 —— 不弹错（取消是常态）
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
      <View className={styles.hero}>
        <Text className={styles.appIcon}>🦺</Text>
        <Text className={styles.title}>Safety Scout</Text>
        <Text className={styles.subtitle}>工地隐患 · 一拍即查</Text>
      </View>

      <View className={styles.stepperPreview}>
        {FLOW_STEPS.map((step, i) => (
          <View key={step.num} className={styles.stepRow}>
            <View className={styles.stepNumWrap}>
              <Text className={styles.stepNum}>{step.num}</Text>
            </View>
            <Text className={styles.stepLabel}>{step.label}</Text>
            {i < FLOW_STEPS.length - 1 && (
              <Text className={styles.stepArrow}>›</Text>
            )}
          </View>
        ))}
      </View>

      <BigButton text="拍隐患" onTap={handleTap} loading={uploading} />

      <View className={styles.tipCard}>
        <Text className={styles.tipIcon}>💡</Text>
        <View className={styles.tipBody}>
          <Text className={styles.tipTitle}>拍摄建议</Text>
          <Text className={styles.tipText}>
            贴近隐患位置 · 光线充足 · 画面包含工人 / 护栏 / 电箱等关键元素
          </Text>
        </View>
      </View>
    </View>
  );
}
