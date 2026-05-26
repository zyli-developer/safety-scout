/**
 * DesktopIndex — PC web 首页桌面布局（unified-modern-minimal · 2026-05-22）。
 *
 * 结构：TopNav / Hero(无 eyebrow, h1 + sub) / 1.4fr+1fr 两栏。
 *   左：UploadDropzone 卡（上传现场照片 · JPG/PNG · ≤10MB + dropzone + 三步流程卡）
 *   右：今日卡（4 宫格 Stat）+ 最近巡检卡（待 history API）
 *
 * 2026-05-24 改动（按 docs/plans/2026-05-24-ui-parity-audit.md B3）：
 * - 删 eyebrow "AI 现场巡检"（mockup 无）
 * - 删头部右侧 "历史报告 / 新建巡检" 双按钮（mockup 无）
 * - 删 engineStrip "Claude Sonnet 4.5 · 平均 29s · v0.3.1"（dev-chrome）
 * - Hero 文案 + lede 对齐 home.html
 * - dropzoneSpec 改"JPG / PNG · 单张 ≤ 10 MB · 不会上传到任何第三方"
 * - 新增三步流程卡（拍照 / 等待 / 看报告）
 *
 * 整页 max-width 1240、左右 32px gutter；视口 <1024px 时由 dispatcher 切回 MobileIndex。
 */
import Taro from '@tarojs/taro';
import { View, Text } from '@tarojs/components';
import { useState } from 'react';

import { TopNav } from '../../components/TopNav';
import { Stat } from '../../components/Stat';
import { UploadDropzone } from '../../components/desktop/UploadDropzone';
import { createInspection } from '../../api/inspections';
import { mapApiError } from '../../utils/errorMessage';
import { rememberPhoto, rememberPhotoFromFile } from '../../utils/lastPhotoStore';

import styles from './desktop.module.scss';

export default function DesktopIndex() {
  const [uploading, setUploading] = useState(false);

  const handleFile = async (file: File) => {
    if (uploading) return;
    setUploading(true);
    try {
      const resp = await createInspection(file);

      // 双轨保存：
      // 1) blob URL 立即同步进内存 —— 不阻塞 navigateTo、报告页挂载时即可读到
      // 2) data URL 异步转换写 sessionStorage —— 给"刷新 / HMR / 新 tab"持久化
      try {
        const blobUrl = URL.createObjectURL(file);
        rememberPhoto(resp.inspection_id, blobUrl);
      } catch (e) {
        console.warn('[upload] createObjectURL 失败，photo 同步预览不可用', e);
      }
      rememberPhotoFromFile(resp.inspection_id, file).catch((e) => {
        console.warn('[upload] FileReader → data URL 失败，reload 后 photo 会丢', e);
      });

      // v2 流量按 V2_TRAFFIC_SHARE 决定；report 页通过 ?v=X 知道用哪条 GET
      const vParam = resp.schema_version === 'v2' ? '&v=2' : '';
      Taro.navigateTo({
        url: `/pages/report/index?id=${resp.inspection_id}&pi=${resp.poll_interval_ms}&to=${resp.timeout_ms}${vParam}`,
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
      <TopNav
        activeTab="inspect"
        onTabChange={(tab) => {
          // 2026-05-24 B8：reports tab 跳 history 页（localStorage 数据源）
          if (tab === 'reports') Taro.navigateTo({ url: '/pages/history/index' });
        }}
      />

      <View className={styles.container}>
        <View className={styles.hero}>
          <Text className={styles.h1}>拍一张工地照片，AI 立刻找出隐患。</Text>
          <Text className={styles.lede}>
            面向安全员的隐患识别工具。识别高处坠落、临边洞口、用电、消防、个人防护等十类常见隐患，给出可执行的整改建议与规范条款引用。平均 3 分钟出报告。
          </Text>
        </View>

        <View className={styles.grid}>
          <View className={styles.dropzoneCard}>
            <View className={styles.dropzoneHeader}>
              <Text className={styles.dropzoneTitle}>上传现场照片</Text>
              <Text className={styles.dropzoneSpec}>JPG / PNG · 单张 ≤ 10 MB · 不会上传到任何第三方</Text>
            </View>
            <UploadDropzone
              onSelect={handleFile}
              uploading={uploading}
              onQRRequest={notImplemented('手机扫码')}
            />
            <View className={styles.uploadSteps} aria-label="使用流程">
              <View className={styles.uploadStep}>
                <Text className={styles.stepNum}>01 · 拍照</Text>
                <Text className={styles.stepLabel}>对准隐患拍清楚</Text>
                <Text className={styles.stepSub}>支持现场拍 / 历史照</Text>
              </View>
              <View className={styles.uploadStep}>
                <Text className={styles.stepNum}>02 · 等待</Text>
                <Text className={styles.stepLabel}>AI 识别 · 平均 3 分钟</Text>
                <Text className={styles.stepSub}>不离开页面也行</Text>
              </View>
              <View className={styles.uploadStep}>
                <Text className={styles.stepNum}>03 · 看报告</Text>
                <Text className={styles.stepLabel}>隐患清单 + 整改建议</Text>
                <Text className={styles.stepSub}>可直接转发给班组</Text>
              </View>
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
                  全部 →
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
