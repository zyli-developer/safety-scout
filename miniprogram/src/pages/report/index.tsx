import Taro from '@tarojs/taro';
import { View, Text } from '@tarojs/components';
import { usePolling } from '../../hooks/usePolling';
import { getInspection } from '../../api/inspections';
import { PlainWarningCard } from '../../components/PlainWarningCard';
import { HazardCard } from '../../components/HazardCard';
import { ProgressIndicator } from '../../components/ProgressIndicator';
import { sortBySeverity } from '../../utils/severity';
import { mapApiError } from '../../utils/errorMessage';
import { ApiError } from '../../api/client';
import {
  DEFAULT_POLL_INTERVAL_MS,
  DEFAULT_TIMEOUT_MS,
} from '../../config';
import type { GetInspectionResponse } from '../../types/inspection';
import type { ReportPayload, Severity } from '../../types/report';
import styles from './index.module.scss';

export default function ReportPage() {
  // useRouter 是 TaroStatic 上的方法（不是 named export），所以走 Taro.useRouter()
  // —— 同时也匹配 tests/setup.ts 里 jest.mock 的形状（mock 把 useRouter 放在 default 上）。
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

  // —— 错误优先级：网络错 > 轮询超时 > 任务 failed > 进行中 > 成功

  if (error) {
    const ui = mapApiError(error);
    return (
      <ErrorView userMessage={ui.userMessage} allowRetry={ui.allowRetry} />
    );
  }

  if (isTimedOut) {
    return (
      <ErrorView
        userMessage="AI 分析超时，请重试"
        allowRetry={true}
      />
    );
  }

  if (!result || result.status === 'queued' || result.status === 'processing') {
    const step = result?.status === 'processing' ? 2 : 1;
    return <ProgressIndicator currentStep={step} elapsedMs={elapsedMs} />;
  }

  if (result.status === 'failed') {
    const err = result.error;
    // 把后端 ErrorBody 包成 ApiError 复用 mapApiError 决定 UI
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

  // succeeded —— 渲染完整报告
  return <SucceededReport report={result.report!} />;
}

// —— 子视图 —— //

function ErrorView({
  userMessage,
  allowRetry,
}: {
  userMessage: string;
  allowRetry: boolean;
}) {
  return (
    <View className={styles.errorView}>
      <Text className={styles.errorText}>{userMessage}</Text>
      {allowRetry && (
        <Text className={styles.retryHint}>请返回首页重新拍照</Text>
      )}
    </View>
  );
}

function SucceededReport({ report }: { report: ReportPayload }) {
  const sorted = sortBySeverity(report.hazards);
  return (
    <View className={styles.reportPage}>
      <PlainWarningCard
        text={report.plain_warning}
        severity={report.overall_severity as Severity}
      />
      <View className={styles.summary}>
        <Text>{report.summary}</Text>
      </View>
      {sorted.map((h, idx) => (
        <HazardCard hazard={h} key={`${h.category_code}-${idx}`} />
      ))}
    </View>
  );
}
