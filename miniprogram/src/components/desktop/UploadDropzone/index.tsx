/**
 * UploadDropzone — clean-minimal 桌面上传组件。
 *
 * 行为不动：
 * - 拖拽 + 点击触发 <input type="file"> 的隐藏 picker
 * - 键盘可达：tabIndex=0、Enter/Space 等价点击；uploading 时 tabIndex=-1
 * - data-hover='true' 由 React 设置；SCSS 用 [data-hover='true'] 选择器变色
 * - uploading：禁用交互 + aria-busy='true'
 *
 * 视觉：朴素 dashed 区域 + 上传图标圆 + 中文主标 + 副标 + 主按钮"选择文件"。
 * 旧 dossier 取景框 / 刻度尺 / Latin uppercase 副标全删（IMPLEMENT.md §4.2）。
 *
 * 这是 desktop/ 目录下纯 H5 组件：用原生 <div>/<span> 而非 Taro <View>/<Text>，
 * 因为 Taro 的 ViewProps 不暴露 onDragEnter/Drop/DragOver 等 HTML5 拖放事件，
 * 且本组件 weapp 端不会渲染（被 useIsDesktop 分发拦截）。
 */
import { useRef, useState } from 'react';

import { Icon } from '../../Icon';

import styles from './index.module.scss';

export interface UploadDropzoneProps {
  /** 用户选/拖完文件后回调；调用方负责调 createInspection 与 navigate。 */
  onSelect: (file: File) => void;
  /** 上传进行中：禁用点击与拖放，UI 灰态。 */
  uploading?: boolean;
  /** 「手机扫码」按钮回调（设计稿里和「选择文件」并排）；不传则不渲染该按钮。 */
  onQRRequest?: () => void;
}

export function UploadDropzone({ onSelect, uploading = false, onQRRequest }: UploadDropzoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [hover, setHover] = useState(false);

  const trigger = () => {
    if (uploading) return;
    inputRef.current?.click();
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setHover(false);
    if (uploading) return;
    const f = e.dataTransfer?.files?.[0];
    if (f) onSelect(f);
  };

  return (
    <div
      className={styles.zone}
      role="button"
      aria-busy={uploading}
      data-hover={hover}
      tabIndex={uploading ? -1 : 0}
      onClick={trigger}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          trigger();
        }
      }}
      onDragEnter={(e) => {
        e.preventDefault();
        setHover(true);
      }}
      onDragOver={(e) => {
        e.preventDefault();
      }}
      onDragLeave={(e) => {
        e.preventDefault();
        setHover(false);
      }}
      onDrop={handleDrop}
    >
      <div className={styles.iconCircle}>
        <Icon name="upload" size={28} color="var(--ink)" />
      </div>
      <div className={styles.body}>
        <span className={styles.label}>
          {uploading ? '上传中…' : '拖拽图片到此处'}
        </span>
        <span className={styles.sublabel}>
          {uploading ? '正在调用 AI 推理…' : '或点击选择文件 · JPG · PNG · HEIC · 最大 15MB'}
        </span>
      </div>
      <div className={styles.cta}>
        {/* 「选择文件」纯视觉提示；点击事件会冒泡到外层 zone 的 onClick → 触发 file picker。 */}
        <span className={styles.ctaPrimary}>
          <Icon name="upload" size={16} color="var(--on-accent)" />
          <span className={styles.ctaText}>选择文件</span>
        </span>
        {onQRRequest && (
          // stopPropagation：本按钮独立动作，不能误触发 file picker。
          <span
            className={styles.ctaSecondary}
            role="button"
            aria-label="手机扫码"
            onClick={(e) => {
              e.stopPropagation();
              if (!uploading) onQRRequest();
            }}
          >
            <Icon name="camera" size={16} color="var(--ink)" />
            <span className={styles.ctaText}>手机扫码</span>
          </span>
        )}
      </div>
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        style={{ display: 'none' }}
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) onSelect(f);
          e.target.value = '';
        }}
      />
    </div>
  );
}
