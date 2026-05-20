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
  | 'chevron-down'
  | 'chevron-up'
  | 'alert-triangle'
  | 'check-circle'
  | 'x-circle'
  | 'document'
  | 'lightbulb'
  | 'arrow-right'
  | 'helmet';

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
  helmet:
    'M4 14a8 8 0 0 1 16 0 M3 14h18 M9 14v-3a3 3 0 0 1 6 0v3',
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
