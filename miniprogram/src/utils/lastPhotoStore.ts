/**
 * 缓存「最近上传的现场照片」让首页 / 报告页能渲真实图，而不是灰底占位。
 *
 * 双层存储：
 *   - 内存 Map：同一 SPA session 内最快路径；Taro.navigateTo 不重挂、跨页直读
 *   - localStorage：跨标签 / 刷新 / HMR 都活；weapp 没有 localStorage 退化到纯内存
 *
 * 桌面上传（File 对象）通常走 {@link rememberPhotoFromFile} 把 File 转 data:URL
 * 再存 —— data URL 自包含字节流、是唯一能跨 reload 的方式。缺点是大图占 5MB+
 * （多数施工照片 1-3MB OK，localStorage 配额 5-10MB 也够单张；超额时静默退化
 * 到内存）。同时调用方建议同步存一份 blob URL 进内存（{@link rememberPhoto}），
 * 让首屏不必等 FileReader。
 *
 * 移动上传（tempFilePath）只走 {@link rememberPhoto} —— Taro chooseMedia 的
 * tempFilePath 在 H5 上是 blob: URL，reload 后失效；接入后端 photo_url 后整个
 * 模块可下线，目前是"够用"的临时兜底。
 *
 * 容量控制：localStorage 5-10MB 上限 —— 单条记录可能 1-3MB，超过 6 条就快爆。
 * writeStorage 会先尝试，触发 quota 时按 capturedAt 升序淘汰最老的、再重试。
 */
interface PhotoRecord {
  inspectionId: string;
  src: string;
  capturedAt: number;
}

const memoryByInspection = new Map<string, PhotoRecord>();
let memoryLastPhoto: PhotoRecord | null = null;

const LS_KEY_LAST = 'safety-scout/last-photo';
const LS_KEY_PREFIX = 'safety-scout/photo:';

function ls(): Storage | null {
  // 用 try/catch 双保险：jsdom / 隐身模式 / 配额满 / weapp 都按"没有"处理。
  try {
    if (typeof window !== 'undefined' && window.localStorage) {
      return window.localStorage;
    }
  } catch {
    /* noop */
  }
  return null;
}

function allPhotoKeys(s: Storage): string[] {
  const keys: string[] = [];
  for (let i = 0; i < s.length; i++) {
    const k = s.key(i);
    if (k && k.startsWith(LS_KEY_PREFIX)) keys.push(k);
  }
  return keys;
}

function evictOldest(s: Storage): boolean {
  const keys = allPhotoKeys(s);
  if (keys.length === 0) return false;
  let oldestKey: string | null = null;
  let oldestAt = Infinity;
  for (const k of keys) {
    try {
      const raw = s.getItem(k);
      if (!raw) continue;
      const rec = JSON.parse(raw) as PhotoRecord;
      if (rec && typeof rec.capturedAt === 'number' && rec.capturedAt < oldestAt) {
        oldestAt = rec.capturedAt;
        oldestKey = k;
      }
    } catch {
      // 坏数据直接当成淘汰候选
      oldestKey = k;
      break;
    }
  }
  if (oldestKey) {
    try {
      s.removeItem(oldestKey);
      return true;
    } catch {
      return false;
    }
  }
  return false;
}

function writeStorage(rec: PhotoRecord): void {
  const s = ls();
  if (!s) return;
  const payload = JSON.stringify(rec);
  // 单条尝试 3 次：失败就淘汰最老的再试，避免 quota 满直接放弃
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      s.setItem(LS_KEY_PREFIX + rec.inspectionId, payload);
      s.setItem(LS_KEY_LAST, payload);
      return;
    } catch (e) {
      if (attempt === 2) {
        // 最后一次还失败，放弃；内存层仍有数据
        console.warn('[lastPhotoStore] localStorage 写入失败（quota？）', e);
        return;
      }
      if (!evictOldest(s)) return; // 没东西可淘汰，硬失败
    }
  }
}

function readStorage(key: string): PhotoRecord | null {
  const s = ls();
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

/** 按 inspection_id 拿照片；先查内存，miss 再 fallback 到 localStorage。 */
export function getPhotoFor(inspectionId: string): PhotoRecord | null {
  if (!inspectionId) return null;
  const inMem = memoryByInspection.get(inspectionId);
  if (inMem) return inMem;
  const fromStorage = readStorage(LS_KEY_PREFIX + inspectionId);
  if (fromStorage) {
    memoryByInspection.set(inspectionId, fromStorage); // 回填内存
    return fromStorage;
  }
  return null;
}

/** 拿"最近一张"——给首页"上次巡检"视觉锚用。无任何上传记录时返回 null。 */
export function getLastPhoto(): PhotoRecord | null {
  if (memoryLastPhoto) return memoryLastPhoto;
  const fromStorage = readStorage(LS_KEY_LAST);
  if (fromStorage) {
    memoryLastPhoto = fromStorage;
    return fromStorage;
  }
  return null;
}

/** 仅测试用：清空所有缓存（内存 + localStorage）。 */
export function _resetPhotoStore(): void {
  memoryByInspection.clear();
  memoryLastPhoto = null;
  const s = ls();
  if (!s) return;
  try {
    s.removeItem(LS_KEY_LAST);
    allPhotoKeys(s).forEach((k) => s.removeItem(k));
  } catch {
    /* noop */
  }
}
