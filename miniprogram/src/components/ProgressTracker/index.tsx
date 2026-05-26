/**
 * ProgressTracker — unified-modern-minimal 3-state tracker + livelog + cancel link。
 *
 * 升级 ProgressIndicator（一个小 ring + step list）→ 把 3 状态进度抬成轮询页主角，
 * 兑现 docs/architecture.md "拍照成功 → AI 分析中 → 报告就绪" 的 UX 不变量。
 *
 * 状态映射：currentStep（1=queued, 2=processing, 3=succeeded）
 *   - Node A「拍照已就绪」：进入此视图意味照片已上传，恒为 done。
 *   - Node B「AI 分析中」：queued / processing 均为 active；succeeded 时父组件已切走。
 *   - Node C「报告就绪」：rendering 期间始终 pending；succeeded 时父组件已切走。
 *
 * 2026-05-24 改动（按 docs/plans/2026-05-24-ui-parity-audit.md B4）：
 * - 加 livelog 实时分析 4 行（按 elapsedMs 推进 done/active/pending 状态）
 *   livelog 第一行已是用户语言"照片已收到 · 准备分析"（critique P0 修复，无 SHA256）
 * - 加 stage__cancel "不想等？取消并返回" 链接
 *
 * 布局：desktop 横向（grid 3 列 + 2 条 connector）；mobile 纵向（垂直 timeline）。
 * 由 .module.scss `@media (max-width: 600px)` 控制。
 */
import { View, Text } from '@tarojs/components';

import { Icon } from '../Icon';

import styles from './index.module.scss';

export interface ProgressTrackerProps {
  /** 1=queued / 2=processing / 3=succeeded（罕用，通常父组件已切走）。 */
  currentStep: 1 | 2 | 3;
  /** 已耗时（毫秒），渲染在 node B 与底部 elapsed 条上。 */
  elapsedMs?: number;
  /** 预计耗时秒数，默认 180 — 复杂场景 Claude vision 实测 ~3 分钟。 */
  estimatedSeconds?: number;
  /** "取消并返回"链接的点击处理。不传时不渲染该链接。 */
  onCancel?: () => void;
}

function fmtMMSS(totalSec: number): string {
  const s = Math.max(0, Math.floor(totalSec));
  const m = Math.floor(s / 60);
  const r = s % 60;
  return `${m}:${String(r).padStart(2, '0')}`;
}

// livelog 4 个固定阶段。tag 是预估时间点（秒），用户实际看到的是渐进显现的过程。
// 文案按 mockup polling.html livelog 抄录，第一行已修复（无 SHA256）。
// 时间点按 180s 默认预计时长重排：~8% / ~17% / ~44% / ~92% 进度位（保持节奏感）。
const LIVELOG_PHASES: Array<{ at: number; text: string }> = [
  { at: 15, text: '照片已收到 · 准备分析' },
  { at: 30, text: '识别现场场景：外架 / 临边 / 楼层结构' },
  { at: 80, text: '逐项核查 H1-H10 类别，参照 JGJ80-2016…' },
  { at: 165, text: '组装 JSON · 校验字段完整性' },
];

function livelogStateFor(phaseAt: number, sec: number): 'done' | 'active' | 'pending' {
  if (sec >= phaseAt + 4) return 'done';
  if (sec >= phaseAt) return 'active';
  return 'pending';
}

export function ProgressTracker({
  currentStep,
  elapsedMs = 0,
  estimatedSeconds = 180,
  onCancel,
}: ProgressTrackerProps) {
  const sec = Math.floor(elapsedMs / 1000);
  const pct = Math.min(100, Math.round((sec / estimatedSeconds) * 100));

  const stateA: NodeState = 'done';
  const stateB: NodeState = currentStep >= 3 ? 'done' : 'active';
  const stateC: NodeState = currentStep >= 3 ? 'active' : 'pending';

  const lineAB: LineState = 'done';
  const lineBC: LineState = currentStep >= 3 ? 'done' : 'active';

  const bHint = currentStep === 1
    ? '上传完成 · 等待分析'
    : `${fmtMMSS(sec)} / ~${fmtMMSS(estimatedSeconds)}`;

  return (
    <View className={styles.wrap} role="region" aria-label="分析进度">
      <View className={styles.tracker} role="list">
        <Node state={stateA} label="拍照已就绪" hint="已上传" glyph="check" />
        <Line state={lineAB} />
        <Node state={stateB} label="AI 分析中" hint={bHint} glyph="clock" />
        <Line state={lineBC} />
        <Node state={stateC} label="报告就绪" hint="即将完成" glyph="document" />
      </View>

      <View className={styles.elapsed}>
        <View className={styles.elapsedRow}>
          <Text className={styles.elapsedLabel}>
            已用时 <Text className={styles.elapsedNum}>{fmtMMSS(sec)}</Text>
          </Text>
          <Text className={styles.elapsedEstimate}>预计 {fmtMMSS(estimatedSeconds)}</Text>
        </View>
        <View className={styles.elapsedBar}>
          <View className={styles.elapsedFill} style={{ width: `${pct}%` }} />
        </View>
      </View>

      {/* livelog — 实时分析 4 行（B4 新增） */}
      <View className={styles.livelog} aria-live="polite">
        <Text className={styles.livelogTitle}>实时分析</Text>
        <View className={styles.livelogList}>
          {LIVELOG_PHASES.map((p) => {
            const st = livelogStateFor(p.at, sec);
            const itemCls = [
              styles.livelogItem,
              st === 'done' ? styles.livelogItemDone : '',
              st === 'active' ? styles.livelogItemActive : '',
            ]
              .filter(Boolean)
              .join(' ');
            const tag = st === 'pending' ? '[—]' : `[${fmtMMSS(p.at)}]`;
            return (
              <View key={p.at} className={itemCls}>
                <View className={styles.livelogDot} />
                <Text className={styles.livelogTag}>{tag}</Text>
                <Text className={styles.livelogText}>{p.text}</Text>
              </View>
            );
          })}
        </View>
      </View>

      <Text className={styles.hint}>
        {`不需要等在这页 — 完成后会自动跳转。${
          estimatedSeconds >= 60
            ? `平均 ${Math.round(estimatedSeconds / 60)} 分钟出结果。`
            : `平均 ${estimatedSeconds} 秒出结果。`
        }`}
      </Text>

      {onCancel && (
        <View className={styles.cancelRow}>
          {/* 2026-05-26：原文案"不想等？取消并返回"撒谎 —— 实际只是 reLaunch
              回首页，后端 analysis runner 继续跑完、扣订阅额度。改为诚实文案
              + 副文告知用户后台继续 + 提示可从「报告」里找到。 */}
          <View className={styles.cancelLink} role="button" onClick={onCancel}>
            <Text>回到首页继续</Text>
          </View>
          <Text className={styles.cancelText}>
            分析在后台继续，完成后可从「报告」里找到
          </Text>
        </View>
      )}
    </View>
  );
}

type NodeState = 'done' | 'active' | 'pending';
type LineState = 'done' | 'active' | 'pending';

function Node({
  state,
  label,
  hint,
  glyph,
}: {
  state: NodeState;
  label: string;
  hint: string;
  glyph: 'check' | 'clock' | 'document';
}) {
  const cls = [
    styles.node,
    state === 'done' ? styles.nodeDone : '',
    state === 'active' ? styles.nodeActive : '',
    state === 'pending' ? styles.nodePending : '',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <View className={cls} role="listitem">
      <View className={styles.dot} aria-label={state}>
        <NodeGlyph glyph={glyph} state={state} />
      </View>
      <Text className={styles.label}>{label}</Text>
      <Text className={styles.hintMono}>{hint}</Text>
    </View>
  );
}

function NodeGlyph({ glyph, state }: { glyph: 'check' | 'clock' | 'document'; state: NodeState }) {
  if (glyph === 'check') {
    return <Icon name="tick" size={22} color={state === 'done' ? '#FFFFFF' : 'currentColor'} />;
  }
  if (glyph === 'document') {
    return <Icon name="document" size={20} color="currentColor" />;
  }
  return <Icon name="check-circle" size={20} color="currentColor" />;
}

function Line({ state }: { state: LineState }) {
  const cls = [
    styles.line,
    state === 'done' ? styles.lineDone : '',
    state === 'active' ? styles.lineActive : '',
  ]
    .filter(Boolean)
    .join(' ');
  return <View className={cls} />;
}
