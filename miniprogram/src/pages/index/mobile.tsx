/**
 * 移动端首页 — Clean & Minimal 重排：品牌栏 / hero 文案 / 主 CTA / 副 CTA / 今日数据。
 *
 * 数据：暂无后端"今日数据"接口，Stat 显示 "—"；接入后改为读取真实计数。
 * 同样地，"上次巡检照片"是设计稿里的视觉锚，但未有数据模型 → 当前不渲染。
 */
import Taro from '@tarojs/taro';
import { View, Text } from '@tarojs/components';
import { useState } from 'react';

import { BigButton } from '../../components/BigButton';
import { Button } from '../../components/Button';
import { Brand } from '../../components/Brand';
import { Stat } from '../../components/Stat';
import { Icon } from '../../components/Icon';
import { Photo } from '../../components/Photo';
import { captureImage } from '../../hooks/useImageCapture';
import { createInspection } from '../../api/inspections';
import { mapApiError } from '../../utils/errorMessage';
import { getLastPhoto, rememberPhoto } from '../../utils/lastPhotoStore';
import { relativeTime } from '../../utils/relativeTime';

import styles from './mobile.module.scss';

export default function MobileIndex() {
  const [uploading, setUploading] = useState(false);
  const lastPhoto = getLastPhoto();

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
      <View className={styles.brandBar}>
        <Brand />
        <View className={styles.avatar}>
          <Text>用</Text>
        </View>
      </View>

      <View className={styles.hero}>
        <Text className={styles.eyebrow}>AI 现场巡检</Text>
        <Text className={styles.h1}>拍一张</Text>
        <Text className={styles.h1}>AI 找隐患</Text>
        <Text className={styles.lede}>上传施工现场照片，30 秒内得到结构化安全报告</Text>
      </View>

      {/* 工地照片视觉锚 —— 仅当本 session 内有上传过才渲染，避免首次进入看到空灰底。
          src 来自 lastPhotoStore（内存缓存的 tempFilePath / blob:URL）；接入后端 photo_url 后改读。 */}
      {lastPhoto && (
        <View className={styles.photoWrap}>
          <Photo
            src={lastPhoto.src}
            ratio="4/3"
            overlay
            meta={`上次巡检 · ${relativeTime(new Date(lastPhoto.capturedAt).toISOString())}`}
          />
        </View>
      )}

      <View className={styles.ctaBlock}>
        <BigButton
          text="开始巡检"
          subtitle="拍照 · 上传 · 等待报告"
          prefixGlyph="camera"
          onTap={handleTap}
          loading={uploading}
        />
        <View className={styles.ghostWrap}>
          <Button variant="ghost" block onTap={handleTap} disabled={uploading}>
            <Icon name="image" size={18} color="var(--ink-2)" />
            <Text className={styles.ghostText}>从相册选择</Text>
          </Button>
        </View>
      </View>

      <View className={styles.today}>
        <View className={styles.todayHead}>
          <Text className={styles.todayTitle}>今日巡检</Text>
        </View>
        <View className={styles.todayCard}>
          <Stat num="—" label="次巡检" />
          <Stat num="—" label="高风险" tone="high" />
          <Stat num="—" label="中风险" tone="med" />
        </View>
      </View>

      {/* 把剩余空间放在 today 之后 —— hero/photo/CTA/today 自然顶部对齐，
          底部 spacer 兜住短内容场景，避免 today 被 margin-top:auto 顶到屏底。 */}
      <View className={styles.spacer} />
    </View>
  );
}
