import Taro from '@tarojs/taro';
import { View, Text } from '@tarojs/components';
import { useState } from 'react';
import { BigButton } from '../../components/BigButton';
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
      Taro.showToast({
        title: ui.userMessage,
        icon: 'none',
        duration: 3000,
      });
    } finally {
      setUploading(false);
    }
  };

  return (
    <View className={styles.indexPage}>
      <View className={styles.headline}>
        <Text className={styles.title}>Safety Scout</Text>
        <Text className={styles.subtitle}>拍一张照片，看隐患</Text>
      </View>
      <BigButton text="拍隐患" onTap={handleTap} loading={uploading} />
      <Text className={styles.hint}>
        建议：贴近隐患位置拍摄，光线充足，画面包含工人/护栏/电箱等关键元素
      </Text>
    </View>
  );
}
