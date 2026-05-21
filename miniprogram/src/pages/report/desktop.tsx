/**
 * DesktopReport —— 桌面布局的报告页。
 *
 * 与 mobile.tsx 行为对齐：用同一个 usePolling + getInspection + mapApiError 链路，
 * 区别只在 UI 编排——左 sticky `ReportSidebar`（4fr），右滚动 hazard 列表（6fr）。
 * `DesktopErrorView` 故意是本地组件而非提到 shared module；mobile 的 ErrorView 是
 * 全屏纵列布局，桌面要居中卡片，差异不值得抽象。YAGNI on sharing。
 *
 * `formatIdentifier` / `hash` 与 mobile.tsx 重复——同样 YAGNI，等真的有第三处再抽。
 */
import Taro from '@tarojs/taro';
import { View, Text } from '@tarojs/components';

import { usePolling } from '../../hooks/usePolling';
import { getInspection } from '../../api/inspections';
import { HazardCard } from '../../components/HazardCard';
import { HeaderBand } from '../../components/HeaderBand';
import { Icon } from '../../components/Icon';
import { ProgressIndicator } from '../../components/ProgressIndicator';
import { ReportSidebar } from '../../components/desktop/ReportSidebar';
import { sortBySeverity } from '../../utils/severity';
import { mapApiError } from '../../utils/errorMessage';
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
      <View className={styles.centered}>
        <ProgressIndicator currentStep={step} elapsedMs={elapsedMs} />
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

  return <DesktopSucceededReport report={result.report!} />;
}

function DesktopErrorView({
  userMessage,
  allowRetry,
}: {
  userMessage: string;
  allowRetry: boolean;
}) {
  return (
    <View className={styles.centered}>
      <View className={styles.errorBox}>
        <Icon name="x-circle" size={56} color="#C8281C" />
        <Text className={styles.errorText}>{userMessage}</Text>
        {allowRetry && <Text className={styles.retryHint}>请返回首页重新上传</Text>}
      </View>
    </View>
  );
}

function DesktopSucceededReport({ report }: { report: ReportPayload }) {
  const sorted = sortBySeverity(report.hazards);
  return (
    <View className={styles.page}>
      <HeaderBand
        identifier={`NO.${formatIdentifier(report.created_at)}`}
        subtitle={report.summary}
      />

      <View className={styles.body}>
        <View className={styles.aside}>
          <ReportSidebar report={report} hazardCount={sorted.length} />
        </View>

        <View className={styles.main}>
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
        </View>
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
