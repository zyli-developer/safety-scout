/**
 * DesktopReport — 桌面布局的报告页（Clean & Minimal）。
 *
 * 结构：TopNav / Breadcrumb / 页头(severity pill + NO + h1 + 3 actions) /
 *   Hero grid 1.4fr+1fr (Photo / ReportSidebar) / 全宽 AlarmBox / 隐患列表卡 /
 *   3 联签字栏 / 页脚。
 *
 * "导出 PDF" / "分享" / "转派班组" / "提醒" / "查看全部" 等是 placeholder action ——
 * 后端尚未实现，按下走 toast 提示。Photo src 暂留空（后端 GET 报告未带 photo_url，
 * 接入后填回），Photo 组件自带 surface-2 灰底兜底，不会崩。
 */
import Taro from '@tarojs/taro';
import { View, Text } from '@tarojs/components';
import { useEffect, useState } from 'react';

import { usePolling } from '../../hooks/usePolling';
import { getInspection } from '../../api/inspections';
import { HazardItem } from '../../components/HazardItem';
import { TopNav } from '../../components/TopNav';
import { Icon } from '../../components/Icon';
import { Button } from '../../components/Button';
import { Photo } from '../../components/Photo';
import { SeverityPill } from '../../components/SeverityPill';
import { AlarmBox } from '../../components/AlarmBox';
import { ProgressTracker } from '../../components/ProgressTracker';
import { ReportSidebar } from '../../components/desktop/ReportSidebar';
import { sortBySeverity } from '../../utils/severity';
import { mapApiError } from '../../utils/errorMessage';
import { getPhotoFor } from '../../utils/lastPhotoStore';
import { ApiError } from '../../api/client';
import { DEFAULT_POLL_INTERVAL_MS, DEFAULT_TIMEOUT_MS } from '../../config';
import type { GetInspectionResponse } from '../../types/inspection';
import type { ReportPayload } from '../../types/report';

import styles from './desktop.module.scss';

export default function DesktopReport() {
  const router = Taro.useRouter();
  const id = router.params.id ?? '';
  const intervalMs = Number(router.params.pi) || DEFAULT_POLL_INTERVAL_MS;
  const timeoutMs = Number(router.params.to) || DEFAULT_TIMEOUT_MS;

  const { result, error, elapsedMs, isTimedOut } = usePolling<GetInspectionResponse>({
    fetch: () => getInspection(id),
    intervalMs,
    timeoutMs,
    stopWhen: (r) => r.status === 'succeeded' || r.status === 'failed',
  });

  if (error) {
    const ui = mapApiError(error);
    return <DesktopErrorView userMessage={ui.userMessage} allowRetry={ui.allowRetry} />;
  }

  if (isTimedOut) {
    return <DesktopErrorView userMessage="AI 分析超时，请重试" allowRetry />;
  }

  if (!result || result.status === 'queued' || result.status === 'processing') {
    const step = result?.status === 'processing' ? 2 : 1;
    return (
      <View className={styles.page}>
        {/* 轮询是巡检流程中的一步：activeTab=inspect + ariaCurrent=step
            （nav "巡检" 链接指向 home，当前页不是 home，语义应为 step 而非 page —— critique P0 修复） */}
        <TopNav
          activeTab="inspect"
          ariaCurrent="step"
          onTabChange={(tab) => {
            if (tab === 'inspect') goHomeReplay();
          }}
        />
        <View className={styles.processing}>
          <ProgressTracker
            currentStep={step}
            elapsedMs={elapsedMs}
            onCancel={goHomeReplay}
          />
        </View>
      </View>
    );
  }

  if (result.status === 'failed') {
    const err = result.error;
    const fakeApiError = new ApiError(
      err?.code ?? 'INTERNAL',
      err?.user_message ?? '分析失败，请重试',
      500,
    );
    const ui = mapApiError(fakeApiError);
    return <DesktopErrorView userMessage={ui.userMessage} allowRetry={ui.allowRetry} />;
  }

  // 用 URL 上的 id（上传时 rememberPhoto 就是用它做 key）做照片查找的权威 id；
  // 旧版后端可能把 LLM 占位符 UUID 写进 report.inspection_id —— 不可信。
  // created_at 同理：outer 字段来自 DB row、可信；report.created_at 是 LLM 占位符。
  return (
    <DesktopSucceededReport
      report={result.report!}
      canonicalId={id}
      createdAt={result.created_at}
    />
  );
}

// 报告页"返回首页" —— 直接 reLaunch 重置页面栈到 index。
//
// 之前的实现是 navigateBack ➜ catch reLaunch。坑在 H5 端：Taro.navigateBack 走的是
// window.history.back()，没有上一项时浏览器是 no-op，但 Promise 依然 resolve、不抛
// 异常 —— 于是 catch 永远不进，按钮"看似可点但无反应"。打印 / 直接打开报告 URL /
// 浏览器 back-forward cache 复活页面 时都会触发这个 stuck 状态。
//
// 这里干脆放弃 navigateBack 路径：用户点"← 报告" / "巡检"标签的语义就是"回到首页
// 重新开始一次巡检"，reLaunch 直接清栈跳 /pages/index/index 才是想要的行为。
async function goHomeReplay(): Promise<void> {
  await Taro.reLaunch({ url: '/pages/index/index' });
}

function DesktopErrorView({
  userMessage,
  allowRetry,
}: {
  userMessage: string;
  allowRetry: boolean;
}) {
  return (
    <View className={styles.page}>
      <TopNav
        activeTab="reports"
        onTabChange={(tab) => {
          if (tab === 'inspect') goHomeReplay();
        }}
      />
      <View className={styles.centered}>
        <View className={styles.errorBox}>
          <Icon name="x-circle" size={56} color="var(--high)" />
          <Text className={styles.errorText}>{userMessage}</Text>
          {allowRetry && <Text className={styles.retryHint}>请返回首页重新上传</Text>}
        </View>
      </View>
    </View>
  );
}

function shortId(inspectionId: string): string {
  return inspectionId.slice(0, 12).toUpperCase();
}

function DesktopSucceededReport({
  report,
  canonicalId,
  createdAt,
}: {
  report: ReportPayload;
  canonicalId: string;
  createdAt: string;
}) {
  const sorted = sortBySeverity(report.hazards);
  const severity = report.overall_severity;
  // canonicalId 来自 URL（与上传时 rememberPhoto 用的 key 同源）；
  // 仅当 URL 丢了 id 时退到 report.inspection_id —— 后者在旧后端上是 LLM 占位符。
  const idForLookup = canonicalId || report.inspection_id;
  const no = shortId(idForLookup);
  // 桌面上传时先存 blob URL 立刻挂屏，FileReader 异步把 data URL 写回 store；
  // 这里轮询 store 直到拿到 data URL —— blob URL 在 window.print() / 导出 PDF
  // 时不稳（Chrome 打印管线偶尔取不到 blob 数据，照片在 PDF 里整张消失），
  // data URL 自带字节流不存在这个问题。命中 data: 即 stop。
  const [photo, setPhoto] = useState(() => getPhotoFor(idForLookup));
  useEffect(() => {
    if (photo?.src?.startsWith('data:')) return;
    const tick = () => {
      const fresh = getPhotoFor(idForLookup);
      if (fresh && fresh.src !== photo?.src) setPhoto(fresh);
      return fresh?.src?.startsWith('data:') ?? false;
    };
    if (tick()) return;
    const timer = setInterval(() => {
      if (tick()) clearInterval(timer);
    }, 500);
    // 30s 上限够 FileReader 处理 10MB+ 图；之后照片要么已升级、要么留着 blob 也能显示
    const stop = setTimeout(() => clearInterval(timer), 30000);
    return () => {
      clearInterval(timer);
      clearTimeout(stop);
    };
  }, [idForLookup, photo?.src]);

  const notImplemented = (label: string) => () =>
    Taro.showToast({ title: `${label}：开发中`, icon: 'none', duration: 2000 });

  const handleExportPdf = () => {
    if (process.env.TARO_ENV === 'h5' && typeof window !== 'undefined') {
      window.print();
    } else {
      Taro.showToast({ title: '导出 PDF 需在 H5 端使用', icon: 'none', duration: 2000 });
    }
  };

  return (
    <View className={styles.page}>
      <TopNav
        className={styles.printHide}
        activeTab="reports"
        onTabChange={(tab) => {
          if (tab === 'inspect') goHomeReplay();
        }}
      />

      <View className={styles.container}>
        <View className={styles.breadcrumb}>
          <View
            className={styles.crumbItem}
            role="button"
            aria-label="返回首页"
            onClick={goHomeReplay}
          >
            <Text>← 报告</Text>
          </View>
          <Icon name="chevron-right" size={12} color="var(--ink-3)" />
          <Text className={styles.crumbCurrent}>NO.{no}</Text>
        </View>

        <View className={styles.header}>
          <View className={styles.headerLeft}>
            <View className={styles.headerTopRow}>
              <SeverityPill level={severity} variant="solid" />
              <Text className={styles.headerNo}>NO.{no}</Text>
            </View>
            <Text className={styles.h1}>现场巡检报告</Text>
            {/* 2026-05-24：删 "由 Claude Vision 分析" (critique P5 dev-chrome)。
                改为只显示中性的隐患计数 + 时间。 */}
            <Text className={styles.lede}>{report.hazards.length} 项隐患 · {createdAt.slice(0, 16).replace('T', ' ')}</Text>
          </View>
          <View className={styles.headerActions}>
            {/* CTA 主次对齐 mockup：分享 primary（mockup 主推班组流转）+ 导出 PDF ghost。
                "转派班组" placeholder 删除（与"分享"语义重叠且未实装） */}
            <Button variant="primary" onTap={notImplemented('分享给班组')}>
              <Icon name="share" size={16} color="var(--on-accent)" />
              <Text className={styles.btnText}>分享给班组</Text>
            </Button>
            <Button variant="secondary" onTap={handleExportPdf}>
              <Icon name="download" size={16} color="var(--ink)" />
              <Text className={styles.btnText}>导出 PDF</Text>
            </Button>
          </View>
        </View>

        <View className={styles.hero}>
          <View className={styles.heroLeft}>
            {/* Hero 高度被 sidebar 卡片决定（grid align-items:stretch），
                给 Photo 一个高度上限避免 4:3 在窄列上拉得过高吃满视口。
                clamp(240, 36vh, 360) —— 1280×800 → 288; 1920×1080 → ~360。 */}
            <Photo
              src={photo?.src ?? ''}
              height="clamp(240px, 36vh, 360px)"
              overlay={!!photo}
              meta={`NO.${no} · ${createdAt.slice(0, 19).replace('T', ' ')}`}
            />
          </View>
          <View className={styles.heroRight}>
            <ReportSidebar report={report} hazardCount={sorted.length} />
          </View>
        </View>

        {report.plain_warning && (
          <View className={styles.alarmRow}>
            <AlarmBox>{report.plain_warning}</AlarmBox>
          </View>
        )}

        <View className={styles.listCard}>
          <View className={styles.listHead}>
            <View className={styles.listTitleWrap}>
              <Text className={styles.listTitle}>隐患明细</Text>
              <Text className={styles.listCaption}>按严重程度排序 · 共 {sorted.length} 项</Text>
            </View>
            <View className={styles.listFilters}>
              {/* 2026-05-24：chip 加 count；count=0 时 aria-disabled (critique P6 修复) */}
              {(() => {
                const high = sorted.filter((h) => h.severity === 'high').length;
                const med = sorted.filter((h) => h.severity === 'medium').length;
                const low = sorted.filter((h) => h.severity === 'low').length;
                const chips: Array<{ key: string; label: string; count: number; active?: boolean }> = [
                  { key: 'all', label: '全部', count: sorted.length, active: true },
                  { key: 'high', label: '高', count: high },
                  { key: 'med', label: '中', count: med },
                  { key: 'low', label: '低', count: low },
                ];
                return chips.map((c) => {
                  const disabled = c.count === 0 && c.key !== 'all';
                  return (
                    <View
                      key={c.key}
                      className={[
                        styles.filterChip,
                        c.active ? styles.filterChipActive : '',
                        disabled ? styles.filterChipDisabled : '',
                      ]
                        .filter(Boolean)
                        .join(' ')}
                      aria-disabled={disabled ? 'true' : undefined}
                    >
                      <Text>
                        {c.label} <Text className={styles.filterChipCount}>{c.count}</Text>
                      </Text>
                    </View>
                  );
                });
              })()}
            </View>
          </View>
          <View className={styles.listBody}>
            {sorted.map((h, idx) => (
              <HazardItem
                hazard={h}
                key={`${h.category_code}-${idx}`}
                index={idx + 1}
                onAction={() =>
                  Taro.navigateTo({
                    url: `/pages/report-detail/index?id=${canonicalId}&h=${idx}`,
                  })
                }
              />
            ))}
          </View>
        </View>

        <View className={styles.signoff}>
          {(['安全员', '班组长', '项目经理'] as const).map((role) => (
            <View key={role} className={styles.signCell}>
              <Text className={styles.signRole}>{role}</Text>
              <View className={styles.signMain}>
                <Text className={styles.signName}>—</Text>
                <Text className={styles.signStatus}>待签字</Text>
              </View>
              <View className={styles.signFoot}>
                <Text className={styles.signTime}>—</Text>
                <Text className={styles.signRemind} onClick={notImplemented(`提醒 ${role}`)}>
                  提醒 →
                </Text>
              </View>
            </View>
          ))}
        </View>

        <View className={styles.footer}>
          {/* 2026-05-24：删 "v0.3.1" (critique P5 dev-chrome 版本号)，保留 NO 与"服务可用"指示。 */}
          <Text className={styles.footerLeft}>服务可用</Text>
          <Text className={styles.footerRight}>NO.{no} · 报告完</Text>
        </View>
      </View>
    </View>
  );
}
