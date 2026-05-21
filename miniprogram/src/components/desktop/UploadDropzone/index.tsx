/**
 * 桌面 H5 上传组件：拖拽 + 点击触发 <input type="file">。
 *
 * 不复用 hooks/useImageCapture —— 它包装 Taro.chooseMedia，weapp 用；桌面浏览器
 * 直接用原生 <input> + DataTransfer 体验更好且无 Taro 依赖。
 *
 * 这是 desktop/ 目录下第一个纯 H5 组件：直接用原生 <div>/<span> 而非 Taro
 * <View>/<Text>，因为 Taro 的 ViewProps 不暴露 onDragEnter/Drop/DragOver 等
 * HTML5 拖放事件，且本组件 weapp 端不会渲染（被 useIsDesktop 分发拦截）。
 *
 * 状态：
 * - idle：默认提示文案
 * - hover：拖拽悬停（data-hover='true'）—— SCSS 用 [data-hover='true'] 选择器变色
 * - uploading：禁用交互 + aria-busy='true'
 * - 键盘可达：tabIndex=0、Enter/Space 等价于点击（uploading 时 tabIndex=-1，键盘不响应）
 */
import { useRef, useState } from 'react';

import { Icon } from '../../Icon';

import styles from './index.module.scss';

export interface UploadDropzoneProps {
  /** 用户选/拖完文件后回调；调用方负责调 createInspection 与 navigate。 */
  onSelect: (file: File) => void;
  /** 上传进行中：禁用点击与拖放，UI 灰态。 */
  uploading?: boolean;
}

export function UploadDropzone({ onSelect, uploading = false }: UploadDropzoneProps) {
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
      <div className={styles.icon}>
        <Icon name="plus-square" size={56} color="#1A1A1A" />
      </div>
      <span className={styles.label}>
        {uploading ? '上传中...' : '拖拽图片到此 / 点击选择文件'}
      </span>
      <span className={styles.sublabel}>
        {uploading ? 'PROCESSING' : 'CAPTURE INSPECTION PHOTO'}
      </span>
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
