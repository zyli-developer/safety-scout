/**
 * DesktopReport 占位 —— 桌面布局将在 Task 8 实现，
 * 现阶段直接复用 MobileReport 让 dispatcher 通编译并保持零行为变化。
 */
import MobileReport from './mobile';

export default function DesktopReport() {
  return <MobileReport />;
}
