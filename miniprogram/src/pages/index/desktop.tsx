/**
 * DesktopIndex 占位 —— 桌面布局将在 Task 6 实现，
 * 现阶段直接复用 MobileIndex 让 dispatcher 通编译并保持零行为变化。
 */
import MobileIndex from './mobile';

export default function DesktopIndex() {
  return <MobileIndex />;
}
