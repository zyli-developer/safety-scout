/**
 * FeedbackModal — v2 badcase 反馈弹层。
 *
 * 三档 kind 与后端 schema 对齐：
 * - false_positive（误报）：模型识别出的某 finding 实际不存在 → 需带 check_id
 * - bad_action（建议不可执行）：模型给的整改建议现场无法执行 → 需带 check_id
 * - missed（漏报）：模型遗漏的隐患 → check_id 可选
 *
 * checkId 入参决定本次反馈面向的 finding：
 * - 传入 → 渲染 false_positive / bad_action 两档可选（针对具体条目）
 * - 不传 → 锁死 kind=missed（"我们漏了什么"全局反馈入口）
 *
 * UX 约束（docs/specs/v2-rollout.md §二）：
 * - description 1-500 字必填；字数 counter 实时显示
 * - 提交中禁交互；成功 toast；失败保留 modal 让用户重试
 */
import Taro from '@tarojs/taro';
import { View, Text } from '@tarojs/components';
import { useEffect, useState } from 'react';

import { submitFeedback, type FeedbackPayload } from '../../api/inspections';
import { ApiError } from '../../api/client';
import { mapApiError } from '../../utils/errorMessage';
import { Icon } from '../Icon';

import styles from './index.module.scss';

type Kind = FeedbackPayload['kind'];

export interface FeedbackModalProps {
  isOpen: boolean;
  onClose: () => void;
  /** v2 inspection id —— 必须，POST 的 path 参数。 */
  inspectionId: string;
  /** 被反馈的 finding check_id；不传则锁死漏报模式。 */
  checkId?: string;
  /** 提交成功后回调（除关闭 modal 之外的额外副作用，如刷新列表）。 */
  onSuccess?: () => void;
}

const KIND_LABELS: Record<Kind, string> = {
  false_positive: '误报',
  missed: '漏报',
  bad_action: '建议不可执行',
};

const MAX_DESC = 500;

export function FeedbackModal({
  isOpen,
  onClose,
  inspectionId,
  checkId,
  onSuccess,
}: FeedbackModalProps) {
  const hasCheckId = !!checkId;
  // 入口决定可选 kind：有 checkId → 误报/不可执行二选一；无 → 锁死 missed
  const defaultKind: Kind = hasCheckId ? 'false_positive' : 'missed';
  const [kind, setKind] = useState<Kind>(defaultKind);
  const [description, setDescription] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // 每次 modal 打开重置（避免上次的草稿污染）
  useEffect(() => {
    if (isOpen) {
      setKind(defaultKind);
      setDescription('');
      setSubmitting(false);
      setErrorMsg(null);
    }
  }, [isOpen, defaultKind]);

  if (!isOpen) return null;

  const canSubmit =
    !submitting && description.trim().length > 0 && description.length <= MAX_DESC;

  const handleSubmit = async () => {
    if (!canSubmit) return;
    setSubmitting(true);
    setErrorMsg(null);
    const body: FeedbackPayload = {
      kind,
      description: description.trim(),
      ...(hasCheckId ? { check_id: checkId } : {}),
    };
    try {
      await submitFeedback(inspectionId, body);
      Taro.showToast({ title: '反馈已提交，感谢', icon: 'success', duration: 2000 });
      onSuccess?.();
      onClose();
    } catch (e) {
      const ui = mapApiError(e instanceof ApiError ? e : new ApiError('UNKNOWN', '提交失败，请重试', 0));
      setErrorMsg(ui.userMessage);
      setSubmitting(false);
    }
  };

  return (
    <View className={styles.overlay} role="dialog" aria-modal="true" aria-label="提交反馈">
      <View className={styles.backdrop} onClick={submitting ? undefined : onClose} />
      <View className={styles.sheet}>
        <View className={styles.head}>
          <Text className={styles.title}>
            {hasCheckId ? `反馈 · ${checkId}` : '反馈：我们漏了什么'}
          </Text>
          <View
            className={styles.closeBtn}
            role="button"
            aria-label="关闭"
            onClick={submitting ? undefined : onClose}
          >
            <Icon name="x-circle" size={18} color="var(--ink-3)" />
          </View>
        </View>

        {hasCheckId && (
          // 误报 / 建议不可执行二选一；漏报模式下不渲染（kind 已锁 missed）
          <View className={styles.kindRow} role="radiogroup" aria-label="反馈类型">
            {(['false_positive', 'bad_action'] as Kind[]).map((k) => (
              <View
                key={k}
                role="radio"
                aria-checked={kind === k}
                className={[styles.kindChip, kind === k ? styles.kindChipActive : '']
                  .filter(Boolean)
                  .join(' ')}
                onClick={submitting ? undefined : () => setKind(k)}
              >
                <Text>{KIND_LABELS[k]}</Text>
              </View>
            ))}
          </View>
        )}

        <View className={styles.descWrap}>
          <textarea
            className={styles.desc}
            value={description}
            placeholder={
              kind === 'missed'
                ? '描述未识别到的隐患（如：右下角钢筋未捆扎）'
                : kind === 'false_positive'
                  ? '说明为何不是隐患（如：工人其实戴了安全带）'
                  : '说明建议为什么不可执行（如：现场条件不允许）'
            }
            maxLength={MAX_DESC}
            disabled={submitting}
            onChange={(e) => setDescription((e.target as HTMLTextAreaElement).value)}
            aria-label="反馈描述"
          />
          <View className={styles.counter} aria-live="polite">
            <Text>{description.length} / {MAX_DESC}</Text>
          </View>
        </View>

        {errorMsg && (
          <View className={styles.errorMsg} role="alert">
            <Text>{errorMsg}</Text>
          </View>
        )}

        <View className={styles.actions}>
          <View
            className={[styles.btn, styles.btnGhost].join(' ')}
            role="button"
            onClick={submitting ? undefined : onClose}
          >
            <Text>取消</Text>
          </View>
          <View
            className={[styles.btn, styles.btnPrimary, canSubmit ? '' : styles.btnDisabled]
              .filter(Boolean)
              .join(' ')}
            role="button"
            aria-disabled={!canSubmit}
            onClick={canSubmit ? handleSubmit : undefined}
          >
            <Text>{submitting ? '提交中…' : '提交反馈'}</Text>
          </View>
        </View>
      </View>
    </View>
  );
}
