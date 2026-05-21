/**
 * DesktopIndex — PC web 首页桌面布局（Clean & Minimal）。
 *
 * 结构：TopNav / 页头(eyebrow + h1 + body + 右侧两按钮) / 1.5fr+1fr 两栏。
 *   左：UploadDropzone 卡（上传现场照片 · JPG/PNG/HEIC · 15MB + dropzone + 模型可用性条）
 *   右：今日卡（4 宫格 Stat）+ 最近巡检卡（暂为空态，待 history API）
 *
 * 整页 max-width 1280px、左右 32px gutter；视口 <1024px 时由 dispatcher 切回 MobileIndex。
 *
 * 上传流：UploadDropzone → handleFile → createInspection(File) → Taro.navigateTo
 * 跳报告页；错误归一为 mapApiError(err).userMessage，弹 Taro.showToast。
 *
 * "历史报告" / "新建巡检" / "查看全部" 是 placeholder action —— 后端尚未实现，
 * 按下走 toast 提示。
 */
import Taro from '@tarojs/taro';
import { View, Text } from '@tarojs/components';
import { useState } from 'react';

import { TopNav } from '../../components/TopNav';
import { Button } from '../../components/Button';
import { Icon } from '../../components/Icon';
import { Stat } from '../../components/Stat';
import { UploadDropzone } from '../../components/desktop/UploadDropzone';
import { createInspection } from '../../api/inspections';
import { mapApiError } from '../../utils/errorMessage';

import styles from './desktop.module.scss';

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

  const notImplemented = (label: string) => () =>
    Taro.showToast({ title: `${label}：开发中`, icon: 'none', duration: 2000 });

  return (
    <View className={styles.page}>
      <TopNav activeTab="inspect" />

      <View className={styles.container}>
        <View className={styles.header}>
          <View className={styles.headerLeft}>
            <Text className={styles.eyebrow}>AI 现场巡检</Text>
            <Text className={styles.h1}>开始一次现场巡检</Text>
            <Text className={styles.lede}>
              上传一张施工现场照片，AI 会在 30 秒内识别隐患、引用规范条款、给出可执行的整改建议。
            </Text>
          </View>
          <View className={styles.headerActions}>
            <Button variant="secondary" onTap={notImplemented('历史报告')}>
              <Icon name="image" size={16} color="var(--ink)" />
              <Text className={styles.btnText}>历史报告</Text>
            </Button>
            <Button variant="primary" onTap={notImplemented('新建巡检')}>
              <Text className={styles.btnText}>新建巡检</Text>
            </Button>
          </View>
        </View>

        <View className={styles.grid}>
          <View className={styles.dropzoneCard}>
            <View className={styles.dropzoneHeader}>
              <Text className={styles.dropzoneTitle}>上传现场照片</Text>
              <Text className={styles.dropzoneSpec}>JPG · PNG · HEIC · 最大 15MB</Text>
            </View>
            <UploadDropzone
              onSelect={handleFile}
              uploading={uploading}
              onQRRequest={notImplemented('手机扫码')}
            />
            <View className={styles.engineStrip}>
              <View className={styles.engineLeft}>
                <View className={styles.engineDot} />
                <Text className={styles.engineModel}>Claude Sonnet 4.5</Text>
                <Text className={styles.engineMeta}>· 平均 29s · 服务可用</Text>
              </View>
              <Text className={styles.engineVer}>v0.3.1</Text>
            </View>
          </View>

          <View className={styles.aside}>
            <View className={styles.todayCard}>
              <Text className={styles.cardTitle}>今日巡检</Text>
              <View className={styles.todayGrid}>
                <Stat num="—" label="次巡检" />
                <Stat num="—" label="高风险" tone="high" />
                <Stat num="—" label="中风险" tone="med" />
                <Stat num="—" label="低风险" tone="low" />
              </View>
            </View>

            <View className={styles.recentCard}>
              <View className={styles.recentHead}>
                <Text className={styles.cardTitle}>最近巡检</Text>
                <Text className={styles.recentLink} onClick={notImplemented('查看全部')}>
                  查看全部 →
                </Text>
              </View>
              <View className={styles.recentBody}>
                <Text className={styles.recentEmpty}>暂无历史，开始第一次巡检即可看到列表</Text>
              </View>
            </View>
          </View>
        </View>
      </View>
    </View>
  );
}
