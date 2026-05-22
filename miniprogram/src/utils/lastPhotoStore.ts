/**
 * 缓存「最近上传的现场照片」让首页 / 报告页能渲真实图，而不是灰底占位。
 *
 * 双层存储：
 *   - 内存 Map：同一 SPA session 内最快路径；Taro.navigateTo 不重挂，跨页直读
 *   - sessionStorage：H5 标签页生命周期内幸存 —— 用户刷报告页、F5、HMR
 *     之后仍能拿回照片；weapp 没有 sessionStorage，退化到纯内存
 *
 * 桌面上传（File 对象）请走 {@link rememberPhotoFromFile} —— 把 File 转 data:URL
 * 再存，data URL 自包含字节流、跨 reload / 跨 tab 都活；缺点是 5MB 上限（多数手机
 * 拍的现场图 1-3MB 没问题，sessionStorage 配额 5-10MB 也够单张）。
 *
 * 移动上传（tempFilePath）走 {@link rememberPhoto} —— Taro chooseMedia 的
 * tempFilePath 在 H5 上是 blob: URL，reload 后失效；接入后端 photo_url 后整个
 * 模块可下线，目前是"够用"的临时兜底。
 */
interface PhotoRecord {
  inspectionId: string;
  src: string;
  capturedAt: number;
}

const memoryByInspection = new Map<string, PhotoRecord>();
let memoryLastPhoto: PhotoRecord | null = null;

const SS_KEY_LAST = 'safety-scout/last-photo';
const SS_KEY_PREFIX = 'safety-scout/photo:';

function ss(): Storage | null {
  // 用 try/catch 双保险：jsdom 测试环境有但访问可能受限；
  // 隐身模式 / 配额满 / weapp 都按"没有"处理。
  try {
    if (typeof window !== 'undefined' && window.sessionStorage) {
      return window.sessionStorage;
    }
  } catch {
    /* noop */
  }
  return null;
}

function writeStorage(rec: PhotoRecord): void {
  const s = ss();
  if (!s) return;
  try {
    const payload = JSON.stringify(rec);
    s.setItem(SS_KEY_PREFIX + rec.inspectionId, payload);
    s.setItem(SS_KEY_LAST, payload);
  } catch {
    // quota exceeded（大图 + sessionStorage 已满）→ 静默退化为仅内存
  }
}

function readStorage(key: string): PhotoRecord | null {
  const s = ss();
  if (!s) return null;
  try {
    const raw = s.getItem(key);
    if (!raw) return null;
    const rec = JSON.parse(raw) as PhotoRecord;
    if (rec && typeof rec.src === 'string' && typeof rec.inspectionId === 'string') {
      return rec;
    }
  } catch {
    /* corrupted */
  }
  return null;
}

/** 上传完成后调用，登记 inspection_id ↔ 本地 src 的映射 + 更新"最近一张"指针。 */
export function rememberPhoto(inspectionId: string, src: string): void {
  if (!inspectionId || !src) return;
  const rec: PhotoRecord = { inspectionId, src, capturedAt: Date.now() };
  memoryByInspection.set(inspectionId, rec);
  memoryLastPhoto = rec;
  writeStorage(rec);
}

/**
 * 桌面 H5：从原始 File 读 base64 data:URL，再走 {@link rememberPhoto}。
 * 写完返回 dataUrl（调用方可直接用、不必再 createObjectURL）。
 * jsdom 没 FileReader → reject；调用方应 catch 后 fallback 到 blob URL 或 skip。
 */
export function rememberPhotoFromFile(inspectionId: string, file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    if (typeof FileReader === 'undefined') {
      reject(new Error('FileReader not available'));
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      const dataUrl = typeof reader.result === 'string' ? reader.result : '';
      if (!dataUrl) {
        reject(new Error('empty data url'));
        return;
      }
      rememberPhoto(inspectionId, dataUrl);
      resolve(dataUrl);
    };
    reader.onerror = () => reject(reader.error ?? new Error('FileReader error'));
    reader.readAsDataURL(file);
  });
}

/** 按 inspection_id 拿照片；先查内存，miss 再 fallback 到 sessionStorage。 */
export function getPhotoFor(inspectionId: string): PhotoRecord | null {
  if (!inspectionId) return null;
  const inMem = memoryByInspection.get(inspectionId);
  if (inMem) return inMem;
  const fromStorage = readStorage(SS_KEY_PREFIX + inspectionId);
  if (fromStorage) {
    memoryByInspection.set(inspectionId, fromStorage); // 回填内存
    return fromStorage;
  }
  return null;
}

/** 拿"最近一张"——给首页"上次巡检"视觉锚用。无任何上传记录时返回 null。 */
export function getLastPhoto(): PhotoRecord | null {
  if (memoryLastPhoto) return memoryLastPhoto;
  const fromStorage = readStorage(SS_KEY_LAST);
  if (fromStorage) {
    memoryLastPhoto = fromStorage;
    return fromStorage;
  }
  return null;
}

/** 仅测试用：清空所有缓存（内存 + sessionStorage）。 */
export function _resetPhotoStore(): void {
  memoryByInspection.clear();
  memoryLastPhoto = null;
  const s = ss();
  if (!s) return;
  try {
    s.removeItem(SS_KEY_LAST);
    // 清掉所有 photo: 前缀的 key
    const keys: string[] = [];
    for (let i = 0; i < s.length; i++) {
      const k = s.key(i);
      if (k && k.startsWith(SS_KEY_PREFIX)) keys.push(k);
    }
    keys.forEach((k) => s.removeItem(k));
  } catch {
    /* noop */
  }
}
