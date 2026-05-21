/**
 * pages/index dispatcher —— 根据视口宽度选择移动或桌面变体。
 *
 * weapp 端 useIsDesktop 始终返回 false，DesktopIndex import 在 weapp webpack
 * 构建中被 dead-code 处理（实测多 10-20KB，可接受；详见 design §3）。
 */
import { useIsDesktop } from '../../hooks/useIsDesktop';
import MobileIndex from './mobile';
import DesktopIndex from './desktop';

export default function IndexPage() {
  const isDesktop = useIsDesktop();
  return isDesktop ? <DesktopIndex /> : <MobileIndex />;
}
