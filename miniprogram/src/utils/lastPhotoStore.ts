/**
 * 内存里缓存「最近上传的现场照片」—— 让首页 / 报告页能渲出真实图，而不是灰底占位。
 *
 * 为什么是内存（不进 storage）：
 *   - H5：`URL.createObjectURL(file)` 返回 blob: URL，仅在当前 SPA session 有效；
 *     落 localStorage 没意义（页面 reload 后 blob handle 已失效）。
 *   - weapp：Taro.chooseMedia 给 wxfile:// tempFilePath，本会话生命周期内有效。
 *
 * Taro 的 navigateTo 不会触发 SPA 重挂载，所以 module-level Map 跨页面读写安全。
 *
 * 等后端 GET inspection 返回 photo_url 后，本模块可整体退役 —— 直接读 report.photo_url。
 */
interface PhotoRecord {
  inspectionId: string;
  src: string;
  capturedAt: number;
}

let lastPhoto: PhotoRecord | null = null;
const byInspection = new Map<string, PhotoRecord>();

/** 上传完成后调用，登记 inspection_id ↔ 本地 src 的映射 + 更新"最近一张"指针。 */
export function rememberPhoto(inspectionId: string, src: string): void {
  if (!inspectionId || !src) return;
  const rec: PhotoRecord = { inspectionId, src, capturedAt: Date.now() };
  byInspection.set(inspectionId, rec);
  lastPhoto = rec;
}

/** 按 inspection_id 拿照片；找不到返回 null（首次打开报告页 / 跨 reload 场景）。 */
export function getPhotoFor(inspectionId: string): PhotoRecord | null {
  if (!inspectionId) return null;
  return byInspection.get(inspectionId) ?? null;
}

/** 拿"最近一张"——给首页"上次巡检"视觉锚用。无任何上传记录时返回 null。 */
export function getLastPhoto(): PhotoRecord | null {
  return lastPhoto;
}

/** 仅测试用：清空缓存。 */
export function _resetPhotoStore(): void {
  lastPhoto = null;
  byInspection.clear();
}
