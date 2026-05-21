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

import { usePolling } from '../../hooks/usePolling';
import { getInspection } from '../../api/inspections';
import { HazardItem } from '../../components/HazardItem';
import { TopNav } from '../../components/TopNav';
import { Icon } from '../../components/Icon';
import { Button } from '../../components/Button';
import { Photo } from '../../components/Photo';
import { SeverityPill } from '../../components/SeverityPill';
import { AlarmBox } from '../../components/AlarmBox';
import { ProgressIndicator } from '../../components/ProgressIndicator';
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
        <TopNav activeTab="reports" />
        <View className={styles.processing}>
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
    <View className={styles.page}>
      <TopNav activeTab="reports" />
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

function DesktopSucceededReport({ report }: { report: ReportPayload }) {
  const sorted = sortBySeverity(report.hazards);
  const severity = report.overall_severity;
  const no = shortId(report.inspection_id);
  const photo = getPhotoFor(report.inspection_id);

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
      <TopNav activeTab="reports" />

      <View className={styles.container}>
        <View className={styles.breadcrumb}>
          <Text className={styles.crumbItem}>报告</Text>
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
            <Text className={styles.lede}>由 Claude Vision 分析 · {report.hazards.length} 项隐患</Text>
          </View>
          <View className={styles.headerActions}>
            <Button variant="secondary" onTap={handleExportPdf}>
              <Icon name="download" size={16} color="var(--ink)" />
              <Text className={styles.btnText}>导出 PDF</Text>
            </Button>
            <Button variant="secondary" onTap={notImplemented('分享')}>
              <Icon name="share" size={16} color="var(--ink)" />
              <Text className={styles.btnText}>分享</Text>
            </Button>
            <Button variant="primary" onTap={notImplemented('转派班组')}>
              <Icon name="arrow-up" size={16} color="var(--on-accent)" />
              <Text className={styles.btnText}>转派班组</Text>
            </Button>
          </View>
        </View>

        <View className={styles.hero}>
          <View className={styles.heroLeft}>
            <Photo
              src={photo?.src ?? ''}
              ratio="4/3"
              overlay={!!photo}
              meta={`NO.${no} · ${report.created_at.slice(0, 19).replace('T', ' ')}`}
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
              <View className={[styles.filterChip, styles.filterChipActive].join(' ')}>
                <Text>全部</Text>
              </View>
              <View className={styles.filterChip}>
                <Text>高</Text>
              </View>
              <View className={styles.filterChip}>
                <Text>中</Text>
              </View>
              <View className={styles.filterChip}>
                <Text>低</Text>
              </View>
            </View>
          </View>
          <View className={styles.listBody}>
            {sorted.map((h, idx) => (
              <HazardItem hazard={h} key={`${h.category_code}-${idx}`} index={idx + 1} />
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
          <Text className={styles.footerLeft}>Safety Scout · v0.3.1</Text>
          <Text className={styles.footerRight}>NO.{no} · 报告完</Text>
        </View>
      </View>
    </View>
  );
}
