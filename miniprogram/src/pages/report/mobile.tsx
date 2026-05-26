/**
 * 移动端报告页 — Clean & Minimal 重排：
 *   AppBar / 概要卡（数字 + pill + summary + breakdown）/ AlarmBox / 隐患列表 /
 *   粘性底部 actbar（导出 PDF / 转派班组）。
 *
 * 状态分支保持原样：error / timeout / processing / failed / succeeded。
 * 现场照片大图：后端 GET 报告暂未带 photo_url，先省略；接入后在 AppBar 下追加 Photo。
 *
 * "导出 PDF" / "转派班组" 是 placeholder action —— 后端尚未实现，按下走 toast 提示。
 */
import Taro from '@tarojs/taro';
import { View, Text } from '@tarojs/components';
import { useEffect, useState } from 'react';

import { usePolling } from '../../hooks/usePolling';
import { getInspection } from '../../api/inspections';
import { HazardItem } from '../../components/HazardItem';
import { FeedbackModal } from '../../components/FeedbackModal';
import { ProgressTracker } from '../../components/ProgressTracker';
import { Icon } from '../../components/Icon';
import { AppBar } from '../../components/AppBar';
import { Button } from '../../components/Button';
import { SeverityPill } from '../../components/SeverityPill';
import { AlarmBox } from '../../components/AlarmBox';
import { Photo } from '../../components/Photo';
import { sortBySeverity } from '../../utils/severity';
import { mapApiError } from '../../utils/errorMessage';
import { getPhotoFor } from '../../utils/lastPhotoStore';
import { appendHistory } from '../../utils/historyStore';
import { ApiError } from '../../api/client';
import {
  DEFAULT_POLL_INTERVAL_MS,
  DEFAULT_TIMEOUT_MS,
} from '../../config';
import type { GetInspectionResponse } from '../../types/inspection';
import type { GetInspectionV2Response, SchemaVersion } from '../../types/inspection-v2';
import type { ReportPayload } from '../../types/report';
import type { Severity } from '../../types/report';
import { mapV2ReportToV1 } from '../../utils/v2Adapter';

import styles from './mobile.module.scss';

export default function MobileReport() {
  const router = Taro.useRouter();
  const id = router.params.id ?? '';
  const intervalMs = Number(router.params.pi) || DEFAULT_POLL_INTERVAL_MS;
  const timeoutMs = Number(router.params.to) || DEFAULT_TIMEOUT_MS;
  // URL ?v=2 决定 GET 走哪条；缺省 v1 与历史 URL 兼容。
  const schemaVersion: SchemaVersion = router.params.v === '2' ? 'v2' : 'v1';

  const { result, error, elapsedMs, isTimedOut } =
    usePolling<GetInspectionResponse | GetInspectionV2Response>({
      fetch: () => getInspection(id, schemaVersion),
      intervalMs,
      timeoutMs,
      stopWhen: (r) => r.status === 'succeeded' || r.status === 'failed',
    });

  if (error) {
    const ui = mapApiError(error);
    return <ErrorView userMessage={ui.userMessage} allowRetry={ui.allowRetry} />;
  }

  if (isTimedOut) {
    return <ErrorView userMessage="AI 分析超时，请重试" allowRetry />;
  }

  if (!result || result.status === 'queued' || result.status === 'processing') {
    const step = result?.status === 'processing' ? 2 : 1;
    const cancelToHome = () => Taro.reLaunch({ url: '/pages/index/index' });
    return (
      <View className={styles.page}>
        <AppBar title="巡检报告" onBack={cancelToHome} />
        <View className={styles.processingWrap}>
          <ProgressTracker
            currentStep={step}
            elapsedMs={elapsedMs}
            onCancel={cancelToHome}
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
    return <ErrorView userMessage={ui.userMessage} allowRetry={ui.allowRetry} />;
  }

  // 见 desktop.tsx 注释：URL 上的 id + outer created_at 才可信，
  // report.inspection_id / report.created_at 在旧后端上是 LLM 占位符。
  // v2 报告先经 adapter 映射成 v1 shape，让现有 SucceededReport 组件直接复用；
  // 损失（image_summary / no_findings / uncertain 明细 / location / confidence）
  // 见 utils/v2Adapter.ts 顶部文档，留后续 PR 增量。
  const v1Report: ReportPayload =
    schemaVersion === 'v2' && result.report
      ? mapV2ReportToV1(result.report as any, id, result.created_at)
      : (result.report! as ReportPayload);
  return (
    <SucceededReport
      report={v1Report}
      canonicalId={id}
      createdAt={result.created_at}
      schemaVersion={schemaVersion}
    />
  );
}

function ErrorView({
  userMessage,
  allowRetry,
}: {
  userMessage: string;
  allowRetry: boolean;
}) {
  return (
    <View className={styles.errorView}>
      <Icon name="x-circle" size={48} color="var(--high)" />
      <Text className={styles.errorText}>{userMessage}</Text>
      {allowRetry && <Text className={styles.retryHint}>请返回首页重新拍照</Text>}
    </View>
  );
}

function countBySeverity(hazards: readonly { severity: Severity }[]) {
  return hazards.reduce(
    (acc, h) => {
      acc[h.severity] += 1;
      return acc;
    },
    { high: 0, medium: 0, low: 0 } as Record<Severity, number>,
  );
}

function SucceededReport({
  report,
  canonicalId,
  createdAt,
  schemaVersion,
}: {
  report: ReportPayload;
  canonicalId: string;
  createdAt: string;
  schemaVersion: SchemaVersion;
}) {
  const sorted = sortBySeverity(report.hazards);
  const severity = report.overall_severity;
  const counts = countBySeverity(sorted);
  const total = sorted.length;
  // 重大事故隐患计数（建质规〔2024〕5号）；> 0 时 summaryCard 内插红色 row。
  const majorCount = sorted.filter((h) => h.is_major === true).length;
  // canonicalId 来自 URL（与上传时 rememberPhoto 同源），
  // 仅在 URL 丢 id 时退到 report.inspection_id（旧后端为 LLM 占位符）。
  const idForLookup = canonicalId || report.inspection_id;

  // 2026-05-24 B8：记录到本地 history store（localStorage 临时方案）
  // schemaVersion 必须持久化 —— history 页跳回此页时按它决定 URL 是否带 ?v=2
  // （否则 v2 inspection 会被按 v1 调 GET → 404）
  useEffect(() => {
    appendHistory({
      inspectionId: idForLookup,
      capturedAt: Date.parse(createdAt) || Date.now(),
      summary: report.summary,
      overallSeverity: severity,
      hazardCount: total,
      breakdown: counts,
      status: 'pending',
      schemaVersion,
    });
  }, [idForLookup, schemaVersion]);
  const shortNo = idForLookup.slice(0, 12).toUpperCase();
  const photoMeta = `NO.${shortNo} · ${createdAt.slice(0, 16).replace('T', ' ')}`;
  // 反馈 modal 状态：null=关闭；{checkId?} 形式打开（checkId 缺省 → 漏报模式）。
  // 仅 v2 显示反馈入口（v1 没有 feedback API）。
  const [feedbackTarget, setFeedbackTarget] = useState<{ checkId?: string } | null>(null);
  const showFeedback = schemaVersion === 'v2';
  // 见 desktop.tsx 同段注释：blob URL → data URL 升级轮询，
  // 让 PDF 导出时拿到的是 data: src，避免 Chrome 打印管线取不到 blob 数据。
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
    const stop = setTimeout(() => clearInterval(timer), 30000);
    return () => {
      clearInterval(timer);
      clearTimeout(stop);
    };
  }, [idForLookup, photo?.src]);

  const handleExportPdf = () => {
    if (process.env.TARO_ENV === 'h5' && typeof window !== 'undefined') {
      window.print();
    } else {
      Taro.showToast({ title: '导出 PDF 需在 H5 端使用', icon: 'none', duration: 2000 });
    }
  };

  return (
    <View className={styles.page}>
      <AppBar
        className={styles.printHide}
        title="巡检报告"
        onBack={() => Taro.reLaunch({ url: '/pages/index/index' })}
        /* 2026-05-26：删除 AppBar 右侧"分享 / 更多"两个 IconBtn ——
           原本都是 notImplemented toast 桩按钮。Product UI 不在顶部
           chrome 上放假动作；功能真做完时通过 right={...} 注回。 */
      />

      {/* 现场照片大图（4:3）—— 报告即报告，照片永远是核心证据。
          src 优先来自 lastPhotoStore（上传时缓存的本地 tempFilePath / blob URL）；
          后端 GET 报告无 photo_url 时 fallback 灰底占位。 */}
      <View className={styles.photoWrap}>
        <Photo src={photo?.src ?? ''} ratio="4/3" overlay={!!photo} meta={photoMeta} />
      </View>

      {/* 2026-05-26 层级重排：AlarmBox（plain_warning，紧急简短）移到 SummaryCard 之前。
          安全员第一眼应该看到「问题是什么」（plain_warning），SummaryCard 提供支撑数据。
          原顺序 SummaryCard→AlarmBox 让两个红色块挤在一起，hierarchy 不清。 */}
      {report.plain_warning && (
        <View className={styles.alarmWrap}>
          <AlarmBox>{report.plain_warning}</AlarmBox>
        </View>
      )}

      <View className={styles.summaryWrap}>
        <View className={styles.summaryCard}>
          <View className={styles.summaryHead}>
            <View className={styles.summaryHeadLeft}>
              <Text className={styles.eyebrow}>检出隐患</Text>
              <View className={styles.summaryCountRow}>
                <Text className={styles.summaryCount}>{total}</Text>
                <Text className={styles.summaryCountUnit}>项</Text>
              </View>
            </View>
            <SeverityPill level={severity} variant="solid" />
          </View>
          <Text className={styles.summaryText}>{report.summary}</Text>
          <View className={styles.breakdown}>
            <SeverityPill level="high" count={counts.high} />
            <SeverityPill level="medium" count={counts.medium} />
            <SeverityPill level="low" count={counts.low} />
          </View>
          {majorCount > 0 && (
            <View
              className={styles.majorRow}
              role="status"
              aria-label={`重大事故隐患 ${majorCount} 项`}
            >
              <View className={styles.majorTag}>
                <Text>重大隐患</Text>
              </View>
              <Text className={styles.majorCount}>{majorCount} 项</Text>
              <Text className={styles.majorBasisHint}>建质规〔2024〕5号</Text>
            </View>
          )}
        </View>
      </View>

      <View className={styles.hazardSection}>
        <Text className={styles.sectionTitle}>隐患明细</Text>
        <Text className={styles.sectionCaption}>按严重程度排序</Text>
        <View className={styles.hazardList}>
          {sorted.map((h, i) => (
            <HazardItem
              hazard={h}
              key={`${h.category_code}-${i}`}
              index={i + 1}
              onAction={() =>
                Taro.navigateTo({
                  url: `/pages/report-detail/index?id=${canonicalId}&h=${i}${schemaVersion === 'v2' ? '&v=2' : ''}`,
                })
              }
              onFeedback={
                // v2 适配器把 check_id 写进了 category_code，可直接当 check_id 用
                showFeedback ? () => setFeedbackTarget({ checkId: h.category_code }) : undefined
              }
            />
          ))}
        </View>
        {showFeedback && (
          <View className={styles.missedRow}>
            <View
              className={styles.missedLink}
              role="button"
              aria-label="反馈：我们漏了什么"
              onClick={() => setFeedbackTarget({})}
            >
              <Text>我们漏了什么？提交反馈 →</Text>
            </View>
          </View>
        )}
      </View>

      {/* 2026-05-26：删除"分享给班组" primary CTA —— 之前是 notImplemented toast 桩，
          主 CTA 撑桩在 product UI 是信任失败。"导出 PDF" 真做完了（调 window.print），
          作为唯一动作保留，提升到 primary。后续真做"分享给班组"时通过 primary 注回。 */}
      <View className={styles.inlineActions}>
        <Button variant="primary" block onTap={handleExportPdf}>
          <Icon name="download" size={16} color="var(--on-accent)" />
          <Text className={styles.actbarText}>导出 PDF</Text>
        </Button>
      </View>

      {showFeedback && (
        <FeedbackModal
          isOpen={feedbackTarget !== null}
          onClose={() => setFeedbackTarget(null)}
          inspectionId={canonicalId}
          checkId={feedbackTarget?.checkId}
        />
      )}
    </View>
  );
}
