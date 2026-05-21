/**
 * DesktopIndex —— PC web 首页桌面布局。
 *
 * 左右分栏 (60/40)：左侧 UploadDropzone；右侧"拍摄要点" + "AI ENGINE"卡片。
 * 整页 max-width 1200px 居中；视口 <1024px 时由 dispatcher 切回 MobileIndex。
 *
 * 上传流：UploadDropzone → handleFile → createInspection(File) → Taro.navigateTo
 * 跳报告页；错误归一为 mapApiError(err).userMessage，弹 Taro.showToast。
 */
import Taro from '@tarojs/taro';
import { View, Text } from '@tarojs/components';
import { useState } from 'react';

import { TopNav } from '../../components/TopNav';
import { UploadDropzone } from '../../components/desktop/UploadDropzone';
import { createInspection } from '../../api/inspections';
import { mapApiError } from '../../utils/errorMessage';

import styles from './desktop.module.scss';

const SHOT_TIPS = [
  '贴近隐患位置，保持光线充足',
  '画面含工人 / 护栏 / 电箱 等关键元素',
  '距离 1–3m 为佳',
];

export default function DesktopIndex() {
  const [uploading, setUploading] = useState(false);

  const handleFile = async (file: File) => {
    if (uploading) return;
    setUploading(true);
    try {
      const resp = await createInspection(file);
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
      <TopNav activeTab="inspect" />

      <View className={styles.titleBlock}>
        <Text className={styles.h1}>工地隐患识别</Text>
        <Text className={styles.h1Latin}>AI · SITE HAZARD INSPECTION</Text>
      </View>

      <View className={styles.body}>
        <View className={styles.left}>
          <UploadDropzone onSelect={handleFile} uploading={uploading} />
        </View>

        <View className={styles.right}>
          <View className={styles.tipsCard}>
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

          <View className={styles.engineCard}>
            <Text className={styles.engineLabel}>⌖ AI ENGINE v3</Text>
            <Text className={styles.engineText}>Claude / Doubao Vision · ~30s/帧</Text>
          </View>
        </View>
      </View>
    </View>
  );
}
