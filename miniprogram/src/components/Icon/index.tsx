/**
 * Inline SVG 图标集（iOS HIG / Heroicons outline 风格）。
 * 取代 emoji（🦺📷⚠️📋💡✅）—— 这些在 iOS 上显示效果不专业、跨平台不一致。
 *
 * 所有 icon：stroke 1.5px、currentColor 继承父容器 color。
 * 用法：<Icon name="camera" size={24} color="#007AFF" />
 */

import { View } from '@tarojs/components';

export type IconName =
  | 'camera'
  | 'chevron-right'
  | 'chevron-left'
  | 'chevron-down'
  | 'chevron-up'
  | 'alert-triangle'
  | 'check-circle'
  | 'x-circle'
  | 'document'
  | 'lightbulb'
  | 'arrow-right'
  | 'arrow-up'
  | 'stamp'
  | 'plus-square'
  | 'crosshair'
  | 'slash-circle'
  | 'tick'
  | 'search'
  | 'dots'
  | 'upload'
  | 'image'
  | 'share';

interface IconProps {
  name: IconName;
  size?: number;
  color?: string;
  className?: string;
}

const PATHS: Record<IconName, string> = {
  // Heroicons outline / Tabler 风格，统一 24x24 viewBox
  camera:
    'M3 9a2 2 0 0 1 2-2h1.5L8 5h8l1.5 2H19a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V9zm9 9a4.5 4.5 0 1 0 0-9 4.5 4.5 0 0 0 0 9z',
  'chevron-right': 'm9 6 6 6-6 6',
  'chevron-left': 'm15 18-6-6 6-6',
  'chevron-down': 'm6 9 6 6 6-6',
  'chevron-up': 'm6 15 6-6 6 6',
  'alert-triangle': 'M12 9v4m0 4h.01M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z',
  'check-circle': 'M9 12l2 2 4-4m6 2a9 9 0 1 1-18 0 9 9 0 0 1 18 0z',
  'x-circle': 'M10 14l4-4m0 4-4-4m12-2a9 9 0 1 1-18 0 9 9 0 0 1 18 0z',
  document:
    'M9 12h6m-6 4h6m2 5H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5.586a1 1 0 0 1 .707.293l5.414 5.414a1 1 0 0 1 .293.707V19a2 2 0 0 1-2 2z',
  lightbulb:
    'M12 2a7 7 0 0 0-4 12.71V17a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1v-2.29A7 7 0 0 0 12 2zM9 21h6',
  'arrow-right': 'M5 12h14m-7-7 7 7-7 7',
  'arrow-up': 'M12 19V5m-7 7 7-7 7 7',
  search: 'm21 21-5.2-5.2M17 10A7 7 0 1 1 3 10a7 7 0 0 1 14 0z',
  dots: 'M6 12a1.5 1.5 0 1 0 0-.001M12 12a1.5 1.5 0 1 0 0-.001M18 12a1.5 1.5 0 1 0 0-.001',
  upload: 'M12 16V4m-5 5 5-5 5 5M4 20h16',
  image: 'M3 6a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6zm0 11 5-5 5 5 3-3 5 5',
  share: 'M8 12V6a4 4 0 1 1 8 0v6M5 12h14l-1 8H6l-1-8z',
  stamp:
    'M6 4h12v8H6z M4 16h16v2H4z M9 12v4 M15 12v4', // 印章 + 底座 + 两条挂绳
  'plus-square':
    'M4 4h16v16H4z M12 8v8 M8 12h8', // ⊕ measure plus inside square
  crosshair:
    'M12 2v20 M2 12h20 M12 6a6 6 0 1 0 0 12 6 6 0 0 0 0-12z', // ⌖ engineering target
  'slash-circle':
    'M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20z M5 5l14 14', // ⊘ forbid / strike
  tick: 'M5 12l4 4 10-10', // ✓ checkmark
};

// camera / document / alert-triangle / lightbulb 用 fill="none" + stroke + 部分填充
const FILLED_NAMES: Set<IconName> = new Set();

export function Icon({ name, size = 24, color = 'currentColor', className }: IconProps) {
  const d = PATHS[name];
  const isFilled = FILLED_NAMES.has(name);
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="${size}" height="${size}" fill="${isFilled ? color : 'none'}" stroke="${color}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="${d}"/></svg>`;
  return (
    <View
      className={className}
      style={{
        display: 'inline-block',
        width: `${size}px`,
        height: `${size}px`,
        flexShrink: 0,
        verticalAlign: 'middle',
      }}
      // dangerouslySetInnerHTML 是 H5 / web 标准；Taro weapp 用 rich-text，
      // 但本项目 Phase 3 目标是 H5 优先，weapp 端图标后续做替换
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  );
}
