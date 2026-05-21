import Taro from '@tarojs/taro';
import { View, Text } from '@tarojs/components';

import { usePolling } from '../../hooks/usePolling';
import { getInspection } from '../../api/inspections';
import { HazardCard } from '../../components/HazardCard';
import { ProgressIndicator } from '../../components/ProgressIndicator';
import { Icon } from '../../components/Icon';
import { HeaderBand } from '../../components/HeaderBand';
import { sortBySeverity, SEVERITY_LABEL, SEVERITY_COLOR } from '../../utils/severity';
import { mapApiError } from '../../utils/errorMessage';
import { relativeTime } from '../../utils/relativeTime';
import { ApiError } from '../../api/client';
import {
  DEFAULT_POLL_INTERVAL_MS,
  DEFAULT_TIMEOUT_MS,
} from '../../config';
import type { GetInspectionResponse } from '../../types/inspection';
import type { ReportPayload } from '../../types/report';

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
    return (
      <ErrorView userMessage={ui.userMessage} allowRetry={ui.allowRetry} />
    );
  }

  if (isTimedOut) {
    return <ErrorView userMessage="AI 分析超时，请重试" allowRetry={true} />;
  }

  if (!result || result.status === 'queued' || result.status === 'processing') {
    const step = result?.status === 'processing' ? 2 : 1;
    return <ProgressIndicator currentStep={step} elapsedMs={elapsedMs} />;
  }

  if (result.status === 'failed') {
    const err = result.error;
    const fakeApiError = new ApiError(
      err?.code ?? 'INTERNAL',
      err?.user_message ?? '分析失败，请重试',
      500,
    );
    const ui = mapApiError(fakeApiError);
    return (
      <ErrorView userMessage={ui.userMessage} allowRetry={ui.allowRetry} />
    );
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
      <Icon name="x-circle" size={48} color="#007AFF" />
      <Text className={styles.errorText}>{userMessage}</Text>
      {allowRetry && (
        <Text className={styles.retryHint}>请返回首页重新拍照</Text>
      )}
    </View>
  );
}

function SucceededReport({ report }: { report: ReportPayload }) {
  const sorted = sortBySeverity(report.hazards);
  const severity = report.overall_severity;
  const meta = `${SEVERITY_LABEL[severity]} · ${relativeTime(report.created_at)}`;
  return (
    <View className={styles.page}>
      <HeaderBand
        identifier={`NO.${formatIdentifier(report.created_at)}`}
        subtitle={meta}
      />

      <View className={styles.titleBlock}>
        <Text className={styles.eyebrow}>INSPECTION REPORT</Text>
        <Text className={styles.h1}>现场巡检报告</Text>
      </View>

      <View className={styles.hero}>
        <View className={styles.heroLeft}>
          <Text className={styles.heroCount} style={{ color: SEVERITY_COLOR[severity] }}>
            {sorted.length}
          </Text>
          <Text className={styles.heroCountLabel}>项隐患待整改</Text>
        </View>
        <View className={styles.heroRight}>
          <Text className={styles.heroSeverity} style={{ color: SEVERITY_COLOR[severity] }}>
            {SEVERITY_LABEL[severity]}
          </Text>
          <Text className={styles.heroSeverityLabel}>风险等级判定</Text>
        </View>
      </View>

      <View className={styles.summarySection}>
        <View className={styles.summaryLabel}>
          <Text className={styles.summaryLabelBar}>▎</Text>
          <Text className={styles.summaryLabelText}>现场总览</Text>
        </View>
        <Text className={styles.summaryText}>{report.summary}</Text>
        {report.plain_warning && (
          <Text className={styles.warning}>{report.plain_warning}</Text>
        )}
      </View>

      <View className={styles.sectionRule}>
        <Text className={styles.sectionLabel}>隐患明细</Text>
      </View>

      {sorted.map((h, idx) => (
        <HazardCard
          hazard={h}
          key={`${h.category_code}-${idx}`}
          index={idx + 1}
          total={sorted.length}
        />
      ))}

      <View className={styles.footer}>
        <Text className={styles.footerText}>⌖ AI ENGINE v3 · Claude Vision</Text>
      </View>
    </View>
  );
}

function formatIdentifier(iso: string): string {
  try {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return iso;
    const yyyy = d.getFullYear();
    const mm = String(d.getMonth() + 1).padStart(2, '0');
    const dd = String(d.getDate()).padStart(2, '0');
    // Production system would use a sequence number from the backend; for now,
    // a short hash of the ISO string is good enough to look like an identifier.
    const seq = Math.abs(hash(iso)) % 10000;
    return `${yyyy}-${mm}-${dd}-${String(seq).padStart(4, '0')}`;
  } catch {
    return iso;
  }
}
function hash(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h << 5) - h + s.charCodeAt(i);
  return h;
}
