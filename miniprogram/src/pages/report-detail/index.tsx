/**
 * ReportDetail — 单 hazard 详情页（B6 · 最小可行）。
 *
 * 对齐 docs/plans/2026-05-22-unified-modern-minimal/report-detail.html 核心 UX：
 *   - 顶部 crumbs（报告 / 隐患 #N / Hh 类别）+ pager (上一条 / 下一条)
 *   - hazard header（code + name + severity pill）
 *   - description + regulation 区
 *   - interactive checklist：一个高 stakes "确认本条已整改" step
 *   - 高 stakes 勾选弹 confirm sheet
 *   - 每次状态变化弹 5s undo toast
 *   - prefers-reduced-motion guard
 *
 * 未做（留下次 session）：
 *   - annotated photo（mockup .annot box 叠加在照片上，需要坐标 + tag）
 *   - Tabs（规范条款 / 整改建议·4步 / 现场处置记录）—— 内容直接平铺
 *   - sidebar "本条信息" + "本报告其他隐患"
 *   - 整改建议拆 4 步（mockup 是硬编码示例；hazard.suggestion 是单 string，不拆）
 *
 * 路由：?id={inspection_id}&h={hazard_index 0-based}
 * 数据：getInspection 一次性拉取，从 hazards[h] 取单条；同一报告内"上一条/下一条"
 *       只改 query h 不重新拉。
 */
import Taro from '@tarojs/taro';
import { View, Text } from '@tarojs/components';
import { useEffect, useState } from 'react';

import { getInspection } from '../../api/inspections';
import { TopNav } from '../../components/TopNav';
import { Icon } from '../../components/Icon';
import { SeverityPill } from '../../components/SeverityPill';
import { mapApiError } from '../../utils/errorMessage';
import { sortBySeverity } from '../../utils/severity';
import { mapV2ReportToV1 } from '../../utils/v2Adapter';
import type { GetInspectionResponse } from '../../types/inspection';
import type {
  GetInspectionV2Response,
  SchemaVersion,
} from '../../types/inspection-v2';
import type { Hazard } from '../../types/report';

import styles from './index.module.scss';

export default function ReportDetail() {
  const router = Taro.useRouter();
  const id = router.params.id ?? '';
  const hIndex = Number(router.params.h) || 0;
  // URL ?v=2 决定 GET 走哪条；缺省 v1。
  const schemaVersion: SchemaVersion = router.params.v === '2' ? 'v2' : 'v1';

  // 状态固定按 v1 shape 存：v2 响应在这里就被 adapter 转回 v1 shape，
  // 让下游 hazard 渲染（HazardItem / SeverityPill）零修改复用。
  const [data, setData] = useState<GetInspectionResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    getInspection(id, schemaVersion)
      .then((r) => {
        if (!alive) return;
        if (schemaVersion === 'v2' && r.report) {
          // v2 响应 → v1 shape；其他字段（status/error/created_at/...）已对齐
          const v2r = r as GetInspectionV2Response;
          setData({
            inspection_id: v2r.inspection_id,
            status: v2r.status,
            created_at: v2r.created_at,
            updated_at: v2r.updated_at,
            report: v2r.report
              ? mapV2ReportToV1(v2r.report, id, v2r.created_at)
              : null,
            error: v2r.error,
          });
        } else {
          setData(r as GetInspectionResponse);
        }
      })
      .catch((e) => {
        if (alive) setError(mapApiError(e).userMessage);
      });
    return () => {
      alive = false;
    };
  }, [id, schemaVersion]);

  if (error) {
    return (
      <View className={styles.page}>
        <TopNav activeTab="reports" />
        <View className={styles.centered}>
          <Icon name="x-circle" size={48} color="var(--high)" />
          <Text className={styles.errorText}>{error}</Text>
        </View>
      </View>
    );
  }

  if (!data || data.status !== 'succeeded' || !data.report) {
    return (
      <View className={styles.page}>
        <TopNav activeTab="reports" />
        <View className={styles.centered}>
          <Text className={styles.lede}>加载中…</Text>
        </View>
      </View>
    );
  }

  const hazards = sortBySeverity(data.report.hazards);
  const hazard = hazards[hIndex];
  if (!hazard) {
    return (
      <View className={styles.page}>
        <TopNav activeTab="reports" />
        <View className={styles.centered}>
          <Text className={styles.errorText}>找不到该条隐患</Text>
        </View>
      </View>
    );
  }

  return (
    <ReportDetailView
      inspectionId={id}
      hazard={hazard}
      hIndex={hIndex}
      total={hazards.length}
      createdAt={data.created_at}
    />
  );
}

function ReportDetailView({
  inspectionId,
  hazard,
  hIndex,
  total,
  createdAt,
}: {
  inspectionId: string;
  hazard: Hazard;
  hIndex: number;
  total: number;
  createdAt: string;
}) {
  const hasPrev = hIndex > 0;
  const hasNext = hIndex < total - 1;
  const go = (delta: number) => {
    const next = hIndex + delta;
    if (next < 0 || next >= total) return;
    // redirectTo 替换栈，避免点 N 次"下一条"在栈里塞 N 个页面
    Taro.redirectTo({
      url: `/pages/report-detail/index?id=${inspectionId}&h=${next}`,
    });
  };
  const goBackToReport = () => {
    Taro.navigateBack().catch(() => Taro.reLaunch({ url: '/pages/index/index' }));
  };

  // step 状态：done/pending；高 stakes 步骤勾选需要弹 confirm。
  const [done, setDone] = useState(false);
  // confirm-sheet 状态
  const [confirmOpen, setConfirmOpen] = useState(false);
  // toast 状态（5s 自动消失）
  const [toast, setToast] = useState<{ text: string; undo: () => void } | null>(null);
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 5000);
    return () => clearTimeout(t);
  }, [toast]);

  const stepAct = `确认 "${hazard.category_name}" 现场已整改`;

  const handleToggle = () => {
    if (!done) {
      // 高 stakes：未勾时点击 → 弹确认表
      setConfirmOpen(true);
      return;
    }
    // 已 done → unmark 不弹确认，直接撤回 + 5s undo
    setDone(false);
    setToast({
      text: '已恢复为待办',
      undo: () => setDone(true),
    });
  };

  const handleConfirm = () => {
    setConfirmOpen(false);
    setDone(true);
    setToast({
      text: `已标记完成 · ${truncate(stepAct, 22)}`,
      undo: () => setDone(false),
    });
  };

  return (
    <View className={styles.page}>
      <TopNav activeTab="reports" />

      <View className={styles.container}>
        <View className={styles.head}>
          <View className={styles.crumbs}>
            <View className={styles.crumbBtn} role="button" onClick={goBackToReport}>
              <Text>← 报告</Text>
            </View>
            <Text className={styles.crumbSep}>/</Text>
            <Text className={styles.crumbCurrent}>
              隐患 #{hIndex + 1} · {hazard.category_code} {hazard.category_name}
            </Text>
            <Text className={styles.crumbPos}>
              {hIndex + 1} / {total}
            </Text>
          </View>
          <View className={styles.pager}>
            <View
              className={[styles.pagerBtn, !hasPrev ? styles.pagerBtnDisabled : ''].join(' ')}
              role="button"
              aria-disabled={!hasPrev}
              onClick={() => hasPrev && go(-1)}
            >
              <Text>← 上一条</Text>
            </View>
            <View
              className={[styles.pagerBtn, !hasNext ? styles.pagerBtnDisabled : ''].join(' ')}
              role="button"
              aria-disabled={!hasNext}
              onClick={() => hasNext && go(1)}
            >
              <Text>下一条 →</Text>
            </View>
          </View>
        </View>

        <View className={styles.hazardHead}>
          <View className={styles.hazardTop}>
            <Text className={styles.hazardCode}>{hazard.category_code}</Text>
            <Text className={styles.hazardName}>{hazard.category_name}</Text>
            <SeverityPill level={hazard.severity} />
            {hazard.is_major === true && (
              <View className={styles.majorBadge} role="status" aria-label="重大事故隐患">
                <Text>重大隐患</Text>
              </View>
            )}
            <Text className={styles.hazardTime}>{createdAt.slice(0, 16).replace('T', ' ')}</Text>
          </View>
          <Text className={styles.hazardDesc}>{hazard.description}</Text>
        </View>

        {hazard.is_major === true && (hazard.major_basis ?? '').length > 0 && (
          <View className={styles.majorBasisBox}>
            <View className={styles.majorBasisHead}>
              <View className={styles.majorTag}>
                <Text>重大事故隐患</Text>
              </View>
              <Text className={styles.majorBasisLabel}>判定依据</Text>
            </View>
            <Text className={styles.majorBasisBody}>{hazard.major_basis}</Text>
          </View>
        )}

        {hazard.regulation && (
          <View className={styles.reg}>
            <View className={styles.regHead}>
              <Text className={styles.regTitle}>规范条款</Text>
              <Text className={styles.regSource}>引用</Text>
            </View>
            <Text className={styles.regBody}>{hazard.regulation}</Text>
          </View>
        )}

        <View className={styles.suggestionBlock}>
          <View className={styles.suggestionHead}>
            <Text className={styles.suggestionTitle}>整改建议</Text>
          </View>
          <Text className={styles.suggestionBody}>{hazard.suggestion}</Text>
        </View>

        {/* Interactive step: 单步硬化版本（confirm sheet + undo toast）
            做这一步的核心 UX 价值：让安全员明确"我做完了"且能撤销，
            是 critique P0 / mockup .step__check 的最小落地形态。 */}
        <View className={styles.checklist}>
          <Text className={styles.checklistTitle}>整改进度</Text>
          <View
            className={[styles.step, done ? styles.stepDone : ''].join(' ')}
            data-confirmable="true"
          >
            <View
              className={styles.stepCheck}
              role="checkbox"
              aria-checked={done}
              aria-label={stepAct}
              onClick={handleToggle}
            >
              {done && <Icon name="tick" size={13} color="#FFFFFF" />}
            </View>
            <View className={styles.stepBody}>
              <Text className={styles.stepAct}>{stepAct}</Text>
              <Text className={styles.stepWhen}>
                {done ? '已完成' : '高 stakes · 勾选时会弹出确认'}
              </Text>
            </View>
          </View>
        </View>

        {/* Confirm sheet —— mockup .confirm-sheet */}
        {confirmOpen && (
          <View className={styles.confirmSheet} role="presentation" onClick={() => setConfirmOpen(false)}>
            <View
              className={styles.confirmInner}
              role="alertdialog"
              aria-modal="true"
              aria-labelledby="confirmTitle"
              onClick={(e) => e.stopPropagation()}
            >
              <Text className={styles.confirmTitle} id="confirmTitle">
                确认现场已完成？
              </Text>
              <Text className={styles.confirmBody}>
                这一条涉及人员安全，错误标记可能误导班组停工或闭环判定。请先确认现场已落实。
              </Text>
              <View className={styles.confirmAct}>
                <Text className={styles.confirmActLabel}>当前整改</Text>
                <Text className={styles.confirmActText}>{stepAct}</Text>
              </View>
              <View className={styles.confirmBtns}>
                <View className={[styles.btn, styles.btnGhost].join(' ')} role="button" onClick={() => setConfirmOpen(false)}>
                  <Text>再想想</Text>
                </View>
                <View className={[styles.btn, styles.btnPrimary].join(' ')} role="button" onClick={handleConfirm}>
                  <Text>确认完成</Text>
                </View>
              </View>
            </View>
          </View>
        )}

        {/* Undo toast — 5s 自动消失，可主动撤销或关闭 */}
        {toast && (
          <View className={styles.toast} role="status" aria-live="polite">
            <Text className={styles.toastText}>{toast.text}</Text>
            <View
              className={styles.toastUndo}
              role="button"
              onClick={() => {
                toast.undo();
                setToast(null);
              }}
            >
              <Text>撤销</Text>
            </View>
            <View className={styles.toastClose} role="button" aria-label="关闭" onClick={() => setToast(null)}>
              <Text>×</Text>
            </View>
          </View>
        )}
      </View>
    </View>
  );
}

function truncate(s: string, n: number): string {
  return s.length > n ? s.slice(0, n) + '…' : s;
}
