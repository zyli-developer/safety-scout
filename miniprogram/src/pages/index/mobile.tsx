/**
 * 移动端首页 — unified-modern-minimal (2026-05-22) 对齐。
 *
 * 结构：TopNav / Hero(h1 + lede) / 大橙色整块 dropzone__tap "拍照" tap target / 小灰链接"或从相册选择"。
 *
 * 2026-05-24 改动（按 docs/plans/2026-05-24-ui-parity-audit.md B3）：
 * - 顶导从独立 brandBar 改 TopNav (mobile 自动隐藏 navlinks，保 brand + avatar)
 * - 删 eyebrow "AI 现场巡检"（mockup 无）
 * - Hero 文案对齐 mockup
 * - 主 CTA 从 BigButton 改为 mockup .dropzone__tap 风格的整块橙色 tap target
 * - 删 today stats 区（移动 mockup 没有）
 * - 删上次巡检 Photo 锚（移动 mockup 没有）
 *
 * Tap target 行为：保留 captureImage() hook —— 真接相机 intent，不是单纯跳页。
 * 这一点代码做得比 mockup 还对（mockup .dropzone__tap 是 <a href> 跳页占位）。
 */
import Taro from '@tarojs/taro';
import { View, Text } from '@tarojs/components';
import { useState } from 'react';

import { TopNav } from '../../components/TopNav';
import { Icon } from '../../components/Icon';
import { captureImage } from '../../hooks/useImageCapture';
import { createInspection } from '../../api/inspections';
import { mapApiError } from '../../utils/errorMessage';
import { rememberPhoto } from '../../utils/lastPhotoStore';

import styles from './mobile.module.scss';

export default function MobileIndex() {
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
      rememberPhoto(resp.inspection_id, image.tempFilePath);
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

      <View className={styles.hero}>
        <Text className={styles.h1}>拍一张工地照片，AI 立刻找出隐患。</Text>
        <Text className={styles.lede}>
          面向安全员的隐患识别工具。识别十类常见隐患，给出可执行的整改建议。平均 29 秒出报告。
        </Text>
      </View>

      <View className={styles.tapWrap}>
        {/* 大橙色整块 tap target：mockup .dropzone__tap 风格。
            uploading 时半透明 + 文案变化，给用户即时反馈。 */}
        <View
          className={[styles.dropzoneTap, uploading ? styles.dropzoneTapBusy : '']
            .filter(Boolean)
            .join(' ')}
          role="button"
          aria-label={uploading ? '正在上传' : '拍照开始巡检'}
          aria-busy={uploading}
          onClick={handleTap}
        >
          <Icon name="camera" size={42} color="var(--on-accent)" />
          <Text className={styles.dropzoneTapTitle}>{uploading ? '上传中…' : '拍照'}</Text>
          <Text className={styles.dropzoneTapSub}>
            {uploading ? '正在送往 AI 分析' : '对准隐患区域，AI 越靠近识别越准'}
          </Text>
        </View>

        <View
          className={styles.albumLink}
          role="button"
          aria-label="从相册选择已有照片"
          onClick={handleTap}
        >
          <Text>或从相册选择已有照片 →</Text>
        </View>
      </View>

      <View className={styles.spacer} />
    </View>
  );
}
