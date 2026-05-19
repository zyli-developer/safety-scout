/**
 * 调相机或相册取 1 张图。原图（sizeType:['original']），不压缩。
 * 返回值带 tempFilePath（给 Taro.uploadFile 用）+ size + fileType。
 * 用户取消会 reject —— 调用方应当 catch 后吞掉（取消是常态、不算错）。
 *
 * 命名说明：文件以 `use` 开头是为了和 hooks/ 目录下其它模块保持一致，
 * 但导出的 `captureImage` 是普通 async 函数，不是 React hook，页面直接调用即可。
 *
 * 架构对照：docs/plans/2026-05-18-架构-design.md §4.4 强约束原图上传。
 */
import Taro from '@tarojs/taro';

export interface CapturedImage {
  /** Taro 临时路径，可直接传给 Taro.uploadFile 的 filePath。 */
  tempFilePath: string;
  /** 字节数。 */
  size: number;
  /** 'image' / 'video' 等。 */
  fileType: string;
}

export async function captureImage(): Promise<CapturedImage> {
  const res = await Taro.chooseMedia({
    count: 1,
    mediaType: ['image'],
    sourceType: ['camera', 'album'],
    sizeType: ['original'], // 架构 §4.4：MVP 强约束原图
  });
  const file = res.tempFiles[0];
  return {
    tempFilePath: file.tempFilePath,
    size: file.size,
    fileType: file.fileType,
  };
}
