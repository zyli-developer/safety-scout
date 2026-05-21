/**
 * pages/report dispatcher —— 根据视口宽度选择移动或桌面变体。
 *
 * weapp 端 useIsDesktop 始终返回 false，DesktopReport import 在 weapp webpack
 * 构建中被 dead-code 处理（详见 design §3）。
 */
import { useIsDesktop } from '../../hooks/useIsDesktop';
import MobileReport from './mobile';
import DesktopReport from './desktop';

export default function ReportPage() {
  const isDesktop = useIsDesktop();
  return isDesktop ? <DesktopReport /> : <MobileReport />;
}
