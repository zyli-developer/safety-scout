import Taro from '@tarojs/taro';
import { View, Text } from '@tarojs/components';

import { usePolling } from '../../hooks/usePolling';
import { getInspection } from '../../api/inspections';
import { HazardCard } from '../../components/HazardCard';
import { ProgressIndicator } from '../../components/ProgressIndicator';
import { Icon } from '../../components/Icon';
import { HeaderBand } from '../../components/HeaderBand';
import { sortBySeverity, SEVERITY_LABEL } from '../../utils/severity';
import { mapApiError } from '../../utils/errorMessage';
import { relativeTime } from '../../utils/relativeTime';
import { ApiError } from '../../api/client';
import {
  DEFAULT_POLL_INTERVAL_MS,
  DEFAULT_TIMEOUT_MS,
} from '../../config';
import type { GetInspectionResponse } from '../../types/inspection';
import type { ReportPayload } from '../../types/report';

import styles from './index.module.scss';

export default function ReportPage() {
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
      <Icon name="x-circle" size={48} color="#FF3B30" />
      <Text className={styles.errorText}>{userMessage}</Text>
      {allowRetry && (
        <Text className={styles.retryHint}>请返回首页重新拍照</Text>
      )}
    </View>
  );
}

function formatTimestamp(iso: string): string {
  try {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return iso;
    const yyyy = d.getFullYear();
    const mm = String(d.getMonth() + 1).padStart(2, '0');
    const dd = String(d.getDate()).padStart(2, '0');
    const hh = String(d.getHours()).padStart(2, '0');
    const mi = String(d.getMinutes()).padStart(2, '0');
    return `${yyyy}-${mm}-${dd} ${hh}:${mi}`;
  } catch {
    return iso;
  }
}

function SucceededReport({ report }: { report: ReportPayload }) {
  const sorted = sortBySeverity(report.hazards);
  const severity = report.overall_severity;
  const meta = `${SEVERITY_LABEL[severity]} · ${relativeTime(report.created_at)}`;
  return (
    <View className={styles.reportPage}>
      <HeaderBand identifier={`NO.${formatIdentifier(report.created_at)}`} subtitle={meta} />

      <View className={styles.pageHeader}>
        <Text className={styles.pageEyebrow}>{formatTimestamp(report.created_at)}</Text>
        <Text className={styles.pageTitle}>隐患报告</Text>
      </View>

      <View className={styles.summaryCard}>
        <Text className={styles.summaryLabel}>现场总览</Text>
        <Text className={styles.summaryText}>{report.summary}</Text>
      </View>

      <View className={styles.sectionHeader}>
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
