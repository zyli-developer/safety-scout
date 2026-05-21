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

import { usePolling } from '../../hooks/usePolling';
import { getInspection } from '../../api/inspections';
import { HazardItem } from '../../components/HazardItem';
import { ProgressIndicator } from '../../components/ProgressIndicator';
import { Icon } from '../../components/Icon';
import { AppBar } from '../../components/AppBar';
import { Button } from '../../components/Button';
import { SeverityPill } from '../../components/SeverityPill';
import { AlarmBox } from '../../components/AlarmBox';
import { sortBySeverity } from '../../utils/severity';
import { mapApiError } from '../../utils/errorMessage';
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
    return (
      <View className={styles.page}>
        <AppBar title="巡检报告" />
        <View className={styles.processingWrap}>
          <ProgressIndicator currentStep={step} elapsedMs={elapsedMs} />
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

  return <SucceededReport report={result.report!} />;
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

function SucceededReport({ report }: { report: ReportPayload }) {
  const sorted = sortBySeverity(report.hazards);
  const severity = report.overall_severity;
  const counts = countBySeverity(sorted);
  const total = sorted.length;

  const notImplemented = (label: string) => () =>
    Taro.showToast({ title: `${label}：开发中`, icon: 'none', duration: 2000 });

  return (
    <View className={styles.page}>
      <AppBar
        title="巡检报告"
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
        <Button variant="secondary" block onTap={notImplemented('导出 PDF')}>
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
