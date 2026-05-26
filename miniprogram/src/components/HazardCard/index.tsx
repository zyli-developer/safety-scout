/**
 * HazardCard — clean-minimal 版本：薄壳代理到 HazardItem。
 *
 * 旧 dossier 形态（编号 + severity 条带 + 三栏标签）已废弃。保留组件名 + props
 * API 不动，避免 pages/report/* 的调用方在 Slice 3 阶段就被迫迁移；后续 Slice
 * 5/6 重排页面时可以选择直接用 HazardItem 替换。
 *
 * `total` 在新设计里无显示位（编号已暗示），保留入参但不渲染。
 */
import { HazardItem } from '../HazardItem';
import type { Hazard } from '../../types/report';

export interface HazardCardProps {
  hazard: Hazard;
  index?: number;
  /** @deprecated 新设计不显示 "x / total"；入参为兼容保留，已无渲染。 */
  total?: number;
}

export function HazardCard({ hazard, index = 1 }: HazardCardProps) {
  return <HazardItem hazard={hazard} index={index} />;
}
