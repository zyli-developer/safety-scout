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
import { ApiError } from '../../api/client';
import {
  DEFAULT_POLL_INTERVAL_MS,
  DEFAULT_TIMEOUT_MS,
} from '../../config';
import type { GetInspectionResponse } from '../../types/inspection';
import type { ReportPayload } from '../../types/report';
import type { Severity } from '../../types/report';

import styles from './mobile.module.scss';

export default function MobileReport() {
  const router = Taro.useRouter();
  const id = router.params.id ?? '';
  const intervalMs = Number(router.params.pi) || DEFAULT_POLL_INTERVAL_MS;
  const timeoutMs = Number(router.params.to) || DEFAULT_TIMEOUT_MS;

  const { result, error, elapsedMs, isTimedOut } =
    usePolling<GetInspectionResponse>({
      fetch: () => getInspection(id),
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
  return (
    <SucceededReport
      report={result.report!}
      canonicalId={id}
      createdAt={result.created_at}
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
}: {
  report: ReportPayload;
  canonicalId: string;
  createdAt: string;
}) {
  const sorted = sortBySeverity(report.hazards);
  const severity = report.overall_severity;
  const counts = countBySeverity(sorted);
  const total = sorted.length;
  // canonicalId 来自 URL（与上传时 rememberPhoto 同源），
  // 仅在 URL 丢 id 时退到 report.inspection_id（旧后端为 LLM 占位符）。
  const idForLookup = canonicalId || report.inspection_id;
  const shortNo = idForLookup.slice(0, 12).toUpperCase();
  const photoMeta = `NO.${shortNo} · ${createdAt.slice(0, 16).replace('T', ' ')}`;
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
      <AppBar
        className={styles.printHide}
        title="巡检报告"
        onBack={() => Taro.reLaunch({ url: '/pages/index/index' })}
        right={
          <>
            <View
              className={styles.iconBtn}
              role="button"
              aria-label="分享"
              onClick={notImplemented('分享')}
            >
              <Icon name="share" size={16} color="var(--ink-2)" />
            </View>
            <View
              className={styles.iconBtn}
              role="button"
              aria-label="更多"
              onClick={notImplemented('更多')}
            >
              <Icon name="dots" size={16} color="var(--ink-2)" />
            </View>
          </>
        }
      />

      {/* 现场照片大图（4:3）—— 报告即报告，照片永远是核心证据。
          src 优先来自 lastPhotoStore（上传时缓存的本地 tempFilePath / blob URL）；
          后端 GET 报告无 photo_url 时 fallback 灰底占位。 */}
      <View className={styles.photoWrap}>
        <Photo src={photo?.src ?? ''} ratio="4/3" overlay={!!photo} meta={photoMeta} />
      </View>

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
        </View>
      </View>

      {report.plain_warning && (
        <View className={styles.alarmWrap}>
          <AlarmBox>{report.plain_warning}</AlarmBox>
        </View>
      )}

      <View className={styles.hazardSection}>
        <Text className={styles.sectionTitle}>隐患明细</Text>
        <Text className={styles.sectionCaption}>按严重程度排序</Text>
        <View className={styles.hazardList}>
          {sorted.map((h, i) => (
            <HazardItem hazard={h} key={`${h.category_code}-${i}`} index={i + 1} />
          ))}
        </View>
      </View>

      <View className={styles.actbar}>
        <Button variant="secondary" block onTap={handleExportPdf}>
          <Icon name="download" size={16} color="var(--ink)" />
          <Text className={styles.actbarText}>导出 PDF</Text>
        </Button>
        <Button variant="primary" block onTap={notImplemented('转派班组')}>
          <Icon name="share" size={16} color="var(--on-accent)" />
          <Text className={styles.actbarText}>转派班组</Text>
        </Button>
      </View>
    </View>
  );
}
